"""Regression checks for the source-reviewed November 2026 inventory repairs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bsm_atlas.catalogue import identity
from bsm_atlas.matter_ordering import matter_dimension
from scripts.review_leading_entries import repair, replacements
from scripts.review_front_page_followup import candidates as followup_candidates

ROOT = Path(__file__).resolve().parents[1]


class LeadingEntryReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads((ROOT / 'atlas/reviews/2026-11-09-leading-entries.json').read_text())

    def fixture(self):
        return {'schema_version': 'bsm-atlas-1',
                'entries': list(deepcopy(self.review['superseded_entries']).values()),
                'papers': deepcopy(self.review['superseded_papers'])}

    def test_complete_sm_inventory_and_source_hypercharges(self):
        expected = [('s1-scalar-leptoquark-8a79a78b7a94', 190, '2'),
                    ('r2-scalar-leptoquark-9eac3b95c500', 196, '7'),
                    ('s3-scalar-leptoquark', 202, '2'),
                    ('u1-vector-leptoquark', 208, '4'),
                    ('v2-vector-leptoquark', 232, '5')]
        sm = json.loads((ROOT / 'atlas/reference_spectra.json').read_text())['R_SM']['specification']
        candidates = replacements()
        for entry_id, dimension, charge in expected:
            with self.subTest(entry=entry_id):
                spec = candidates[entry_id]['specification']
                self.assertEqual(spec['matter'][:-1], sm['matter'])
                self.assertEqual(spec['matter'][-1]['gauge_representations']['hypercharge']['charge'], charge)
                self.assertEqual(matter_dimension(json.loads(identity(spec)['canonical_json'])), dimension)
        for entry_id in ['u1-vector-leptoquark', 'v2-vector-leptoquark']:
            self.assertEqual(candidates[entry_id]['specification']['matter'][-1]['reality'], 'complex')

    def test_horizontal_factor_and_family_multiplicities(self):
        spec = replacements()['u1h-noninvertible-pq']['specification']
        self.assertEqual(sum(a['family'] == 'U1' for a in spec['gauge_factors']), 2)
        quarks = [row for row in spec['matter'] if any(row['gauge_representations']['colour']['dynkin'])]
        self.assertEqual(sum(row['copies'] for row in quarks), 9)
        self.assertEqual(sorted((r['copies'], r['gauge_representations']['horizontal']['charge']) for r in quarks),
                         [(1, '-2'), (1, '2'), (1, '2'), (2, '-1'), (2, '-1'), (2, '1')])
        self.assertEqual(matter_dimension(json.loads(identity(spec)['canonical_json'])), 184)

    def test_followup_restores_colour_and_bminusl_conjugations(self):
        entries = followup_candidates()
        scalar = entries['scalar-leptoquarks-s1prime']['specification']
        self.assertEqual(identity(scalar), identity(replacements()['s1-scalar-leptoquark-8a79a78b7a94']['specification']))
        seesaw = entries['u1-bminusl-seesaw']['specification']
        self.assertEqual(matter_dimension(json.loads(identity(seesaw)['canonical_json'])), 198)
        self.assertTrue(any(f['family'] == 'A' and f['rank'] == 2 for f in seesaw['gauge_factors']))
        leptons = [row for row in seesaw['matter'] if row['lorentz']['irreps'] == [['1/2', '0']]
                   and row['gauge_representations']['colour']['dynkin'] == [0, 0]]
        self.assertEqual(sorted((r['gauge_representations']['I3R']['charge'],
                                 r['gauge_representations']['B_minus_L']['charge']) for r in leptons),
                         [('-1', '3'), ('0', '-3'), ('1', '3')])

    def test_reconciliation_preserves_old_leptoquark_url(self):
        data = self.fixture()
        existing = deepcopy(replacements()['s1-scalar-leptoquark-8a79a78b7a94'])
        existing['id'] = 'existing-complete-s1'
        data['entries'].append(existing)
        original = deepcopy(data)
        empty_links = {'schema_version': 'atlas-literature-links-1', 'papers': {}}
        updated, _, report = repair(data, empty_links)
        self.assertEqual(data, original)
        self.assertEqual(report['changes']['s1-scalar-leptoquark-8a79a78b7a94']['target'], existing['id'])
        target = next(e for e in updated['entries'] if e['id'] == existing['id'])
        self.assertIn('s1-scalar-leptoquark-8a79a78b7a94', [a['id'] for a in target['aliases']])
        self.assertEqual(len(updated['entries']), 6)
        self.assertNotIn('deflected-amsb-singlet-vectorlike-messengers', [e['id'] for e in updated['entries']])
        horizontal = next(e for e in updated['entries'] if e['id'] == 'u1h-noninvertible-pq')
        self.assertEqual([r['paper_id'] for r in horizontal['references']], ['arxiv-2402-12453v1'])
        self.assertFalse(horizontal.get('aliases'))

    def test_old_assessments_are_retained_for_review(self):
        data = self.fixture()
        receipt = {'entry_id': 'u1h-noninvertible-pq', 'problems': [], 'mechanisms': []}
        links = {'schema_version': 'atlas-literature-links-1', 'papers': {
            'arxiv-2402-12453v1': {'models': [receipt]}}}
        _, updated_links, report = repair(data, links)
        self.assertEqual(updated_links['papers']['arxiv-2402-12453v1']['models'], [])
        self.assertEqual(report['detached_literature']['arxiv-2402-12453v1'], [receipt])

    def test_changed_inventory_requires_a_new_review(self):
        data = self.fixture()
        data['entries'][0]['specification']['matter'][0]['copies'] += 1
        with self.assertRaisesRegex(ValueError, 'Reviewed entry changed'):
            repair(data, {'schema_version': 'atlas-literature-links-1', 'papers': {}})


if __name__ == '__main__':
    unittest.main()
