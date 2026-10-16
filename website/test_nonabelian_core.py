"""Derived core grouping regressions; not a new source-physics review."""
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
import csv
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'atlas'))
from catalogue_identity import canonicalize
from nonabelian_core import restrict_nonabelian,algebra_key

DATA=json.loads((ROOT/'website/field-catalogue.json').read_text())
ENTRIES={e['id']:e for e in DATA['entries']}

def spec(name):return deepcopy(ENTRIES[name]['identity']['input'])
def core(value):return restrict_nonabelian(value)['id']

class NonAbelianCore(unittest.TestCase):
    def test_algebra_projection_forgets_all_matter_but_not_simple_factors(self):
        a=restrict_nonabelian(spec('two-higgs-doublets'))['canonical']
        b=restrict_nonabelian(spec('nmssm-matter'))['canonical']
        self.assertNotEqual(a,b)
        self.assertEqual(algebra_key(a),algebra_key(b))
        b=deepcopy(a);b['matter']=[];b['gauge_factors'].reverse()
        self.assertEqual(algebra_key(a),algebra_key(b))
        b['gauge_factors'].append({'family':'A','rank':1})
        self.assertNotEqual(algebra_key(a)['id'],algebra_key(b)['id'])
        self.assertNotIn('matter',algebra_key(a)['canonical'])
        self.assertEqual(algebra_key({'gauge_factors':[]})['canonical']['gauge_factors'],[])

    def test_three_layer_memberships_are_a_partition(self):
        self.assertEqual(DATA['counts']['semisimpleAlgebras'],14)
        self.assertEqual(len(DATA['semisimpleAlgebras']),14)
        seen_cores=[];seen_entries=[]
        for a in DATA['semisimpleAlgebras']:
            self.assertEqual(a['id'],sha256(json.dumps(a['canonical'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
            self.assertNotIn('matter',a['canonical'])
            children=[c for c in DATA['cores'] if c['semisimpleId']==a['id']]
            self.assertEqual(set(a['coreIds']),{c['id'] for c in children})
            self.assertEqual(set(a['readyEntryIds']),{e for c in children for e in c['entryIds']})
            self.assertEqual(set(a['entryIds']),set(a['readyEntryIds'])|set(a['pendingEntryIds']))
            self.assertFalse(set(a['readyEntryIds'])&set(a['pendingEntryIds']))
            for c in children:self.assertEqual(algebra_key(c['canonical'])['id'],a['id'])
            for entry_id in a['entryIds']:self.assertEqual(ENTRIES[entry_id]['semisimpleId'],a['id'])
            seen_cores.extend(a['coreIds']);seen_entries.extend(a['entryIds'])
        self.assertEqual(len(seen_cores),len(set(seen_cores)))
        self.assertEqual(len(seen_entries),len(set(seen_entries)))
        self.assertEqual(set(seen_cores),{c['id'] for c in DATA['cores']})
        self.assertEqual(len(seen_entries),94)
        self.assertEqual(sum(e['semisimpleId'] is None for e in DATA['entries']),9)
        self.assertTrue(all(e['coreId'] is None for e in DATA['entries'] if e['publicationStatus']=='pending'))

    def test_algebra_membership_does_not_require_complete_matter(self):
        a=next(a for a in DATA['semisimpleAlgebras'] if a['algebra']=='su(5)')
        self.assertEqual(len(a['entryIds']),5)
        self.assertEqual(len(a['readyEntryIds']),4)
        self.assertEqual(a['pendingEntryIds'],['su5-rpv-trilinear-sector'])
        self.assertIsNotNone(ENTRIES['so10-45-126-sector']['semisimpleId'])
        self.assertIsNone(ENTRIES['hidden-valley-colored-x-framework']['semisimpleId'])
        for rank in [None,True,0,-1,2.5]:
            with self.assertRaises(ValueError):algebra_key({'gauge_factors':[{'family':'A','rank':rank}]})

    def test_algebra_csv_and_relational_join(self):
        with (ROOT/'website/downloads/semisimple-algebras.csv').open(newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),14)
        for a in DATA['semisimpleAlgebras']:
            row=next(r for r in rows if r['semisimple_algebra_id']==a['id'])
            self.assertEqual(json.loads(row['cartan_factors']),a['canonical']['gauge_factors'])
            self.assertEqual(set(filter(None,row['core_ids'].split(';'))),set(a['coreIds']))
            self.assertEqual(set(filter(None,row['pending_entry_ids'].split(';'))),set(a['pendingEntryIds']))
        with closing(sqlite3.connect((ROOT/'website/downloads/field-catalogue.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as con:
            self.assertEqual(con.execute('pragma foreign_key_check').fetchall(),[])
            self.assertEqual(con.execute('select count(*) from semisimple_algebras').fetchone()[0],14)
            self.assertEqual(con.execute('select count(*) from entry_layers').fetchone()[0],103)
            for e in DATA['entries']:
                self.assertEqual(con.execute('select semisimple_id,core_id from entry_layers where entry_id=?',(e['id'],)).fetchone(),(e['semisimpleId'],e['coreId']))

    def test_charge_assignments_group_without_merging_full_entries(self):
        for names in [('vlq-t-singlet','vlq-b-singlet'),
                      ('vlq-xt-doublet','vlq-tb-doublet','vlq-by-doublet'),
                      ('vlq-xtb-triplet','vlq-tby-triplet')]:
            self.assertEqual(len({core(spec(name)) for name in names}),1)
            self.assertEqual(len({canonicalize(spec(name))['fingerprint'] for name in names}),len(names))

    def test_multiplicity_and_lorentz_are_part_of_the_core(self):
        a=spec('two-higgs-doublets');b=deepcopy(a)
        b['matter'][-1]['copies']+=1
        self.assertNotEqual(core(a),core(b))
        b=deepcopy(a);b['matter'][-1]['lorentz']['irreps']=[['1/2','0']];b['matter'][-1]['reality']='none'
        self.assertNotEqual(core(a),core(b))
        self.assertNotEqual(core(spec('real-singlet-z2')),core(spec('complex-singlet-portal')))

    def test_lost_charges_merge_identical_fermion_rows(self):
        result=restrict_nonabelian(spec('two-higgs-doublets'))['canonical']
        up_down=next(f for f in result['matter'] if f['lorentz']['irreps']==[['1/2','0']] and f['gauge']==[{'dynkin':[0,1]},{'dynkin':[0]}])
        self.assertEqual(up_down['copies'],6)
        self.assertTrue(all('charge' not in r for f in result['matter'] for r in f['gauge']))

    def test_restriction_preserves_real_scalar_degrees(self):
        a={'schema_version':'field-content-1','inventory_complete':True,
            'gauge_factors':[{'id':'g','family':'A','rank':1},{'id':'q','family':'U1','rank':1}],
            'matter':[{'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']]},
                'reality':'complex','copies':1,'gauge_representations':{'g':{'dynkin':[0]},'q':{'charge':'1'}}}]}
        b=deepcopy(a);b['matter'][0].update(reality='real',copies=2);b['matter'][0]['gauge_representations']['q']['charge']='0'
        self.assertEqual(core(a),core(b))
        self.assertEqual(restrict_nonabelian(a)['canonical']['matter'][0]['copies'],2)
        # A charged weak doublet remains one quaternionic underlying-real
        # module; it must not be doubled merely because its charge is omitted.
        a['matter'][0]['gauge_representations']['g']['dynkin']=[1]
        self.assertEqual(restrict_nonabelian(a)['canonical']['matter'][0]['copies'],1)

    def test_abelian_rank_is_separate_from_core_identity(self):
        a=spec('two-higgs-doublets');b=deepcopy(a)
        b['gauge_factors'].append({'id':'extra','family':'U1','rank':1})
        for f in b['matter']:f['gauge_representations']['extra']={'charge':'0'}
        self.assertEqual(core(a),core(b))
        self.assertEqual(restrict_nonabelian(b)['abelianRank'],2)

    def test_factor_row_names_and_splitting_do_not_change_core(self):
        a=spec('lr-triplet-matter');b=deepcopy(a)
        b['gauge_factors'].reverse();b['matter'].reverse();b['name']='Different label'
        f=next(f for f in b['matter'] if f['copies']==3)
        duplicate=deepcopy(f);f['copies']=2;duplicate['copies']=1;b['matter'].append(duplicate)
        self.assertEqual(core(a),core(b))

    def test_zero_semisimple_algebra_is_not_an_unknown_algebra(self):
        a={'schema_version':'field-content-1','inventory_complete':True,
            'gauge_factors':[{'id':'q','family':'U1','rank':1}],
            'matter':[{'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']]},
                'reality':'complex','copies':1,'gauge_representations':{'q':{'charge':'1'}}}]}
        result=restrict_nonabelian(a)['canonical']
        self.assertEqual(result['gauge_factors'],[])
        self.assertEqual(result['matter'][0]['gauge'],[])
        self.assertEqual(result['matter'][0]['copies'],2)

    def test_exported_keys_and_memberships(self):
        self.assertEqual(DATA['counts']['cores'],15)
        self.assertEqual(sum(len(c['entryIds']) for c in DATA['cores']),19)
        for c in DATA['cores']:
            self.assertEqual(c['id'],sha256(json.dumps(c['canonical'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
            for entry_id in c['entryIds']:
                self.assertEqual(ENTRIES[entry_id]['coreId'],c['id'])
                self.assertEqual(core(spec(entry_id)),c['id'])
        self.assertTrue(all(e['coreId'] is None for e in DATA['entries'] if e['publicationStatus']=='pending'))

    def test_relational_factors_and_core_index(self):
        with closing(sqlite3.connect((ROOT/'website/downloads/field-catalogue.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as con:
            self.assertEqual(con.execute('pragma foreign_key_check').fetchall(),[])
            self.assertEqual(con.execute('select count(*) from nonabelian_cores').fetchone()[0],15)
            self.assertEqual(con.execute('select count(*) from entry_cores where core_id is not null').fetchone()[0],19)
            self.assertEqual(con.execute('select count(*) from entry_cores').fetchone()[0],103)
            self.assertEqual(con.execute("select count(*) from abelian_factors where cartan_family!='U1'").fetchone()[0],0)
            self.assertEqual(con.execute("select count(*) from nonabelian_factors where cartan_family='U1'").fetchone()[0],0)
            for e in DATA['entries']:
                self.assertEqual(con.execute('select core_id,abelian_rank from entry_cores where entry_id=?',(e['id'],)).fetchone(),(e['coreId'],e['abelianRank']))
                for v in e['variants']:
                    for r in v['regimes']:
                        rows=con.execute('select factor_key,cartan_family,rank from gauge_factors where regime_id=? order by factor_order',(r['id'],)).fetchall()
                        self.assertEqual(rows,[(a['key'],a['type'],a['rank']) for a in r['factors']])

    def test_core_csv_has_exact_weights_and_copies(self):
        with (ROOT/'website/downloads/nonabelian-cores.csv').open(newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),sum(len(c['canonical']['matter']) for c in DATA['cores']))
        for c in DATA['cores']:
            actual=[r for r in rows if r['core_id']==c['id']]
            for r,expected in zip(actual,c['canonical']['matter']):
                self.assertEqual(int(r['copies']),expected['copies'])
                self.assertEqual(json.loads(r['dynkin_labels']),[g['dynkin'] for g in expected['gauge']])

if __name__=='__main__':unittest.main()
