"""Semisimple restrictions, matter grouping and exact identity regressions."""
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

def spec(name):return deepcopy(ENTRIES[name]['specification'])
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
        a={'schema_version':'field-content-2','inventory_complete':True,
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
        a={'schema_version':'field-content-2','inventory_complete':True,
            'gauge_factors':[{'id':'q','family':'U1','rank':1}],
            'matter':[{'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']]},
                'reality':'complex','copies':1,'gauge_representations':{'q':{'charge':'1'}}}]}
        result=restrict_nonabelian(a)['canonical']
        self.assertEqual(result['gauge_factors'],[])
        self.assertEqual(result['matter'][0]['gauge'],[])
        self.assertEqual(result['matter'][0]['copies'],2)

    def test_exported_keys_and_memberships(self):
        self.assertEqual(DATA['counts']['cores'],len(DATA['cores']))
        self.assertEqual(sum(len(c['entryIds']) for c in DATA['cores']),len(DATA['entries']))
        for c in DATA['cores']:
            self.assertEqual(c['id'],sha256(json.dumps(c['canonical'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
            for entry_id in c['entryIds']:
                self.assertEqual(ENTRIES[entry_id]['coreId'],c['id'])
                self.assertEqual(core(spec(entry_id)),c['id'])


if __name__=='__main__':unittest.main()
