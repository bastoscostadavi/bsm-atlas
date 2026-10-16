import copy
from fractions import Fraction
import json
from pathlib import Path
import sqlite3
import sys
import unittest
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'atlas'))
from catalogue_identity import canonicalize,normalize_spec,conjugate,IncompleteContent
from check_entry import check
from prepare_entry import prepare
from spacetime_conventions import field_reps,spacetime
DATA=json.loads((ROOT/'website/field-catalogue.json').read_text())
ENTRIES={e['id']:e for e in DATA['entries']}
def spec(e):return copy.deepcopy(ENTRIES[e]['identity']['input'])
def fingerprint(x):return canonicalize(x)['fingerprint']

class Identity(unittest.TestCase):
    def test_normalize_before_persistence_not_only_inside_fingerprint(self):
        expected=spec('two-higgs-doublets');source=copy.deepcopy(expected)
        for f in source['matter']:
            for rep in f['gauge_representations'].values():
                if 'charge' in rep:rep['charge']=str(Fraction(rep['charge'])/6)
        original=copy.deepcopy(source)
        result=prepare(source,ROOT/'website/downloads/field-catalogue.sqlite')
        self.assertEqual(result['normalized_entry'],expected)
        self.assertEqual(source,original)
        self.assertEqual(result['transformations'][0]['positive_source_scale'],'6')
        self.assertEqual(result['duplicate_check']['status'],'exact_field_content_match')
        self.assertEqual(normalize_spec(result['normalized_entry']),result['normalized_entry'])

    def test_lr_charge_unit_uses_all_fields(self):
        a={'schema_version':'field-content-1','inventory_complete':True,'gauge_factors':[{'id':'bl','family':'U1','rank':1}],'matter':[]}
        for label,q in [('quark','1/3'),('lepton','-1'),('triplet','2')]:
            a['matter'].append({'label':label,'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']]},'reality':'complex','copies':1,'gauge_representations':{'bl':{'charge':q}}})
        result=prepare(a)
        self.assertEqual([f['gauge_representations']['bl']['charge'] for f in result['normalized_entry']['matter']],['1','-3','6'])
        self.assertEqual(result['transformations'][0]['positive_source_scale'],'3')

    def test_preflight_blocks_unfinished_and_untyped_inputs(self):
        for charge in ['?', 'q', 'source:2',0.5,{'status':'not_extracted'}]:
            a=spec('two-higgs-doublets')
            u1=next(f['id'] for f in a['gauge_factors'] if f['family']=='U1')
            a['matter'][0]['gauge_representations'][u1]={'charge':charge}
            with self.assertRaises(IncompleteContent):prepare(a)
        a=spec('two-higgs-doublets');a['inventory_complete']=False
        with self.assertRaises(IncompleteContent):prepare(a)
        a=spec('two-higgs-doublets');a['matter'][0]['unvalidated_source_note']='not a canonical field'
        with self.assertRaises(IncompleteContent):prepare(a)
        a=spec('two-higgs-doublets');a['gauge_factors'][0]['rank']=True
        with self.assertRaises(IncompleteContent):prepare(a)
        a=spec('two-higgs-doublets');a['matter'][-1]['reality']='real'
        with self.assertRaises(IncompleteContent):prepare(a)

    def test_order_names_charge_scaling_and_sign(self):
        a=spec('two-higgs-doublets');b=copy.deepcopy(a)
        b['name']='Another paper calls it something else';b['paper_ids']=['new-paper']
        b['matter'].reverse();b['gauge_factors'].reverse()
        for f in b['matter']:
            for r in f['gauge_representations'].values():
                if 'charge' in r:r['charge']=str(Fraction(r['charge'])*-7)
        self.assertEqual(fingerprint(a),fingerprint(b))
        scalar=b['matter'].pop(0)
        b['matter'].extend([copy.deepcopy(scalar)])
        # Splitting/merging identical irrep rows preserves their TOTAL copies.
        scalar=next(f for f in b['matter'] if f['copies']==3)
        scalar['copies']=2;clone=copy.deepcopy(scalar);clone['copies']=1;b['matter'].append(clone)
        self.assertEqual(fingerprint(a),fingerprint(b))

    def test_right_to_left_conjugates_every_factor(self):
        a=spec('real-singlet-z2');b=copy.deepcopy(a)
        f=next(f for f in b['matter'] if f.get('label')=='uᶜ')
        f['lorentz']['irreps']=[['0','1/2']]
        f['gauge_representations']={a['id']:conjugate(f['gauge_representations'][a['id']],a) for a in b['gauge_factors']}
        self.assertEqual(fingerprint(a),fingerprint(b))
        wrong=copy.deepcopy(b);f=next(f for f in wrong['matter'] if f.get('label')=='uᶜ')
        colour=next(a for a in wrong['gauge_factors'] if a['family']=='A' and a['rank']==2)
        f['gauge_representations'][colour['id']]['dynkin']=[0,1] # Negating only Y is not equivalent.
        self.assertNotEqual(fingerprint(a),fingerprint(wrong))

    def test_dirac_and_weyl_pair_agree_not_deleted(self):
        a=spec('vlq-t-singlet');b=copy.deepcopy(a)
        b['matter'].pop();b['matter'][-1]['lorentz']['irreps']=[['1/2','0'],['0','1/2']]
        self.assertEqual(fingerprint(a),fingerprint(b))
        no_pair=copy.deepcopy(a);no_pair['matter']=no_pair['matter'][:-2]
        self.assertNotEqual(fingerprint(a),fingerprint(no_pair))

    def test_incomplete_never_unique_and_reality_matters(self):
        self.assertNotEqual(fingerprint(spec('real-singlet-z2')),fingerprint(spec('complex-singlet-portal')))
        a=spec('two-higgs-doublets');a['matter'][0]['copies']=None
        with self.assertRaises(IncompleteContent):canonicalize(a)
        self.assertEqual(ENTRIES['three-higgs-doublets']['identity']['status'],'unresolved')
        self.assertEqual(ENTRIES['numsm']['identity']['status'],'unresolved')

    def test_readonly_lookup_and_registry(self):
        database=ROOT/'website/downloads/field-catalogue.sqlite'
        result=check(spec('nmssm-matter'),database)
        self.assertEqual(result['status'],'exact_field_content_match')
        self.assertIn('nmssm-matter',[e['entry_id'] for e in result['matches']])
        with sqlite3.connect(database) as c:
            self.assertEqual(c.execute('pragma foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('select count(*) from entry_identity').fetchone()[0],103)
            conjugate_row='vlq-t-singlet:73:1'
            self.assertEqual(c.execute("select charge from component_gauge_representations where component_id=? and role='hypercharge'",(conjugate_row,)).fetchone()[0],'-4')
            self.assertEqual(json.loads(c.execute("select dynkin_json from component_gauge_representations where component_id=? and role='colour'",(conjugate_row,)).fetchone()[0]),[0,1])
            for e in DATA['entries']:
                h=e['identity']['fingerprint']
                if h:self.assertEqual(h,fingerprint(e['identity']['input']))
            rows=c.execute('select representation_json from spacetime_representations').fetchall()
            for row in rows:
                l=json.loads(row[0])
                if l['spacetime']['dimension']=='4' and l['component']=='F':self.assertEqual(l['irreps'],[['1/2','0']])

    def test_dimension_and_chiral_superfield(self):
        self.assertEqual(len(field_reps(['S','F'])),2)
        d5=spacetime({'spacetime_dimension':'5'},{'field_kind':'bulk Dirac fermion'})
        self.assertEqual(field_reps(['F_D'],scope=d5)[0]['label'],'[0,1]')
        self.assertEqual(len(field_reps(['F_D'],scope=d5)),1)
        brane=spacetime({'spacetime_dimension':'5'},{'field_kind':'IR-brane fermion'})
        self.assertEqual(brane['dimension'],'4')
        d6=spacetime({'spacetime_dimension':'6'})
        self.assertEqual(field_reps(['F'],scope=d6)[0]['status'],'chirality_unresolved')

if __name__=='__main__':unittest.main()
