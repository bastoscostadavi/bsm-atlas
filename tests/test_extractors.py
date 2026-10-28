"""Extractor attribution is small, factual and does not change model identity."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from bsm_atlas import harvest
from bsm_atlas.build import database,main_data
from bsm_atlas.catalogue import load,validate,write_json
from bsm_atlas.extractors import job_extractor,sync_extractors
from bsm_atlas.retention import cleanup_run
from tests.test_harvest import BODY


class ExtractorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'catalogue.json'
        write_json(self.source,{'schema_version':'bsm-atlas-1','papers':[],'entries':[]})
        (self.root/'paper.txt').write_text(BODY)
        self.manifest=self.root/'papers.json';self.run=self.root/'run'
        write_json(self.manifest,{'papers':[{'arxiv':'2501.00001v1','title':'Paper','authors':'Author','text':'paper.txt'}]})
        harvest.prepare_batch(self.manifest,self.run,source=self.source)
        self.job=self.run/'jobs/2501.00001v1'
        attempt=self.job/'attempt-0001';attempt.mkdir()
        write_json(attempt/'metrics.json',{'model':'gpt-6.1-sol','reasoning':'medium',
            'usage':{'input_tokens':1,'output_tokens':1},'elapsed_seconds':1})
        write_json(self.job/'status.json',{'state':'skipped'})
        write_json(self.job/'result.json',{'outcome':'skip','reason':'No complete model','entries':[]})

    def test_provenance_backfill_uses_receipts_and_preserves_source_identity(self):
        harvest.ingest_batch(self.run,self.source,True)
        cleanup_run(self.run,source=self.source,write=True)
        data=load(self.source);data['papers'][0].pop('extractor')
        write_json(self.source,data)
        report=sync_extractors(self.root,self.source)
        self.assertEqual(report['backfilled'],1)
        self.assertNotIn('extractor',load(self.source)['papers'][0])
        sync_extractors(self.root,self.source,True)
        expected={'provider':'openai','model':'gpt-6.1-sol','reasoning':'medium'}
        self.assertEqual(load(self.source)['papers'][0]['extractor'],expected)
        self.assertEqual(sync_extractors(self.root,self.source,True)['backfilled'],0)

    def test_unknown_or_unmeasured_model_is_not_guessed(self):
        p=self.job/'attempt-0001/metrics.json'
        write_json(p,{'model':'gpt-6.1-sol','usage':None})
        self.assertIsNone(job_extractor(self.job))
        write_json(p,{'model':'fixture','usage':{'input_tokens':1}})
        self.assertIsNone(job_extractor(self.job))

    def test_database_exports_attribution_and_validates_it(self):
        harvest.ingest_batch(self.run,self.source,True)
        data=load(self.source)
        path=self.root/'export.sqlite';database(path,main_data(data))
        with closing(sqlite3.connect(path)) as con:
            self.assertEqual(con.execute('SELECT extractor_provider,extractor_model,extractor_reasoning FROM papers').fetchone(),
                ('openai','gpt-6.1-sol','medium'))
        for value in [{}, {'provider':'unknown','model':'x','reasoning':'medium'},
                      {'provider':'openai','model':'','reasoning':'medium'},
                      {'provider':'openai','model':'gpt-6.1-sol','reasoning':'arbitrary'}]:
            altered=deepcopy(data);altered['papers'][0]['extractor']=value
            with self.assertRaises(ValueError):validate(altered)
