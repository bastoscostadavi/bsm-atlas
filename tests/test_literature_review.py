"""Publish Terra inventory corrections while preserving Luna's annotation layer."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from bsm_atlas.catalogue import ROOT, identity, normalize, write_json
from bsm_atlas.literature import bind_luna_receipt, path_for, preview


class LiteratureInventoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'catalogue.json'
        self.paper = {'id': 'luna-paper', 'arxiv': '2401.00001v1', 'title': 'Paper', 'authors': 'A'}
        self.other = {**self.paper, 'id': 'other-paper', 'arxiv': '2401.00002v1'}
        spec = normalize(json.loads((ROOT/'atlas/examples/two-higgs-doublets.json').read_text()))
        self.entry = {'id': 'original', 'name': 'Original model', 'specification': spec,
                      'references': [{'paper_id': self.paper['id']}]}
        self.model = {'entry_id': 'original', 'problems': [{'term_id': 'dark_matter',
            'rationale': 'Original Luna assessment', 'evidence': [{'quote': 'Original evidence', 'locator': 'Section 2'}],
            'reviewReasons': []}], 'mechanisms': []}
        self.receipt = {'arxiv': self.paper['arxiv'], 'extractor': {
            'provider': 'openai', 'model': 'gpt-6-luna', 'reasoning': 'medium'}, 'models': [self.model]}

    def test_only_exact_inventory_bindings_preserve_live_luna_evidence(self):
        renamed = {**deepcopy(self.entry), 'id': 'canonical-id'}
        stored = bind_luna_receipt(self.receipt, [self.entry], [renamed], self.paper)
        self.assertEqual(stored['extractor'], self.receipt['extractor'])
        self.assertEqual(stored['models'][0], {**self.model, 'entry_id': 'canonical-id'})
        changed = deepcopy(self.entry)
        changed['specification']['matter'][0]['copies'] += 1
        detached = bind_luna_receipt(self.receipt, [self.entry], [changed], self.paper)
        self.assertEqual(detached['models'], [])
        self.assertEqual(detached['detached_models'], [{'model': self.model,
            'fingerprint': identity(self.entry['specification'])['fingerprint']}])
        restored = bind_luna_receipt(detached, [], [renamed], self.paper)
        self.assertEqual(restored['models'], stored['models'])
        self.assertEqual(restored['detached_models'], [])

    def test_withdrawn_paper_links_do_not_leak_into_published_shared_entry(self):
        shared = {**deepcopy(self.entry), 'references': [{'paper_id': self.other['id']}]}
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [self.paper, self.other], 'entries': [shared]})
        retained = bind_luna_receipt(self.receipt, [self.entry], [shared], self.paper)
        write_json(path_for(self.source), {'schema_version': 'atlas-literature-links-1',
            'papers': {self.paper['id']: retained}})
        baseline = self.root/'baseline.json'
        write_json(baseline, {'schema_version': 'atlas-literature-baseline-1',
            'entry_fingerprints': {'original': identity(self.entry['specification'])['fingerprint']},
            'problems': {'problems': [{'id': 'dark_matter'}], 'assessed': ['original'],
                'links': {'original': {'dark_matter': [{'paperId': self.paper['id']}, {'paperId': self.other['id']}]}}}})
        published = preview('problems', self.source, baseline)
        self.assertEqual(published['links']['original']['dark_matter'], [{'paperId': self.other['id']}])
        self.assertEqual(retained['detached_models'][0]['model'], self.model)
        # Missing references outside an intentional inventory review still fail.
        write_json(path_for(self.source), {'schema_version': 'atlas-literature-links-1', 'papers': {}})
        with self.assertRaisesRegex(ValueError, 'paper reference'):
            preview('problems', self.source, baseline)

    def test_terra_annotations_cannot_be_relabelled_as_luna(self):
        receipt = deepcopy(self.receipt)
        receipt['extractor']['model'] = 'gpt-6.1-terra'
        with self.assertRaisesRegex(ValueError, 'original Luna'):
            bind_luna_receipt(receipt, [self.entry], [self.entry], self.paper)


if __name__ == '__main__':
    unittest.main()
