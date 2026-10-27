"""Cleanup is terminal-only, durable and independent of the deleted payloads."""
from copy import deepcopy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bsm_atlas import harvest, expansion
from bsm_atlas.catalogue import exclusive_lock, write_json
from bsm_atlas.retention import cleanup_run, compact_record, compact_job


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'catalogue.json'
        write_json(self.source, {'schema_version':'bsm-atlas-1','papers':[],'entries':[]})
        self.manifest = self.root / 'papers.json'
        (self.root / 'text.txt').write_text('Full offline source. ' * 50)
        write_json(self.manifest, {'papers':[{'arxiv':'2501.00001v1','title':'Fixture','authors':'Author','text':'text.txt'}]})
        self.run = self.root / 'run'
        harvest.prepare_batch(self.manifest, self.run, source=self.source)
        self.job = self.run / 'jobs/2501.00001v1'

    def finish(self, outcome='skip'):
        result={'outcome':outcome,'reason':'Fixture outcome','entries':[]}
        write_json(self.job/'result.json',result)
        write_json(self.job/'status.json',{'state':'skipped' if outcome=='skip' else 'retry'})
        attempt=self.job/'attempt-0001';attempt.mkdir()
        write_json(attempt/'metrics.json',{'model':'fixture','elapsed_seconds':1,'usage':{'input_tokens':20,'output_tokens':2}})
        write_json(attempt/'result.json',result)
        (attempt/'events.jsonl').write_text('Full response duplicated here')
        return attempt

    def test_ingested_job_resumes_without_text_results_or_model_calls(self):
        attempt=self.finish()
        harvest.record_extractions(self.run,self.source,True)
        harvest.ingest_batch(self.run,self.source,True)
        before=self.source.read_bytes()
        preview=cleanup_run(self.run,source=self.source)
        self.assertGreater(preview['bytes_removed'],0)
        self.assertTrue((self.job/'paper.txt').exists())
        cleanup_run(self.run,source=self.source,write=True)
        for p in [self.job/'paper.txt',self.job/'prompt.txt',self.job/'result.json',attempt/'result.json',attempt/'events.jsonl']:
            self.assertFalse(p.exists())
        self.assertEqual(harvest.status(self.run)['counts'],{'ingested':1})
        self.assertTrue(harvest.inspect_result(self.run,self.job.name)['compacted'])
        self.assertEqual(harvest.status(self.run)['usage']['input_tokens'],20)
        self.assertEqual(cleanup_run(self.run,source=self.source,write=True)['files_removed'],0)
        with patch('bsm_atlas.harvest.run_job',side_effect=AssertionError('Repeated paper')):
            harvest.run_batch(self.run,execute=True)
        self.assertEqual(self.source.read_bytes(),before)
        write_json(self.run/'expansion.json',{'config':{
            'manifest_sha256':harvest.digest(str(self.manifest.resolve()).encode()+self.manifest.read_bytes()),
            'context_sha256':harvest.digest(harvest.context().encode()),'model':'gpt-6.1-sol',
            'workers':2,'reasoning':'medium','timeout':900,'fetch_size':5,'executable':'codex',
            'source':str(self.source.resolve())}})
        with patch('bsm_atlas.expansion.check_worker'),patch('bsm_atlas.expansion.run_job',side_effect=AssertionError('Repeated paper')),redirect_stdout(io.StringIO()):
            result=expansion.expand_batch(self.manifest,self.run,execute=True,resume=True,source=self.source)
        self.assertEqual(result['phase'],'extraction_complete')

    def test_running_and_unprocessed_inputs_are_never_removed(self):
        self.assertEqual(cleanup_run(self.run,source=self.source,write=True)['kept_jobs'],1)
        write_json(self.job/'status.json',{'state':'running'})
        self.assertEqual(cleanup_run(self.run,source=self.source,write=True,discard_uningested=True)['kept_jobs'],1)
        self.assertTrue((self.job/'prompt.txt').exists())

    def test_failure_progress_is_retained_without_retrying_or_losing_usage(self):
        self.finish('retry')
        harvest.record_extractions(self.run,self.source,True)
        cleanup_run(self.run,source=self.source,write=True)
        self.assertEqual(harvest.status(self.run)['counts'],{'retry':1})
        self.assertEqual(harvest.run_batch(self.run)['jobs'],[])
        with self.assertRaisesRegex(ValueError,'new run'):
            harvest.run_batch(self.run,retry=True)

    def test_no_uningested_results_are_lost_without_explicit_discard(self):
        self.finish()
        self.assertEqual(cleanup_run(self.run,source=self.source,write=True)['kept_jobs'],1)
        cleanup_run(self.run,source=self.source,write=True,discard_uningested=True)
        self.assertEqual(harvest.status(self.run)['counts'],{'discarded':1})
        self.assertEqual(harvest.run_batch(self.run)['jobs'],[])

    def test_marker_first_cleanup_recovers_partial_unlink(self):
        self.finish();harvest.ingest_batch(self.run,self.source,True)
        original=Path.unlink
        calls=[]
        def interrupted(path,*args,**kwargs):
            if path.name=='prompt.txt':raise OSError('Crash fixture')
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',interrupted),self.assertRaises(OSError):
            cleanup_run(self.run,source=self.source,write=True)
        self.assertIsNotNone(compact_record(self.job))
        self.assertEqual(harvest.status(self.run)['counts'],{'ingested':1})
        cleanup_run(self.run,source=self.source,write=True)
        self.assertFalse((self.job/'prompt.txt').exists())

    def test_tampered_response_receipt_and_symlink_are_rejected(self):
        self.finish();harvest.ingest_batch(self.run,self.source,True)
        original=(self.job/'result.json').read_bytes()
        write_json(self.job/'result.json',{'tampered':True})
        with self.assertRaisesRegex(ValueError,'changed'):
            cleanup_run(self.run,source=self.source,write=True)
        (self.job/'result.json').write_bytes(original)
        (self.job/'source.raw.txt').unlink()
        (self.job/'source.raw.txt').symlink_to(self.root/'text.txt')
        with self.assertRaisesRegex(ValueError,'symlink'):
            cleanup_run(self.run,source=self.source,write=True)
        self.assertTrue((self.root/'text.txt').exists())

    def test_cleanup_refuses_a_live_run_lock(self):
        with exclusive_lock(self.run/'run.lock'),self.assertRaises(ValueError):
            cleanup_run(self.run,source=self.source,write=True)

    def test_model_and_reference_survive_cleanup_byte_for_byte(self):
        spec=json.loads((Path(harvest.ROOT)/'atlas/examples/two-higgs-doublets.json').read_text())
        value={'outcome':'entries','reason':'Full source model fixture','entries':[
            {'id':'retention-fixture','name':'Fixture model','specification_json':json.dumps(spec),
             'locators':['Table 1']}]}
        write_json(self.job/'result.json',value)
        write_json(self.job/'status.json',{'state':'extracted'})
        harvest.ingest_batch(self.run,self.source,True)
        before=self.source.read_bytes()
        cleanup_run(self.run,source=self.source,write=True)
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(len(json.loads(before)['entries']),1)
        self.assertEqual(harvest.status(self.run)['jobs'][0]['entry_ids'],['retention-fixture'])

    def test_short_failure_diagnostic_survives_event_log_removal(self):
        attempt=self.finish('retry')
        (attempt/'events.jsonl').write_text(json.dumps({'type':'error','message':'Selected model is at capacity.'})+'\n')
        harvest.record_extractions(self.run,self.source,True)
        cleanup_run(self.run,source=self.source,write=True)
        self.assertEqual(harvest.status(self.run)['jobs'][0]['diagnostic'],'Selected model is at capacity.')
        self.assertFalse((attempt/'events.jsonl').exists())

    def test_compressed_metadata_cache_retains_identical_bytes_without_network(self):
        from bsm_atlas.citations import cached_response
        from unittest.mock import Mock
        client=Mock(); client.get.return_value=b'original metadata bytes '*1000
        url='https://inspirehep.net/api/literature?q=test'
        body=cached_response(self.root,'cache.json',url,client)
        client.get.reset_mock()
        self.assertEqual(cached_response(self.root,'cache.json',url,client),body)
        client.get.assert_not_called()
        self.assertLess((self.root/'cache.json').stat().st_size,len(body))


if __name__=='__main__':unittest.main()
