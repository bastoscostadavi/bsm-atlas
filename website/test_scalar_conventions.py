"""Exact scalar counting and identity regressions, not source-physics review."""
from contextlib import closing
from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
import sys
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'atlas'))
from scalar_conventions import dual_weight, representation_type, real_scalar
from catalogue_identity import canonicalize, normalize_spec, IncompleteContent

def single(family='A', weight=(0,), charge=0, reality='complex', copies=1):
    return {'schema_version':'field-content-2','inventory_complete':True,
        'gauge_factors':[{'id':'g','family':family,'rank':len(weight)},{'id':'q','family':'U1','rank':1}],
        'matter':[{'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']]},
            'reality':reality,'copies':copies,'gauge_representations':{'g':{'dynkin':list(weight)},'q':{'charge':str(charge)}}}]}

def fp(spec):return canonicalize(spec)['fingerprint']

class ScalarModules(unittest.TestCase):
    def test_real_complex_and_pseudoreal_types(self):
        cases=[('A',(1,),'pseudoreal'),('A',(2,),'real'),('A',(1,0),'complex'),
            ('A',(1,1),'real'),('C',(1,0),'pseudoreal'),('C',(0,2),'real'),
            ('B',(0,0,1),'real'),('B',(0,0,0,1),'real'),
            ('D',(0,0,0,0,0,1),'pseudoreal'),('E',(0,0,0,0,0,0,1),'pseudoreal'),
            ('F',(0,0,0,1),'real'),('G',(1,0),'real')]
        for family,weight,expected in cases:
            s=single(family,weight)
            self.assertEqual(representation_type(s['gauge_factors'],s['matter'][0]['gauge_representations']),expected)
        self.assertEqual(dual_weight('E',(1,0,0,0,0,0)),(0,0,0,0,0,1))

    def test_complex_singlet_equals_two_real_not_one(self):
        a=single();b=single(reality='real',copies=2);c=single(reality='real')
        self.assertEqual(fp(a),fp(b));self.assertNotEqual(fp(a),fp(c))
        n=normalize_spec(a)
        self.assertEqual(n['matter'][0]['copies'],2)
        self.assertEqual(n['matter'][0]['reality'],'real_module')
        self.assertEqual(n,normalize_spec(n))

    def test_pseudoreal_product_is_real(self):
        s=single(weight=(1,));s['gauge_factors'].append({'id':'h','family':'A','rank':1})
        s['matter'][0]['gauge_representations']['h']={'dynkin':[1]}
        self.assertEqual(normalize_spec(s)['matter'][0]['copies'],2)
        s['matter'][0]['reality']='real'
        self.assertEqual(normalize_spec(s)['matter'][0]['copies'],1)

    def test_charged_and_pseudoreal_scalars_not_doubled(self):
        for s in [single(charge=3),single(weight=(1,))]:
            self.assertEqual(normalize_spec(s)['matter'][0]['copies'],1)
            s['matter'][0]['reality']='real'
            with self.assertRaises(IncompleteContent):normalize_spec(s)

    def test_scalar_full_conjugation_but_not_weyl(self):
        a=single(weight=(1,0),charge=1)
        # A fixed chiral spectator prevents a common U(1) sign from identifying
        # the two fermionic spectra accidentally.
        spectator=deepcopy(a['matter'][0]);spectator['lorentz']['irreps']=[['1/2','0']]
        spectator['reality']='none';spectator['gauge_representations']['q']['charge']='2'
        a['matter'].append(spectator)
        b=deepcopy(a);b['matter'][0]['gauge_representations']={'g':{'dynkin':[0,1]},'q':{'charge':'-1'}}
        self.assertEqual(fp(a),fp(b))
        for s in [a,b]:
            s['matter'][0]['lorentz']['irreps']=[['1/2','0']];s['matter'][0]['reality']='none'
        self.assertNotEqual(fp(a),fp(b))

    def test_factor_order_sign_scaling_and_higher_dimension(self):
        a=single(weight=(1,),charge=-2);b=deepcopy(a)
        b['gauge_factors'].reverse();b['matter'][0]['gauge_representations']['q']['charge']='12'
        self.assertEqual(fp(a),fp(b))
        a['matter'][0]['lorentz']={'dimension':5,'scheme':'B2_Dynkin','irreps':[[0,0]]}
        self.assertEqual(normalize_spec(a)['matter'][0]['reality'],'real_module')


if __name__=='__main__':unittest.main()
