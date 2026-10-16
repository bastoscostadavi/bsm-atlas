"""Regression checks for the projection, not independent physics validation."""
from contextlib import closing
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from field_conventions import factor, rational, primitive_scale, dynkin, dimension_a, dimension_d, irrep_dimension, irrep_dimension_label, young_rows, dynkin_representation
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
        self.assertEqual(dynkin_representation([{'factor':'so(10)','value':'16','dynkin':None}]),'(?)')
        self.assertEqual(dynkin_representation([]),'?')

    def test_particle_types(self):
        self.assertEqual(field_type({'field_kind':'vector leptoquark'}),['V'])
        self.assertEqual(field_type({'field_kind':'vector-like quark multiplet'}),['F_D'])
        self.assertEqual(field_type({'field_kind':'chiral superfield'}),['S','F'])
        self.assertEqual(field_type({'field_kind':'two-component higgsino doublet'}),['F'])
        self.assertTrue(excluded({'field_kind':'composite fermionic operator collection'}))
        self.assertTrue(excluded({'field_kind':'vector leptoquark gauge component'}))

    def test_exact_d_series_dimensions_do_not_guess_weights_from_names(self):
        d5=factor('SO(10)')
        for weight,dimension in [([0,0,0,0,0],1),([1,0,0,0,0],10),
                                 ([0,1,0,0,0],45),([0,0,0,1,0],16),
                                 ([0,0,0,0,1],16),([0,0,0,2,0],126),
                                 ([0,0,0,0,2],126)]:
            self.assertEqual(dimension_d(weight),dimension)
            self.assertEqual(irrep_dimension(d5,weight),dimension)
        self.assertEqual(irrep_dimension_label(d5,[0,0,0,1,0]),'16')
        self.assertEqual(irrep_dimension_label(d5,[0,0,0,0,1]),'bar(16)')
        self.assertEqual(irrep_dimension_label(d5,[0,0,0,2,0]),'126')
        self.assertEqual(irrep_dimension_label(d5,[0,0,0,0,2]),'bar(126)')
        self.assertIsNone(dynkin(d5,'16'))
        self.assertIsNone(dimension_d(None))
        for invalid in [[0,0,0],[-1,0,0,0,0],[True,0,0,0,0]]:
            with self.assertRaises(ValueError):dimension_d(invalid)
        with self.assertRaisesRegex(ValueError,'rank mismatch'):
            irrep_dimension(d5,[1,0,0,0])

