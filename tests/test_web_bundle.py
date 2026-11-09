"""Static shards preserve exact records and keep metadata out of the bootstrap."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from bsm_atlas.web_bundle import Bundle, SHARD_BYTES, pages, tokens, paper_order


class WebBundleTests(unittest.TestCase):
    def test_partition_is_lossless_content_addressed_and_byte_bounded(self):
        records = {f'record-{i}': {'value': str(i) * 100} for i in range(2000)}
        builder = Bundle(); routes = builder.shards(records); recovered = {}
        self.assertGreater(len(routes), 1)
        for path in routes.values():
            raw = builder.files[path]
            self.assertLessEqual(len(raw), SHARD_BYTES)
            self.assertEqual(path, 'data/blobs/' + sha256(raw).hexdigest() + '.json')
            for key, value in json.loads(raw).items():
                self.assertNotIn(key, recovered); recovered[key] = value
        self.assertEqual(recovered, records)
        again = Bundle(); self.assertEqual(again.shards(records), routes)

    def test_evidence_pages_bound_rows_and_bytes_without_losing_quotes(self):
        rows = [{'paperId': str(i), 'quote': 'x' * 3000} for i in range(53)]
        grouped = pages(rows)
        self.assertEqual([row for group in grouped for row in group], rows)
        self.assertTrue(all(len(group) <= 20 for group in grouped))
        self.assertTrue(all(len(json.dumps(group)) < 33 * 1024 for group in grouped))

    def test_search_normalization_and_paper_chronology(self):
        self.assertEqual(tokens('Néutrino SU(3) MÜLLER z1**2'), {'neutrino', 'su', '3', 'muller', 'z1', '2'})
        papers = [{'arxiv': value} for value in ['2101.10000v2', 'hep-ph/9901001v1', '2101.00001v1']]
        self.assertEqual([p['arxiv'] for p in sorted(papers, key=paper_order)],
                         ['hep-ph/9901001v1', '2101.00001v1', '2101.10000v2'])
