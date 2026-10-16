"""Regression checks for the projection, not independent physics validation."""
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from field_conventions import factor, rational, primitive_scale, dynkin, dimension_a, young_rows
from build_field_catalogue import field_type, excluded

SITE=Path(__file__).resolve().parent
ROOT=SITE.parent
DATA=json.loads((SITE/'field-catalogue.json').read_text())
ENTRIES={e['id']:e for e in DATA['entries']}

def fields(entry):
    return [f for v in ENTRIES[entry]['variants'] for r in v['regimes'] for f in r['fields']]

class Conventions(unittest.TestCase):
    def test_exact_normalization(self):
        self.assertEqual(rational('−1/6'),Fraction(-1,6))
        self.assertIsNone(rational('0.1'))
        self.assertIsNone(rational('q/3'))
        self.assertEqual(primitive_scale([Fraction(1,6),Fraction(-2,3),Fraction(1)]),6)
        self.assertEqual(primitive_scale([Fraction(2),Fraction(4)]),Fraction(1,2))
        self.assertIsNone(primitive_scale([Fraction(0)]))

    def test_irrep_not_dimension_or_copies(self):
        a=factor('SU(3)')
        self.assertEqual(dynkin(a,'3'),[1,0])
        self.assertEqual(dynkin(a,'bar(3)'),[0,1])
        self.assertEqual(dimension_a([1,0]),3)
        self.assertEqual(dimension_a([1,1]),8)
        self.assertEqual(young_rows(a,[0,1]),[1,1])
        self.assertIsNone(dynkin(factor('SO(10)'),'16'))
        self.assertEqual(factor('Spin(6)')['id'],factor('SU(4)')['id'])

    def test_particle_types(self):
        self.assertEqual(field_type({'field_kind':'vector leptoquark'}),['V'])
        self.assertEqual(field_type({'field_kind':'vector-like quark multiplet'}),['F_D'])
        self.assertEqual(field_type({'field_kind':'chiral superfield'}),['S','F'])
        self.assertEqual(field_type({'field_kind':'two-component higgsino doublet'}),['F'])
        self.assertTrue(excluded({'field_kind':'composite fermionic operator collection'}))
        self.assertTrue(excluded({'field_kind':'vector leptoquark gauge component'}))

class Catalogue(unittest.TestCase):
    def test_papers_independent_from_models(self):
        self.assertEqual(DATA['counts']['seedPapers'],50)
        self.assertEqual(len(DATA['papers']),51)
        p=next(p for p in DATA['papers'] if p['arxiv']=='1905.13729v1')
        self.assertEqual(p['entryIds'],[])
        self.assertTrue(p['referenceOnly'])
        self.assertFalse(any(p['id'] in e['paperIds'] for e in DATA['entries']))
        for eid in ['sm-eft-matter','general-gauge-mediation','abelian-stueckelberg-sector']:
            self.assertNotIn(eid,ENTRIES)
        self.assertEqual(next(p for p in DATA['papers'] if p['id']=='P47')['entryIds'],[])

    def test_source_coverage_and_immutability(self):
        self.assertEqual(hashlib.sha256((ROOT/'atlas/atlas.sqlite').read_bytes()).hexdigest(),
            'd4dbf023b667fe810296c43c8f72e0d0b3f6559e66b344a2920c9e2e520e6c4c')
        records=DATA['entries']+DATA['referenceRecords']
        models=[v['id'] for e in records for v in e['variants']]
        fs=[f['sourceFieldId'] for e in records for v in e['variants'] for r in v['regimes'] for f in r['fields']]
        self.assertEqual(len(models),125)
        self.assertEqual(len(set(models)),125)
        self.assertEqual(len(fs),573)
        self.assertEqual(len(set(fs)),573)
        self.assertEqual((SITE/'field-catalogue.json').read_bytes(),(ROOT/'atlas/FIELD_CONTENT_CATALOGUE.json').read_bytes())

    def test_normalization_scope(self):
        delta=next(f for f in fields('lr-triplet-matter') if f['label']=='ΔL')
        self.assertIn('source:2',delta['representation'])
        self.assertFalse(delta['notationComplete'])
        phi=ENTRIES['two-higgs-doublets']['summaryFields'][0]
        self.assertEqual(phi['representation'],'(?, 2; 3)')
        self.assertEqual(ENTRIES['three-higgs-doublets']['summaryFields'][0]['representation'],'(2; 3)')
        chi=fields('u1-chi-minimal16-charge')[0]
        self.assertEqual(next(c['value'] for c in chi['components'] if c['role']=='χ'),'-1')
        self.assertIsNone(next(c['value'] for c in chi['components'] if c['role']=='hypercharge'))

    def test_baselines_and_scopes(self):
        q=DATA['templates']['R_SM']['fields'][0]
        self.assertEqual(q['copies'],3)
        self.assertEqual(q['representation'],['3','2','1'])
        self.assertEqual(ENTRIES['nmssm-matter']['baseline'],'R_MSSM')
        self.assertEqual(ENTRIES['two-higgs-doublets']['baseline'],'F_SM')
        self.assertEqual(ENTRIES['numsm']['status'],'partial')
        self.assertEqual(ENTRIES['vlq-t-singlet']['summaryFields'][0]['kinds'],['F_D'])
        self.assertEqual(ENTRIES['lq-u1-effective']['summaryFields'][0]['kinds'],['V'])
        r=next(r for v in ENTRIES['littlest-higgs-minimal']['variants'] for r in v['regimes'] if r['id']==131)
        self.assertEqual(len(r['factors']),4) # UV, not UV plus diagonal subgroup

    def test_sqlite_and_csv_roundtrip(self):
        with sqlite3.connect((SITE/'downloads/field-catalogue.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as c:
            self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('pragma foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('select count(*) from entries').fetchone()[0],len(DATA['entries']))
            self.assertEqual(c.execute('select count(*) from papers').fetchone()[0],51)
            self.assertEqual(c.execute("select count(*) from entry_papers where paper_id='R01'").fetchone()[0],0)
            for e in DATA['entries']:
                self.assertEqual(set(r[0] for r in c.execute('select paper_id from entry_papers where entry_id=?',(e['id'],))),set(e['paperIds']))
                for v in e['variants']:
                    for r in v['regimes']:
                        self.assertEqual(c.execute('select factors_json from regimes where regime_id=?',(r['id'],)).fetchone()[0],json.dumps(r['factors'],ensure_ascii=False))
                        for f in r['fields']:
                            row=c.execute('select source_rows_json from multiplets where source_field_id=?',(f['sourceFieldId'],)).fetchone()
                            self.assertEqual(json.loads(row[0]),f)
        with (SITE/'downloads/field-catalogue.csv').open(newline='') as stream:
            self.assertEqual(len(list(csv.DictReader(stream))),len(DATA['entries']))

if __name__=='__main__': unittest.main()