class Catalogue(unittest.TestCase):
    def test_dynkin_notation_and_metadata(self):
        self.assertEqual(DATA['representationConvention']['id'],'dynkin-gauge-1')
        self.assertIn('Bourbaki',DATA['representationConvention']['nodeNumbering'])
        self.assertEqual(DATA['templates']['R_SM']['fields'][0]['dynkinRepresentation'],'([1,0], [1]; 1)')
        self.assertEqual(ENTRIES['two-higgs-doublets']['summaryFields'][0]['dynkinRepresentation'],'([0,0], [1]; 3)')
        for e in DATA['entries']+DATA['referenceRecords']:
            for v in e['variants']:
                for r in v['regimes']:
                    for f in r['fields']:
                        self.assertEqual(f['dynkinRepresentation'],dynkin_representation(f['components']))
                        for l in f['lorentz']:
                            self.assertEqual(l['dynkinRepresentation'],dynkin_representation(l['gaugeComponents']))

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
        self.assertEqual(len(fs),582)  # Eight GG and one SO(10) inherited occurrence, not new source fields.
        self.assertEqual(len(set(fs)),573)
        self.assertEqual((SITE/'field-catalogue.json').read_bytes(),(ROOT/'atlas/FIELD_CONTENT_CATALOGUE.json').read_bytes())

    def test_normalization_scope(self):
        delta=next(f for f in fields('lr-triplet-matter') if f['label']=='Delta_L')
        self.assertEqual(delta['representation'],'(1, 3, 1; 6)')
        self.assertTrue(delta['notationComplete'])
        self.assertIn('source:2',delta['legacyProjection']['representation'])
        phi=ENTRIES['two-higgs-doublets']['summaryFields'][0]
        self.assertEqual(phi['representation'],'(1, 2; 3)')
        for f in fields('two-higgs-doublets'):
            if f['sourceFieldId'] in {6,7,11,12}:
                self.assertEqual(f['representation'],'(1, 2; 3)')
                self.assertEqual(f['curatedCompletion']['paper'],'1106.0034v3')
        self.assertEqual(ENTRIES['three-higgs-doublets']['summaryFields'][0]['representation'],'(2; 3)')
        chi=fields('u1-chi-minimal16-charge')[0]
        self.assertEqual(next(c['value'] for c in chi['components'] if c['role']=='χ'),'-1')
        self.assertIsNone(next(c['value'] for c in chi['components'] if c['role']=='hypercharge'))

    def test_accepted_reextraction_is_additive_and_deduplicated(self):
        self.assertEqual(DATA['reextraction']['acceptedPapers'],8)
        self.assertEqual(DATA['reextraction']['acceptedCandidates'],12)
        self.assertEqual(DATA['reextraction']['acceptedEntries'],11)
        lr=ENTRIES['lr-triplet-matter']
        self.assertEqual(lr['status'],'recorded_content')
        self.assertEqual(lr['legacyIdentity']['fingerprint'],'1bea82909a308b94c40d2c1531ae7fc4723a2e7a857e521971963aeeb7a40f79')
        self.assertEqual(lr['identity']['input']['schema_version'],'field-content-2')
        for v in lr['variants']:
            r=v['regimes'][0]
            self.assertEqual([a['id'] for a in r['factors']],['A2','A1','A1','u1'])
            self.assertEqual(len(r['fields']),7)
            q=next(f for f in r['fields'] if f['label']=='Q_Rᶜ')
            self.assertEqual(q['copies'],3)
            self.assertEqual(q['components'][0]['dynkin'],[0,1])
            self.assertEqual(q['components'][-1]['value'],'-1')
            self.assertEqual(q['lorentz'][0]['irreps'],[['1/2','0']])
            self.assertTrue(all(f['notationComplete'] for f in r['fields']))
            self.assertTrue(all('legacyProjection' in f for f in r['fields']))
        self.assertEqual({p['id'] for p in DATA['papers'] if p.get('reextractions')},
                         {'P01','P02','P03','P04','P05','P11','P18','P19'})
        self.assertEqual(len(ENTRIES['real-singlet-z2']['reextractions']),2)

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
        with closing(sqlite3.connect((SITE/'downloads/field-catalogue.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as c:
            self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('pragma foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('select count(*) from entries').fetchone()[0],len(DATA['entries']))
            self.assertEqual(c.execute('select count(*) from papers').fetchone()[0],51)
            self.assertEqual(c.execute('select count(*) from extraction_reviews').fetchone()[0],12)
            self.assertEqual(c.execute("select count(*) from entry_papers where paper_id='R01'").fetchone()[0],0)
            self.assertEqual(json.loads(c.execute("select value from metadata where key='representation_convention_json'").fetchone()[0]),DATA['representationConvention'])
            for e in DATA['entries']:
                self.assertEqual(set(r[0] for r in c.execute('select paper_id from entry_papers where entry_id=?',(e['id'],))),set(e['paperIds']))
                for v in e['variants']:
                    for r in v['regimes']:
                        self.assertEqual(c.execute('select factors_json from regimes where regime_id=?',(r['id'],)).fetchone()[0],json.dumps(r['factors'],ensure_ascii=False))
                        for f in r['fields']:
                            row=c.execute('select source_rows_json from multiplets where entry_id=? and regime_id=? and source_field_id=?',(e['id'],r['id'],f['sourceFieldId'])).fetchone()
                            self.assertEqual(json.loads(row[0]),f)
        with (SITE/'downloads/field-catalogue.csv').open(newline='') as stream:
            rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),len(DATA['entries']))
            thdm=next(r for r in rows if r['entry_id']=='two-higgs-doublets')
            self.assertIn('([0,0], [1]; 3)',thdm['additional_recorded_multiplets'])

if __name__=='__main__': unittest.main()
