"""Staging/regression checks, not an independent source-physics review."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'atlas'))
from catalogue_identity_v1 import canonicalize, normalize_spec

class PilotTests(unittest.TestCase):
    def load(self, path):
        return json.loads((HERE / path).read_text())

    def test_source_immutable(self):
        self.assertEqual(sha256((ROOT / 'atlas/atlas.sqlite').read_bytes()).hexdigest(),
                         'd4dbf023b667fe810296c43c8f72e0d0b3f6559e66b344a2920c9e2e520e6c4c')

    def test_manifest_has_fifty_and_pilot_ledger_has_five(self):
        paper_ids = re.findall(r'^\| (P\d\d) \|', (ROOT/'BSM_ATLAS_SEED.md').read_text(), re.M)
        self.assertEqual(len(paper_ids), 50)
        self.assertEqual(set(paper_ids), {f'P{i:02d}' for i in range(1,51)})
        pilot = self.load('run-ledger.json')['papers']
        self.assertEqual({p['paper_id'] for p in pilot}, {'P01','P02','P03','P04','P05'})

    def test_staged_payloads_normalized_and_outputs_consistent(self):
        for pid in ['P01','P02','P03','P04','P05']:
            checkpoint = self.load(f'{pid}/checkpoint.json')
            self.assertFalse(checkpoint['database_write_performed'])
            self.assertFalse(checkpoint['source']['whole_paper_scientifically_read'])
            self.assertIsNone(checkpoint['measurement']['api_dollars'])
            for name in checkpoint['staged_numerical_candidates']:
                spec = self.load(f'{pid}/{name}')
                self.assertEqual(spec, normalize_spec(spec))
                stem = name.replace('-normalized-candidate.json','')
                fp = canonicalize(spec)['fingerprint']
                self.assertEqual(fp, self.load(f'{pid}/{stem}-preflight.json')['fingerprint'])
                self.assertEqual(fp, self.load(f'{pid}/{stem}-require-normalized.json')['fingerprint'])
                self.assertEqual(fp, self.load(f'{pid}/{stem}-duplicate-check.json')['fingerprint'])

    def test_lr_joint_normalization_and_full_conjugation(self):
        raw = self.load('P04/lr-source-candidate.json')
        normalized = self.load('P04/lr-normalized-candidate.json')
        fields = {f['label']: f for f in normalized['matter']}
        self.assertEqual(len(raw['gauge_factors']), 4)
        self.assertEqual(fields['Q_R^c']['gauge_representations']['colour']['dynkin'], [0,1])
        self.assertEqual(fields['Q_R^c']['gauge_representations']['bl']['charge'], '-1')
        self.assertEqual(fields['l_R^c']['gauge_representations']['bl']['charge'], '3')
        for label in ['Delta_L','Delta_R']:
            self.assertEqual(fields[label]['gauge_representations']['bl']['charge'], '6')
        for label in ['Q_L','Q_R^c','l_L','l_R^c']:
            self.assertEqual(fields[label]['copies'], 3)
        preflight = self.load('P04/lr-preflight.json')
        self.assertEqual(preflight['transformations'][0]['positive_source_scale'], '3')
        self.assertEqual(preflight['duplicate_check']['status'], 'no_exact_match_review_required')
        self.assertEqual(self.load('P04/checkpoint.json')['legacy_targets']['entry_id'], 'lr-triplet-matter')

    def test_p01_p02_reuse_one_content(self):
        first = self.load('P01/singlet-duplicate-check.json')
        second = self.load('P02/singlet-duplicate-check.json')
        self.assertEqual(first['fingerprint'], second['fingerprint'])
        self.assertEqual(first['matches'][0]['entry_id'], 'real-singlet-z2')
        for pid,stem,entry in [('P02','complex-singlet','complex-singlet-portal'),
                               ('P03','thdm','two-higgs-doublets'),('P05','nmssm','nmssm-matter')]:
            self.assertEqual(self.load(f'{pid}/{stem}-duplicate-check.json')['matches'][0]['entry_id'], entry)

    def test_historical_scalar_equivalence_receipt_is_preserved(self):
        primary = self.load('P02/complex-singlet-normalized-candidate.json')
        alternate = self.load('P02/complex-two-real-description.json')
        eq = self.load('P02/scalar-equivalence.json')
        self.assertEqual(primary['matter'][-1]['reality'], 'complex')
        self.assertEqual(alternate['matter'][-1]['reality'], 'real')
        self.assertEqual(alternate['matter'][-1]['copies'], 2)
        self.assertNotEqual(canonicalize(primary)['fingerprint'], canonicalize(alternate)['fingerprint'])
        self.assertFalse(eq['fingerprints_currently_equal'])

    def test_every_staged_field_has_attribute_evidence(self):
        for pid in ['P01','P02','P03','P04','P05']:
            checkpoint = self.load(f'{pid}/checkpoint.json')
            evidence = self.load(f'{pid}/field-evidence.json')
            claims = {c['id'] for c in checkpoint['claims']}
            expected_count = sum(len(self.load(f'{pid}/{name}')['matter']) for name in checkpoint['staged_numerical_candidates'])
            self.assertEqual(len(evidence['rows']), expected_count)
            for row in evidence['rows']:
                for attribute in ['gauge_algebra','nonabelian_irreps','source_charge','copies','lorentz_and_reality','conversion']:
                    refs = row['attribute_evidence_claim_ids'][attribute]
                    self.assertTrue(refs)
                    self.assertTrue(set(refs) <= claims)

if __name__ == '__main__':
    unittest.main()
