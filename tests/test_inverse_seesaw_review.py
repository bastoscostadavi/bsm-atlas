"""A curator's generation completion must preserve the dark sector and identity rules."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bsm_atlas.catalogue import identity
from bsm_atlas.matter_ordering import matter_dimension
from bsm_atlas.presentation import compact_baseline, matrix
from scripts.review_inverse_seesaw_generations import candidate, review, ENTRY, EXPECTED

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    spec = deepcopy(json.loads((ROOT / 'atlas/reference_spectra.json').read_text())['R_SM']['specification'])
    for row in spec['matter']:
        if row['lorentz']['irreps'] == [['1/2', '0']]:
            row['copies'] = 1
    singlet = deepcopy(spec['matter'][-1])
    singlet['gauge_representations']['weak_L']['dynkin'] = [0]
    singlet['gauge_representations']['hypercharge']['charge'] = '0'
    singlet['copies'] = 2
    fermion = deepcopy(singlet)
    fermion.update(copies=6, reality='none')
    fermion['lorentz']['irreps'] = [['1/2', '0']]
    spec['matter'].extend([fermion, singlet])
    entry = {'id': ENTRY, 'name': 'Cosmologically decaying dark matter with inverse seesaw',
             'specification': spec, 'references': [{'paper_id': 'source', 'locators': ['Sec. 3.2']}],
             'aliases': [{'id': 'one-generation-old', 'name': 'One-generation model'}]}
    data = {'schema_version': 'bsm-atlas-1', 'entries': [entry],
            'papers': [{'id': 'source', 'arxiv': '2509.19596v1', 'title': 'Source', 'authors': 'Authors'}]}
    links = {'papers': {'source': {'models': [{'entry_id': ENTRY, 'problems': [], 'mechanisms': []}],
                                  'model_fingerprints': {ENTRY: EXPECTED},
                                  'quality': {'needs_followup': False}}}}
    return data, links


class InverseSeesawReview(unittest.TestCase):
    def test_completion_displays_sm_and_preserves_singlet_sector(self):
        data, _ = fixture()
        original = data['entries'][0]
        before = deepcopy(original)
        self.assertEqual(identity(original['specification'])['fingerprint'], EXPECTED)
        updated = candidate(original)
        references = json.loads((ROOT / 'atlas/reference_spectra.json').read_text())
        templates = {key: matrix(value['specification']) for key, value in references.items()}
        regime = matrix(updated['specification'])
        compact_baseline(regime, templates)
        self.assertEqual(regime['baseline'], 'R_SM')
        self.assertEqual([(r['lorentz']['component'], r['copies']) for r in regime['additionalRows']],
                         [('F', 6), ('S', 2)])
        canonical = json.loads(identity(updated['specification'])['canonical_json'])
        self.assertEqual(matter_dimension(canonical), 210)
        self.assertEqual(original, before)
        self.assertNotIn('aliases', updated)

    def test_duplicate_completion_merges_and_retires_old_evidence(self):
        data, links = fixture()
        duplicate = candidate(data['entries'][0])
        duplicate.update(id='existing-complete-entry', name='Existing spectrum')
        data['entries'].append(duplicate)
        updated, annotations, report = review(data, links)
        self.assertEqual(len(updated['entries']), 1)
        self.assertEqual(report['changes'][ENTRY]['target'], 'existing-complete-entry')
        receipt = annotations['papers']['source']
        self.assertEqual(receipt['models'], [])
        self.assertNotIn(ENTRY, receipt['model_fingerprints'])
        self.assertEqual(receipt['detached_models'][0]['fingerprint'], EXPECTED)
        self.assertTrue(receipt['quality']['needs_followup'])
        self.assertIn('aliases', report['superseded_entries'][ENTRY])
        self.assertEqual(links['papers']['source']['model_fingerprints'][ENTRY], EXPECTED)

    def test_changed_spectrum_cannot_be_silently_repaired_again(self):
        data, links = fixture()
        data['entries'][0]['specification']['matter'][-1]['copies'] = 3
        with self.assertRaisesRegex(ValueError, 'Reviewed entry changed'):
            review(data, links)


if __name__ == '__main__':
    unittest.main()
