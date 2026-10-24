"""Catalogue schema, stable identities, ingestion and export regressions."""
from contextlib import closing
from copy import deepcopy
import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
from bsm_atlas.catalogue import load, validate, normalize, identity, ingest, check
from bsm_atlas.catalogue_identity import canonicalize, normalize_spec, IncompleteContent
from bsm_atlas.field_conventions import dimension_a, dimension_d
from bsm_atlas.build import main_data, database

SOURCE=load()
DATA=json.loads((ROOT/'website/field-catalogue.json').read_text())
ENTRIES={e['id']:e for e in SOURCE['entries']}
DATABASE=ROOT/'website/downloads/field-catalogue.sqlite'
NEW_COPIES=sum(f['copies'] for e in SOURCE['entries'] for f in e['specification']['matter'])+1


class CatalogueTests(unittest.TestCase):
    def test_catalogue_identities_references_and_view_memberships(self):
        baseline=json.loads((ROOT/'tests/fixtures/catalogue-identities.json').read_text())
        current={e['id']:e for e in DATA['entries']}
        for key,expected in baseline.items():
            actual=current[key]
            self.assertEqual(actual['identity']['fingerprint'],expected['fingerprint'])
            for layer in ['coreId','semisimpleId','fullAlgebraId']:self.assertEqual(actual[layer],expected[layer])
            self.assertLessEqual(set(expected['paperIds']),set(actual['paperIds']))
        self.assertGreaterEqual(len(current),len(baseline))
        self.assertEqual(DATA['counts'],dict(entries=len(DATA['entries']),papers=len(DATA['papers']),
            linkedPapers=sum(bool(p['entryIds']) for p in DATA['papers']),cores=len(DATA['cores']),
            semisimpleAlgebras=len(DATA['semisimpleAlgebras']),fullAlgebras=len(DATA['fullAlgebras'])))

    def test_source_and_derived_scope(self):
        self.assertEqual(set(SOURCE),{'schema_version','papers','entries'})
        for e in SOURCE['entries']:
            self.assertLessEqual(set(e),{'id','name','specification','references','aliases'})
            self.assertEqual(normalize(e['specification']),e['specification'])
            exported=next(x for x in DATA['entries'] if x['id']==e['id'])
            self.assertEqual(exported['specification'],e['specification'])
            self.assertEqual(identity(e['specification'])['fingerprint'],exported['identity']['fingerprint'])
            for row in e['specification']['matter']:
                self.assertEqual(set(row),{'lorentz','reality','copies','gauge_representations'})
            for row in exported['regime']['rows']:
                self.assertEqual(set(row),{'copies','components','lorentz'})
        for p in SOURCE['papers']:
            self.assertLessEqual({'id','arxiv','title','authors'},set(p))
            self.assertLessEqual(set(p),{'id','arxiv','title','authors','extraction_status'})
        self.assertFalse(next(p for p in DATA['papers'] if p['id']=='R01')['entryIds'])
        self.assertFalse(any(a['algebra']=='su(2)' for a in DATA['semisimpleAlgebras']))

    def test_bad_objects_cannot_be_stored(self):
        for change in ['extras','partial','copies','weight','charge-array','charge-float','charge-unknown','unnormalized','unknown-paper','duplicate','wrong-rank','unversioned','duplicate-alias']:
            bad=deepcopy(SOURCE);e=bad['entries'][0];s=e['specification'];f=s['matter'][0]
            if change=='extras':e['interactions']=[]
            if change=='partial':s['inventory_complete']=False
            if change=='copies':f['copies']=True
            if change=='weight':f['gauge_representations'][s['gauge_factors'][0]['id']]={'dynkin':[-1]}
            if change.startswith('charge-'):
                q=next(a['id'] for a in s['gauge_factors'] if a['family']=='U1')
                f['gauge_representations'][q]['charge']={'charge-array':[0,-3,3],'charge-float':1.0,'charge-unknown':'?'}[change]
            if change=='unnormalized':
                q=next(a['id'] for a in s['gauge_factors'] if a['family']=='U1')
                for row in s['matter']:row['gauge_representations'][q]['charge']=str(2*int(row['gauge_representations'][q]['charge']))
            if change=='unknown-paper':e['references'][0]['paper_id']='missing'
            if change=='duplicate':
                clone=deepcopy(e);clone['id']='another-name';bad['entries'].append(clone)
            if change=='wrong-rank':s['gauge_factors'][0]['rank']=True
            if change=='unversioned':bad['papers'][0]['arxiv']='1905.13729'
            if change=='duplicate-alias':e['aliases']=[{'id':bad['entries'][-1]['id'],'name':'duplicate'}]
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):validate(bad)

    def test_numeric_identity_invariances(self):
        a=deepcopy(ENTRIES['lr-triplet-matter']['specification']);b=deepcopy(a)
        b['gauge_factors'].reverse();b['matter'].reverse()
        for row in b['matter']:
            for factor in b['gauge_factors']:
                if factor['family']=='U1':row['gauge_representations'][factor['id']]['charge']=str(-7*int(row['gauge_representations'][factor['id']]['charge']))
        self.assertEqual(canonicalize(a),canonicalize(b))
        f=next(row for row in b['matter'] if row['copies']>1);clone=deepcopy(f);clone['copies']=1;f['copies']-=1;b['matter'].append(clone)
        self.assertEqual(canonicalize(a),canonicalize(b))
        f['copies']+=1
        self.assertNotEqual(canonicalize(a),canonicalize(b))

    def test_free_text_is_not_representation_data(self):
        for entry_id in ['two-higgs-doublets','u1-ybl-charge-family']:
            for location in ['specification','factor','row','lorentz','representation']:
                for key in ['label','symbol']:
                    spec=deepcopy(ENTRIES[entry_id]['specification'])
                    row=spec['matter'][0]
                    target={'specification':spec,'factor':spec['gauge_factors'][0],
                            'row':row,'lorentz':row['lorentz'],
                            'representation':next(iter(row['gauge_representations'].values()))}[location]
                    target[key]='Q'
                    with self.subTest(entry=entry_id,location=location,key=key),self.assertRaises(IncompleteContent):
                        normalize(spec)
            for key,value in [('name','A field inventory'),('paper_ids',['P01'])]:
                spec=deepcopy(ENTRIES[entry_id]['specification']);spec[key]=value
                with self.subTest(entry=entry_id,key=key),self.assertRaises(IncompleteContent):normalize(spec)

    def test_right_handed_conversion_and_dirac_splitting(self):
        s=deepcopy(ENTRIES['vlq-t-singlet']['specification'])
        f=next(f for f in s['matter'] if f['gauge_representations']=={'colour':{'dynkin':[1,0]},'weak_L':{'dynkin':[0]},'hypercharge':{'charge':'4'}})
        source=deepcopy(s);source['matter']=[deepcopy(f)]
        right=deepcopy(source);right['matter'][0]['lorentz']['irreps']=[['0','1/2']]
        normalized=normalize_spec(right)['matter'][0]
        self.assertEqual(normalized['lorentz']['irreps'],[['1/2','0']])
        self.assertEqual(normalized['gauge_representations']['colour']['dynkin'],[0,1])
        self.assertEqual(normalized['gauge_representations']['hypercharge']['charge'],'-1')
        source['matter'][0]['lorentz']['irreps']=[['1/2','0'],['0','1/2']]
        self.assertEqual(len(normalize_spec(source)['matter']),2)

    def test_ingestion_normalizes_and_merges_instead_of_duplicating(self):
        candidate=deepcopy(ENTRIES['two-higgs-doublets']);candidate['id']='another-two-higgs-name'
        candidate['references']=[{'paper_id':'P15','locators':['Table 1']}]
        s=candidate['specification']
        q=next(a['id'] for a in s['gauge_factors'] if a['family']=='U1')
        for f in s['matter']:f['gauge_representations'][q]['charge']=str(2*int(f['gauge_representations'][q]['charge']))
        before=deepcopy(SOURCE);after,target=ingest(SOURCE,candidate)
        self.assertEqual(SOURCE,before);self.assertEqual(len(after['entries']),len(SOURCE['entries']))
        self.assertEqual(target,'two-higgs-doublets')
        entry=next(e for e in after['entries'] if e['id']==target)
        self.assertIn({'paper_id':'P15','locators':['Table 1']},entry['references'])
        self.assertIn({'id':'another-two-higgs-name','name':candidate['name']},entry['aliases'])
        for extra in ['interactions','claims']:
            bad=deepcopy(candidate);bad[extra]=[]
            with self.assertRaises(ValueError):ingest(SOURCE,bad)
        bad=deepcopy(candidate);bad['references'][0]['claims']=[]
        with self.assertRaises(ValueError):ingest(SOURCE,bad)

    def test_ingestion_new_entry_and_empty_family(self):
        candidate=deepcopy(ENTRIES['two-higgs-doublets']);candidate['id']='three-extra-higgs-benchmark'
        candidate.pop('aliases',None)  # Navigation aliases belong to the original identity.
        candidate['specification']['matter'][-1]['copies']+=NEW_COPIES
        after,target=ingest(SOURCE,candidate)
        self.assertEqual(len(after['entries']),len(SOURCE['entries'])+1);self.assertEqual(target,candidate['id'])
        numeric=deepcopy(ENTRIES['two-higgs-doublets'])
        numeric['specification'].update(schema_version='field-content-3',parameters={},constraints=[])
        after,target=ingest(SOURCE,numeric)
        self.assertEqual(target,'two-higgs-doublets');self.assertEqual(len(after['entries']),len(SOURCE['entries']))

    def test_ingestion_cli_is_dry_by_default_and_atomic_on_validation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'source.json';p.write_text(json.dumps(SOURCE))
            candidate=Path(directory)/'candidate.json';c=deepcopy(ENTRIES['two-higgs-doublets'])
            c.pop('aliases',None)
            c['specification']['matter'][-1]['copies']+=NEW_COPIES;c['id']='a-new-higgs-model'
            candidate.write_text(json.dumps(c));before=p.read_bytes()
            command=[sys.executable,'-B','-m','bsm_atlas','add',str(candidate),'--source',str(p)]
            run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(p.read_bytes(),before)
            run=subprocess.run([*command,'--write'],cwd=ROOT,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(len(load(p)['entries']),len(SOURCE['entries'])+1)
            before=p.read_bytes();c['references'][0]['paper_id']='missing';candidate.write_text(json.dumps(c))
            run=subprocess.run([*command,'--write'],cwd=ROOT,capture_output=True,text=True);self.assertEqual(run.returncode,2);self.assertEqual(p.read_bytes(),before)

    def test_lookup_exact_and_nearby(self):
        s=deepcopy(ENTRIES['two-higgs-doublets']['specification'])
        self.assertEqual(check(s,DATABASE)['matches'][0]['entry_id'],'two-higgs-doublets')
        s['matter'][-1]['copies']+=NEW_COPIES
        self.assertTrue(check(s,DATABASE)['same_algebra_candidates'])

    def test_new_entry_projects_to_every_view_and_export(self):
        candidate=deepcopy(ENTRIES['two-higgs-doublets']);candidate['id']='growth-test-model'
        candidate.pop('aliases',None)
        candidate['specification']['matter'][-1]['copies']+=NEW_COPIES
        source,target=ingest(SOURCE,candidate)
        expanded=main_data(source)
        self.assertEqual(expanded['counts']['entries'],len(SOURCE['entries'])+1)
        self.assertIn(target,[e['id'] for e in expanded['entries']])
        for kind in ['cores','fullAlgebras','semisimpleAlgebras']:
            self.assertEqual(sum(len(g['entryIds']) for g in expanded[kind]),len(expanded['entries']))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'expanded.sqlite';database(path,expanded)
            with closing(sqlite3.connect(path)) as con:
                self.assertEqual(con.execute('SELECT count(*) FROM entries').fetchone()[0],len(expanded['entries']))

    def test_exact_dimension_displays(self):
        self.assertEqual(dimension_a([1,0]),3);self.assertEqual(dimension_a([0,1]),3)
        self.assertEqual(dimension_a([2,1]),15);self.assertEqual(dimension_a([4,0]),15)
        for weights,dimension in [([0,0,0,1,0],16),([1,0,0,0,0],10),([0,1,0,0,0],45),([0,0,0,2,0],126)]:
            self.assertEqual(dimension_d(weights),dimension)

    def test_reference_shortcuts_are_derived_not_truncated_sources(self):
        for entry in DATA['entries']:
            regime=entry['regime']
            if regime.get('baseline'):
                self.assertEqual(len(regime['factors']),3)
                self.assertTrue(regime['rows'])
                self.assertEqual(sum(r['copies'] for r in regime['rows']),
                    sum(r['copies'] for r in regime['additionalRows'])+sum(r['copies'] for r in DATA['templates'][regime['baseline']]['rows']))
        nm=next(e for e in DATA['entries'] if e['id']=='nmssm-matter')
        self.assertEqual(nm['regime']['baseline'],'R_MSSM')
        self.assertEqual(sorted(r['copies'] for r in nm['regime']['additionalRows']),[1,2])
        thdm=next(e for e in DATA['entries'] if e['id']=='two-higgs-doublets')['regime']
        self.assertEqual(thdm['baseline'],'F_SM')
        self.assertEqual(thdm['additionalRows'][0]['copies'],2)

    def test_sql_roundtrips_precise_objects_and_references(self):
        with closing(sqlite3.connect(DATABASE)) as con:
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(tables,{'metadata','papers','entries','aliases','entry_papers','gauge_factors','matter','matter_representations','entry_parameters','entry_constraints','semisimple_algebras','full_gauge_algebras','nonabelian_cores'})
            views={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view'")}
            self.assertEqual(views,{'entry_layers','entry_identity'})
            self.assertEqual([r[1] for r in con.execute('PRAGMA table_info(matter)')],['entry_id','row_id','lorentz_json','reality','copies'])
            for e in SOURCE['entries']:
                spec=e['specification']
                self.assertEqual(json.loads(con.execute('SELECT specification_json FROM entries WHERE entry_id=?',(e['id'],)).fetchone()[0]),spec)
                self.assertEqual(con.execute('SELECT count(*) FROM matter WHERE entry_id=?',(e['id'],)).fetchone()[0],len(spec['matter']))
                self.assertEqual({r[0] for r in con.execute('SELECT paper_id FROM entry_papers WHERE entry_id=?',(e['id'],))},{r['paper_id'] for r in e['references']})
                for i,f in enumerate(spec['matter']):
                    lorentz,reality,copies=con.execute('SELECT lorentz_json,reality,copies FROM matter WHERE entry_id=? AND row_id=?',(e['id'],i)).fetchone()
                    self.assertEqual((json.loads(lorentz),reality,copies),(f['lorentz'],f['reality'],f['copies']))
                    for factor in spec['gauge_factors']:
                        w,q,p=con.execute('SELECT dynkin_json,charge,charge_expression FROM matter_representations WHERE entry_id=? AND row_id=? AND factor_id=?',(e['id'],i,factor['id'])).fetchone()
                        expected=f['gauge_representations'][factor['id']]
                        self.assertEqual({'dynkin':json.loads(w)} if w is not None else {'charge':q if q is not None else p},expected)
            self.assertGreater(con.execute('SELECT count(*) FROM matter_representations WHERE charge_expression IS NOT NULL').fetchone()[0],0)

    def test_integer_storage_guard_and_arbitrary_precision(self):
        with closing(sqlite3.connect(DATABASE)) as source,closing(sqlite3.connect(':memory:')) as con:
            source.backup(con)
            for value in ['[0,-3,3]','z1','1/2','source:2','1.0','--3','01','-0','']:
                with self.subTest(value=value),self.assertRaises(sqlite3.IntegrityError):
                    con.execute("UPDATE matter_representations SET charge=? WHERE entry_id='two-higgs-doublets' AND factor_id='hypercharge'",(value,))
            value=str(10**100)
            con.execute("UPDATE matter_representations SET charge=? WHERE entry_id='two-higgs-doublets' AND factor_id='hypercharge'",(value,))
            self.assertEqual(con.execute("SELECT charge FROM matter_representations WHERE entry_id='two-higgs-doublets' AND factor_id='hypercharge' LIMIT 1").fetchone()[0],value)

    def test_all_downloads_retain_exact_content(self):
        with (ROOT/'website/downloads/field-catalogue.csv').open(newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),len(DATA['entries']))
        for row in rows:self.assertEqual(json.loads(row['specification_json']),ENTRIES[row['entry_id']]['specification'])
        for kind,file in [('cores','nonabelian-cores'),('semisimpleAlgebras','semisimple-algebras'),('fullAlgebras','full-gauge-algebras')]:
            with (ROOT/'website/downloads'/str(file+'.csv')).open(newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),len(DATA[kind]))
            for row in rows:self.assertEqual(json.loads(row['canonical_json']),next(g['canonical'] for g in DATA[kind] if g['id']==row['id']))

if __name__=='__main__':unittest.main()
