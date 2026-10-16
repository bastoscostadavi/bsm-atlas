"""Mechanical staging/provenance checks; not independent source-physics review."""
from collections import Counter
from fractions import Fraction
from functools import reduce
from hashlib import sha256
import json
from math import gcd
from pathlib import Path
import subprocess
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'atlas'))
from catalogue_identity_v1 import normalize_spec,canonicalize
from corpus import manifest,SOURCE_HASH

class CorpusTests(unittest.TestCase):
    def load(self,path):return json.loads((HERE/path).read_text())
    def spec(self,pid,stem):return self.load(f'{pid}/{stem}-normalized-candidate.json')
    def fields(self,pid,stem):return {f['label']:f for f in self.spec(pid,stem)['matter']}

    def test_exact_fifty_ids_and_honest_statuses(self):
        ids={f'P{i:02d}' for i in range(1,51)}
        self.assertEqual(set(manifest()),ids)
        ledger=self.load('corpus-run-ledger.json')
        self.assertEqual({p['paper_id'] for p in ledger['papers']},ids)
        self.assertEqual(ledger['queued'],0)
        counts=Counter(p['status'] for p in ledger['papers'])
        self.assertEqual(dict(counts),ledger['counts'])
        self.assertEqual(sum(counts.values()),50)
        self.assertGreater(counts['partial_scoped_reextraction_staged'],0)
        self.assertEqual({p['paper_id'] for p in self.load('queue.json')['papers']},ids)

    def test_original_db_and_frozen_pilot_unchanged(self):
        self.assertEqual(sha256((ROOT/'atlas/atlas.sqlite').read_bytes()).hexdigest(),SOURCE_HASH)
        paths=[f'atlas/reextraction/P{i:02d}' for i in range(1,6)]+['atlas/reextraction/pilot.py','atlas/reextraction/run-ledger.json','atlas/reextraction/accepted.json','atlas/reextraction/README.md']
        result=subprocess.run(['git','diff','--exit-code','HEAD','--',*paths],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout)

    def test_pinned_download_hashes_and_attempts(self):
        for i in range(6,51):
            pid=f'P{i:02d}';r=self.load(f'{pid}/retrieval.json');c=self.load(f'{pid}/checkpoint.json')
            self.assertEqual(r['arxiv_version'],manifest()[pid]['arxiv_version'])
            pdf=ROOT/r['local_pdf']
            self.assertEqual(pdf.stat().st_size,r['bytes'])
            self.assertEqual(sha256(pdf.read_bytes()).hexdigest(),r['sha256'])
            self.assertEqual(c['source']['sha256'],r['sha256'])
            self.assertTrue(r['attempts'])
            self.assertTrue(all(a['returncode']==0 for a in r['attempts']))
            self.assertFalse(c['inspection']['whole_paper_scientifically_read'])
            self.assertTrue(c['inspection']['text_pages_with_claim_anchors'])

    def test_each_complete_candidate_is_normalized_and_preflight_consistent(self):
        for i in range(6,51):
            pid=f'P{i:02d}';c=self.load(f'{pid}/checkpoint.json')
            self.assertFalse(c['database_write_performed'])
            for item in c['preflight_results']:
                stem=item['stem'];spec=self.spec(pid,stem)
                self.assertTrue(spec['inventory_complete'])
                self.assertEqual(spec,normalize_spec(spec))
                fp=canonicalize(spec)['fingerprint']
                for suffix in ['preflight','require-normalized','duplicate-check']:
                    self.assertEqual(fp,self.load(f'{pid}/{stem}-{suffix}.json')['fingerprint'])
                for factor in spec['gauge_factors']:
                    if factor['family']=='U1':
                        qs=[Fraction(f['gauge_representations'][factor['id']]['charge']) for f in spec['matter']]
                        self.assertTrue(all(q.denominator==1 for q in qs))
                        nonzero=[abs(q.numerator) for q in qs if q]
                        if nonzero:self.assertEqual(reduce(gcd,nonzero),1)
                for f in spec['matter']:
                    if f['lorentz']['dimension']==4:self.assertNotIn(['0','1/2'],f['lorentz']['irreps'])

    def test_field_claims_and_legacy_ids_are_retained(self):
        public={e['id']:e for e in json.loads((ROOT/'website/field-catalogue.json').read_text())['entries']}
        for i in range(6,51):
            pid=f'P{i:02d}';c=self.load(f'{pid}/checkpoint.json');ev=self.load(f'{pid}/field-evidence.json');old=self.load(f'{pid}/legacy-records.json')
            claims={x['id'] for x in c['claims']}
            oldids={f['field_id'] for f in old['source_fields']}
            self.assertEqual(set(c['legacy_targets']['source_field_ids']),oldids)
            targets=set()
            for block in ev['candidates']:
                targets.add(block['target_existing_entry_id'])
                self.assertIn(block['target_existing_entry_id'],public)
                self.assertTrue({f['field_id'] for f in block['legacy_inventory_reference']}<=oldids)
                for row in block['fields']:
                    self.assertTrue(row['normalized_rows'])
                    self.assertTrue(set(row['claim_ids'])<=claims)
                    self.assertTrue(row['claim_ids'])
                    self.assertEqual(len(row['attribute_evidence_claim_ids']),6)
            for item in c['source_descriptions']:
                targets.update(item.get('target_entry_ids',[]))
                if 'target_entry_id' in item:targets.add(item['target_entry_id'])
            self.assertEqual({e['entry_id'] for e in old['public_entries']}-targets,set())

    def test_no_fabricated_model_cost(self):
        ledger=self.load('corpus-run-ledger.json')
        for key in ['tokens','api_dollars','gpu_hours']:self.assertIsNone(ledger[key])
        for i in range(6,51):
            m=self.load(f'P{i:02d}/checkpoint.json')['measurement']
            for key in ['input_tokens','cached_input_tokens','output_tokens','api_dollars','gpu_hours','scientific_extraction_active_seconds']:self.assertIsNone(m[key])

    def test_bl_whole_inventory_and_rh_conversion(self):
        fields=self.fields('P14','bl')
        self.assertEqual(fields['nu_R']['gauge_representations']['bl']['charge'],'3')
        self.assertEqual(fields['chi']['gauge_representations']['bl']['charge'],'6')
        self.assertEqual(fields['u^c']['gauge_representations']['colour']['dynkin'],[0,1])
        ev=self.load('P14/field-evidence.json')['candidates'][0]['fields']
        self.assertTrue(all('bl' in r['claim_ids'] for r in ev))

    def test_flavour_triplet_is_not_three_copies_and_all_factors_conjugate(self):
        f=self.fields('P31','flavour-u3')
        self.assertEqual(f['QL']['copies'],1)
        self.assertEqual(f['UR']['copies'],1)
        for factor in ['colour','flU']:self.assertEqual(f['UR']['gauge_representations'][factor]['dynkin'],[0,1])
        self.assertEqual(f['UR']['gauge_representations']['uRnumber']['charge'],'-1')
        self.assertEqual(f['UR']['gauge_representations']['hypercharge']['charge'],'-4')
        self.assertEqual(f['Psiu']['gauge_representations']['flU']['dynkin'],[1,0])

    def test_bulk_5d_is_not_blindly_conjugated_as_4d_rh(self):
        f=self.fields('P41','ued-5d')
        self.assertEqual(f['U']['lorentz'],{'dimension':5,'scheme':'B2_Dynkin','irreps':[[0,1]]})
        self.assertEqual(f['U']['gauge_representations']['colour']['dynkin'],[1,0])
        self.assertEqual(f['U']['gauge_representations']['hypercharge']['charge'],'4')
        self.assertEqual(f['H']['lorentz']['irreps'],[[0,0]])

    def test_composite_hc_does_not_add_elementary_higgs_or_composites(self):
        f=self.fields('P35','hypercolour')
        self.assertNotIn('H',f)
        self.assertEqual(f['psi_plus']['gauge_representations']['hypercolour']['dynkin'],[0,1,0])
        self.assertEqual(f['chi']['gauge_representations']['hypercolour']['dynkin'],[1,0,0])
        self.assertEqual(f['chitilde']['gauge_representations']['hypercolour']['dynkin'],[0,0,1])
        self.assertTrue(all(x['lorentz']['irreps']==[['1/2','0']] for x in f.values()))

    def test_fraternal_no_twin_hypercharge_or_three_extra_generations(self):
        spec=self.spec('P38','fraternal');f={x['label']:x for x in spec['matter']}
        self.assertEqual(sum(g['family']=='U1' for g in spec['gauge_factors']),1)
        self.assertEqual(f['Qhat']['copies'],1)
        self.assertEqual(f['that_R']['gauge_representations']['twin_colour']['dynkin'],[0,1])
        self.assertNotIn('twin_N_R',f)

    def test_dirac_is_pair_and_majorana_is_single_weyl(self):
        vlq=self.spec('P10','t-singlet')['matter']
        pair=[f for f in vlq if f['label']=='T']
        self.assertEqual(len(pair),2)
        self.assertEqual({f['gauge_representations']['hypercharge']['charge'] for f in pair},{'4','-4'})
        n=self.fields('P32','numsm')['N_R']
        self.assertEqual(n['copies'],3)
        self.assertEqual(n['lorentz']['irreps'],[['1/2','0']])

    def test_duplicate_reuse_and_no_automatic_novelty(self):
        self.assertEqual(self.load('P21/mssm-preflight.json')['fingerprint'],self.load('P22/rpv-preflight.json')['fingerprint'])
        for i in range(6,51):
            c=self.load(f'P{i:02d}/checkpoint.json')
            for result in c['preflight_results']:
                self.assertIn('existing',result['reconciliation_action'])
                if result['duplicate_check']['matches']:self.assertIn('do not add duplicate',result['reconciliation_action'])
                else:self.assertIn('not a novelty',result['reconciliation_action'])

if __name__=='__main__':unittest.main()
