from fractions import Fraction
from functools import reduce
from math import gcd
import unittest
from stage import *
from catalogue_identity import normalize_spec,canonicalize

class FollowupTests(unittest.TestCase):
    def test_frozen_originals_unchanged(self):self.assertGreater(frozen_unchanged(),100)
    def test_all_ready_v2_and_preflights(self):
        for e in load(HERE/'integration-manifest.json')['entries']:
            if e['status']!='ready_for_curator_integration':continue
            s=load(ROOT/e['normalized_candidate_path'])
            self.assertEqual(s['schema_version'],'field-content-2')
            self.assertEqual(s,normalize_spec(s))
            self.assertEqual(canonicalize(s)['fingerprint'],e['fingerprint'])
            for suffix in ['preflight','require-normalized','duplicates']:
                self.assertEqual(load(HERE/f"{e['target_entry_id']}-{suffix}.json")['fingerprint'],e['fingerprint'])
            ev=load(ROOT/e['evidence_path']);claims={c['id'] for c in ev['claims']}
            raw=load(ROOT/e['source_candidate_path'])
            self.assertEqual({x['candidate_label'] for x in e['source_field_mapping']},{f['label'] for f in raw['matter']})
            for m in e['source_field_mapping']:
                self.assertTrue(set(m['claim_ids'])<=claims)
            for f in s['matter']:
                if f['lorentz']['dimension']==4:self.assertNotIn(['0','1/2'],f['lorentz']['irreps'])
                if f['lorentz']['irreps']==[['0','0']]:self.assertEqual(f['reality'],'real_module')
            for a in s['gauge_factors']:
                if a['family']=='U1':
                    qs=[Fraction(f['gauge_representations'][a['id']]['charge']) for f in s['matter']]
                    self.assertTrue(all(q.denominator==1 for q in qs))
                    if any(qs):self.assertEqual(reduce(gcd,[abs(q.numerator) for q in qs if q]),1)
            accepted={r['entry'] for r in load(ROOT/'atlas/reextraction/accepted-followup.json')['reviews']}
            self.assertEqual(e['accepted_or_published'],e['target_entry_id'] in accepted)
            for k in ['input_tokens','output_tokens','api_dollars','gpu_hours']:self.assertIsNone(e['measurement'][k])
    def test_su5_counts_and_weights(self):
        s=load(HERE/'su5-gg-extra5-two10-normalized.json')
        f={x['label']:x for x in s['matter']}
        self.assertEqual(f['24_H']['copies'],1)
        self.assertEqual(f['10_H,a']['copies'],2)
        self.assertEqual(f['bar5_i']['gauge_representations']['unified']['dynkin'],[0,0,0,1])
        a=load(HERE/'su5-adjoint-renormalizable-normalized.json')
        a={x['label']:x for x in a['matter']}
        self.assertEqual(a['45H']['gauge_representations']['unified']['dynkin'],[1,0,1,0])
        self.assertEqual(a['24H']['copies'],1)
    def test_so10_node_map_dimension_and_indices(self):
        def dim_index(a):
            n=5;lam=[Fraction(0) for _ in range(n)]
            for i,k in enumerate(a):
                w=[Fraction(1 if j<=i else 0) for j in range(n)] if i<3 else [Fraction(1,2)]*n
                if i==3:w[-1]=Fraction(-1,2)
                lam=[x+k*y for x,y in zip(lam,w)]
            rho=list(range(4,-1,-1));dim=Fraction(1)
            for i in range(n):
                for j in range(i+1,n):dim*=((lam[i]+rho[i])**2-(lam[j]+rho[j])**2)/Fraction(rho[i]**2-rho[j]**2)
            casimir=sum(x*(x+2*r) for x,r in zip(lam,rho))/2
            return dim,dim*casimir/45
        self.assertEqual(dim_index([0,0,0,1,0]),(16,2))
        self.assertEqual(dim_index([0,0,0,2,0]),(126,35))
        self.assertEqual(dim_index([0,1,0,0,0]),(45,8))
        self.assertEqual(dim_index([1,0,0,0,0]),(10,1))
        s=load(HERE/'so10-45-126-complex10-normalized.json');f={x['label']:x for x in s['matter']}
        self.assertEqual(f['10H']['copies'],2)
        self.assertEqual(f['16F']['copies'],3)
    def test_sector_is_not_fingerprinted(self):
        for name in ['su5-rpv-trilinear-sector','so10-45-126-sector']:
            e=next(x for x in load(HERE/'integration-manifest.json')['entries'] if x['target_entry_id']==name)
            self.assertNotIn('fingerprint',e)
            self.assertNotIn('normalized_candidate_path',e)
    def test_ksvz_labels_are_unambiguous(self):
        raw=load(HERE/'ksvz-neutral-triplet-source-candidate.json')
        self.assertEqual(len({f['label'] for f in raw['matter']}),len(raw['matter']))
        self.assertIn('Q_KSVZ',{f['label'] for f in raw['matter']})

if __name__=='__main__':unittest.main()
