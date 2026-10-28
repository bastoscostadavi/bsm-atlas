"""Reservations exclude both database papers and papers assigned to other providers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bsm_atlas import allocations, relevance
from bsm_atlas.catalogue import write_json
from tests.test_relevance import metadata_client, arxiv_client, hit


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'catalogue.json'
        write_json(self.source,{'schema_version':'bsm-atlas-1','papers':[], 'entries':[]})
        self.records=[hit('2401.00001',30,1),hit('2401.00002',20,2),
                      hit('2501.00001',10,3),hit('2501.00002',5,4)]

    def offline(self, directory, count, **kwargs):
        return self.real_select(directory,count,**{**kwargs,'client':metadata_client(self.records),
            'arxiv_client':arxiv_client(),'first_year':2024,'last_year':2025,'page_size':2,'batch_size':2})

    def test_disjoint_batches_and_idempotent_resume(self):
        existing=self.root/'sol.json'
        write_json(existing,{'papers':[{'arxiv':'2401.00001v1'}]})
        allocations.register_manifest(existing,'codex',self.source)
        self.real_select=relevance.select_population
        with patch.object(relevance,'select_population',side_effect=self.offline) as select:
            first=allocations.reserve_batch(self.root/'claude',2,source=self.source)
            second=allocations.reserve_batch(self.root/'next',1,provider='codex',source=self.source)
            repeated=allocations.reserve_batch(self.root/'claude',2,source=self.source)
        self.assertEqual(select.call_count,2)
        a=json.loads(Path(first['manifest']).read_text())['papers']
        b=json.loads(Path(second['manifest']).read_text())['papers']
        self.assertEqual([p['arxiv'] for p in a],['2401.00002v2','2501.00001v2'])
        self.assertEqual([p['arxiv'] for p in b],['2501.00002v2'])
        self.assertTrue(repeated['reused'])
        self.assertFalse((self.root/'claude/selection-input.json').exists())
        self.assertEqual(json.loads(self.source.read_text())['papers'],[])

    def test_overlapping_and_mutated_manifests_are_rejected(self):
        first,second=self.root/'a.json',self.root/'b.json'
        write_json(first,{'papers':[{'arxiv':'2401.00001v1'}]})
        write_json(second,{'papers':[{'arxiv':'2401.00001v2'}]})
        allocations.register_manifest(first,'codex',self.source)
        with self.assertRaisesRegex(ValueError,'already reserved'):
            allocations.register_manifest(second,'claude',self.source)
        write_json(first,{'papers':[{'arxiv':'2401.00002v1'}]})
        with self.assertRaisesRegex(ValueError,'changed'):
            allocations.register_manifest(first,'codex',self.source)

    def test_duplicate_versions_cannot_count_as_two_reserved_papers(self):
        p=self.root/'duplicates.json'
        write_json(p,{'papers':[{'arxiv':'2401.00001v1'},{'arxiv':'2401.00001v2'}]})
        with self.assertRaisesRegex(ValueError,'different versions'):
            allocations.register_manifest(p,'claude',self.source)
