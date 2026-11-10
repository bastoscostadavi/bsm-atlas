"""Unverified Luna inventories stay local; completed Terra corrections publish."""
from copy import deepcopy
import json
import unittest

from bsm_atlas.catalogue import ROOT, identity, normalize, validate
from bsm_atlas.publication_filter import reviewed_luna_snapshot


class PublicationFilterTests(unittest.TestCase):
    def setUp(self):
        self.luna = {'id': 'luna', 'arxiv': '2401.00001v1', 'title': 'Paper', 'authors': 'A',
                     'extractor': {'provider': 'openai', 'model': 'gpt-6-luna', 'reasoning': 'medium'}}
        self.other = {**self.luna, 'id': 'other', 'arxiv': '2401.00002v1',
                      'extractor': {'provider': 'openai', 'model': 'gpt-6.1-sol', 'reasoning': 'medium'}}
        spec = normalize(json.loads((ROOT/'atlas/examples/two-higgs-doublets.json').read_text()))
        self.entry = {'id': 'model', 'name': 'Model', 'specification': spec, 'references': [{'paper_id': 'luna'}]}
        self.data = {'schema_version': 'bsm-atlas-1', 'papers': [self.luna, self.other], 'entries': [self.entry]}
        self.links = {'schema_version': 'atlas-literature-links-1', 'papers': {'luna': {
            'arxiv': self.luna['arxiv'], 'extractor': self.luna['extractor'], 'models': [
                {'entry_id': 'model', 'problems': [{'term_id': 'dark_matter', 'rationale': 'Luna claim',
                 'evidence': [], 'reviewReasons': []}], 'mechanisms': []}]}}}
        self.registry = {'schema_version': 'luna-terra-entry-review-1', 'papers': {}}

    def record(self, fingerprints, **changes):
        return {'paper': self.luna, 'model': 'gpt-6.1-terra', 'state': 'agreement', 'applied': True,
                'checked': False, 'terra': {'fingerprints': fingerprints}, **changes}

    def test_unreviewed_and_unresolved_luna_inventories_are_not_published(self):
        for records in ({}, {'luna': self.record([], state='unresolved', applied=False)}):
            registry = {**self.registry, 'papers': records}
            original = deepcopy((self.data, self.links, registry))
            data, links, report = reviewed_luna_snapshot(self.data, self.links, registry)
            self.assertEqual(data['entries'], [])
            self.assertEqual(data['papers'], self.data['papers'])
            self.assertEqual(report['removed_luna_only_entry_ids'], ['model'])
            self.assertEqual(links['papers']['luna']['models'], [])
            self.assertEqual(links['papers']['luna']['detached_models'][0]['model'], self.links['papers']['luna']['models'][0])
            self.assertEqual((self.data, self.links, registry), original)

    def test_completed_terra_agreement_qualifies_without_checked_quality_flag(self):
        fingerprint = identity(self.entry['specification'])['fingerprint']
        self.registry['papers']['luna'] = self.record([fingerprint])
        data, links, report = reviewed_luna_snapshot(self.data, self.links, self.registry)
        self.assertEqual(data, self.data)
        self.assertEqual(links, self.links)
        self.assertEqual(report['retained_terra_reviewed_entries'], 1)
        validate(data)

    def test_disagreement_publishes_exact_terra_specification_and_preserves_luna_layer(self):
        corrected = deepcopy(self.entry)
        corrected['id'] = 'corrected'
        corrected['specification']['matter'][0]['copies'] += 1
        self.data['entries'].append(corrected)
        fingerprint = identity(corrected['specification'])['fingerprint']
        self.registry['papers']['luna'] = self.record([fingerprint], state='disagreement')
        data, links, report = reviewed_luna_snapshot(self.data, self.links, self.registry)
        self.assertEqual(data['entries'], [corrected])
        self.assertEqual(report['retained_terra_reviewed_entries'], 1)
        self.assertEqual(links['papers']['luna']['extractor']['model'], 'gpt-6-luna')
        self.assertEqual(links['papers']['luna']['detached_models'][0]['model'], self.links['papers']['luna']['models'][0])
        validate(data)

    def test_independent_support_survives_unverified_luna_reference_removal(self):
        self.entry['references'].append({'paper_id': 'other'})
        data, _, report = reviewed_luna_snapshot(self.data, self.links, self.registry)
        self.assertEqual(data['entries'][0]['references'], [{'paper_id': 'other'}])
        self.assertEqual(report['retained_other_supported_entries'], 1)
        validate(data)

    def test_current_terra_provenance_still_requires_matching_review_inventory(self):
        self.luna['extractor'] = {**self.luna['extractor'], 'model': 'gpt-6.1-terra'}
        self.registry['papers']['luna'] = self.record(['different-fingerprint'])
        data, _, _ = reviewed_luna_snapshot(self.data, self.links, self.registry)
        self.assertEqual(data['entries'], [])

    def test_a_different_paper_version_is_not_certified(self):
        fingerprint = identity(self.entry['specification'])['fingerprint']
        self.registry['papers']['luna'] = self.record([fingerprint], paper={**self.luna, 'arxiv': '2401.00001v2'})
        data, _, _ = reviewed_luna_snapshot(self.data, self.links, self.registry)
        self.assertEqual(data['entries'], [])

    def test_missing_review_registry_cannot_be_used_as_publication_approval(self):
        with self.assertRaises(ValueError):
            reviewed_luna_snapshot(self.data, self.links, {})


if __name__ == '__main__':
    unittest.main()
