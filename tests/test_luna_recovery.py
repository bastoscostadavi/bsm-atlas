"""Offline recovery checks; no network or model calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bsm_atlas import luna_recovery as recovery, luna_slots as slots
from bsm_atlas.catalogue import write_json


PAPER = {'id':'test-paper', 'arxiv':'2401.00001v1', 'title':'Paper', 'authors':'Author'}


class SlotTests(unittest.TestCase):
    def test_shared_budget_cannot_be_exceeded_and_releases(self):
        with tempfile.TemporaryDirectory() as d:
            held = [slots.take(d) for _ in range(16)]
            try:
                self.assertTrue(all(held))
                self.assertIsNone(slots.take(d))
                slots.release(held.pop())
                replacement = slots.take(d)
                self.assertIsNotNone(replacement)
                slots.release(replacement)
            finally:
                for handle in held: slots.release(handle)

    def test_first_pass_context_releases_on_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                with slots.first_pass_slot(d): raise RuntimeError('test')
            handles = [slots.take(d) for _ in range(16)]
            self.assertTrue(all(handles))
            for handle in handles: slots.release(handle)


class PriorityTests(unittest.TestCase):
    def test_missing_first_pass_status_waits_without_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            allowed, reason = recovery.permission(Path(d))
            self.assertFalse(allowed)
            self.assertIn('status unavailable', reason)

    def test_priority_and_provider_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for status, expected in [
                ({'phase':'running','pipeline':{'active_workers':1}},True),
                ({'phase':'running','pipeline':{'active_workers':14}},False),
                ({'phase':'running','producer':{'ready_buffer':1}},False),
                ({'phase':'running','pipeline':{'active_workers':0}},True),
                ({'phase':'blocked','reason':'429 Too Many Requests'},False),
                ({'phase':'blocked','reason':'unrecognized failure'},False)]:
                self.assertEqual(recovery.permission(root,current=status)[0],expected)
            self.assertTrue(recovery.permission(root,probe=True,current={'phase':'blocked','reason':'429'})[0])
            (root/'STOP').touch()
            self.assertFalse(recovery.permission(root,probe=True,current={'reason':'429'})[0])


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.run = self.root/'recovery'
        self.source = self.root/'catalogue.json'; self.first = self.root/'first'; self.first.mkdir()
        self.corpus = self.root/'corpus'; self.harvest = self.root/'harvest'; self.harvest.mkdir()
        write_json(self.source,{'papers':[{**PAPER,'extraction_status':'unresolved'}]})
        write_json(self.first/'status.json',{'phase':'blocked','reason':'429 Too Many Requests'})

    def prepare(self):
        with patch.object(recovery,'read_index',return_value=[{'arxiv':'2401.00001','categories':['hep-ph']}]),patch.object(recovery,'read_source',return_value=('source',{'text_sha256':'abc'})):
            return recovery.prepare(self.run,self.source,self.corpus,self.harvest)

    def test_selection_keeps_only_unresolved_readable_primary_papers(self):
        second={**PAPER,'id':'second','arxiv':'2401.00002v1','extraction_status':'complete'}
        third={**PAPER,'id':'third','arxiv':'2401.00003v1','extraction_status':'unresolved'}
        write_json(self.source,{'papers':[{**PAPER,'extraction_status':'unresolved'},second,third]})
        summary=self.prepare()
        self.assertEqual(summary['ready_for_one_retry'],1)
        self.assertEqual(summary['deferred'],{'not_primary_hep_ph':1})
        saved=(self.run/'manifest.json').read_bytes()
        self.prepare();self.assertEqual((self.run/'manifest.json').read_bytes(),saved)

    def test_source_only_selection_excludes_all_historical_model_attempts(self):
        papers=[{**PAPER,'arxiv':f'2401.{i:05d}v1','id':f'p{i}','extraction_status':'unresolved'} for i in range(1,5)]
        write_json(self.source,{'papers':papers})
        for i in (1,2,3):
            job=self.harvest/'first'/'jobs'/f'2401.{i:05d}v1';job.mkdir(parents=True)
            write_json(job/'state.json',{'state':'source_unavailable','paper':papers[i-1],'reason':'Unsupported TeX'})
        old=self.harvest/'old'/'jobs'/'2401.00002v2';old.mkdir(parents=True)
        write_json(old/'state.json',{'state':'invalid','paper':{**papers[1],'arxiv':'2401.00002v2'}})
        write_json(old/'metrics.json',{'model':'gpt-6-luna','usage':None})
        write_json(self.harvest/'first'/'jobs'/'2401.00003v1'/'metrics.json',{'usage':None})
        with patch.object(recovery,'read_index',return_value=[{'arxiv':f'2401.{i:05d}','categories':['hep-ph']} for i in range(1,5)]),patch.object(recovery,'read_source',return_value=('source',{'text_sha256':'abc'})) as reader:
            summary=recovery.prepare(self.run,self.source,self.corpus,self.harvest,source_only=True,workers=16)
        self.assertEqual(summary['selection_scope'],'blocked_before_extraction')
        self.assertEqual(summary['ready_for_one_retry'],1)
        self.assertEqual(summary['workers'],16)
        self.assertEqual(reader.call_count,1)
        self.assertEqual(summary['deferred']['prior_model_attempt'],2)
        self.assertEqual(summary['deferred']['no_pre_extraction_block_receipt'],1)
        saved=recovery.read(self.run/'manifest.json')['papers']
        self.assertEqual(saved[0]['paper']['arxiv'],PAPER['arxiv'])
        self.assertTrue(saved[0]['baseline']['sha256'])

    def test_new_profile_only_considers_candidate_subset_and_excludes_reservations(self):
        second={**PAPER,'id':'second','arxiv':'2401.00002v1','extraction_status':'unresolved'}
        third={**PAPER,'id':'third','arxiv':'2401.00003v1','extraction_status':'unresolved'}
        write_json(self.source,{'papers':[{**PAPER,'extraction_status':'unresolved'},second,third]})
        for paper in (PAPER,second,third):
            job=self.harvest/'first'/'jobs'/recovery.job_id(paper['arxiv']);job.mkdir(parents=True)
            write_json(job/'state.json',{'state':'source_unavailable','paper':paper,'reason':'Unsupported TeX'})
        candidates=self.root/'candidates.json';write_json(candidates,{'papers':[PAPER,second]})
        reservation=self.root/'reserved.json';write_json(reservation,{'papers':[{'paper':second}]})
        with patch.object(recovery,'read_index',return_value=[{'arxiv':f'2401.{i:05d}','categories':['hep-ph']} for i in range(1,4)]),patch.object(recovery,'read_source',return_value=('source',{'text_sha256':'abc'})) as reader:
            selection=recovery.prepare(self.run,self.source,self.corpus,self.harvest,source_only=True,workers=4,preparation_profile='tex-v3',candidates_from=candidates,exclude_manifests=[reservation])
        self.assertEqual(selection['ready_for_one_retry'],1)
        self.assertEqual(selection['reserved_base_ids_excluded'],1)
        self.assertEqual(selection['source_preparation_profile'],'tex-v3')
        self.assertEqual(selection['workers'],4)
        self.assertEqual(reader.call_count,1)
        self.assertIn('preparer',reader.call_args.kwargs)
        self.assertEqual(recovery.read(self.run/'manifest.json')['papers'][0]['paper']['arxiv'],PAPER['arxiv'])

    def test_nested_legacy_metrics_are_prior_attempts_even_without_usage(self):
        job=self.harvest/'legacy'/'jobs'/'2401.00001v1'
        (job/'attempt-001').mkdir(parents=True)
        write_json(job/'attempt-001'/'metrics.json',{'usage':None})
        self.assertTrue(recovery.prior_model_attempt(job,{'state':'source_unavailable'}))

    def test_completed_first_pass_ignores_stale_producer_buffer(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(recovery.permission(Path(d),current={'phase':'completed','producer':{'ready_buffer':7}})[0])
            (Path(d)/'STOP').touch()
            self.assertFalse(recovery.permission(Path(d),current={'phase':'completed'})[0])

    def test_unusable_source_is_deferred_without_model_call(self):
        with patch.object(recovery,'read_index',return_value=[{'arxiv':'2401.00001','categories':['hep-ph']}]),patch.object(recovery,'read_source',side_effect=ValueError('Missing TeX dependency in main.tex: foo')),patch.object(recovery.joint,'run_worker') as worker:
            summary=recovery.prepare(self.run,self.source,self.corpus,self.harvest)
            self.assertEqual(summary['ready_for_one_retry'],0)
            worker.assert_not_called()

    def fake_intake(self, directory, rows, source):
        for row in rows:
            job=directory/'jobs'/'2401.00001v1'
            state={**row,'state':'ingested' if row['state']=='ready' else row['state']}
            write_json(job/'state.json',state)
            recovery.joint.compact(job)
            (job/'intake.json').unlink(missing_ok=True)
            if row['state']=='ready':
                data=recovery.read(source);data['papers'][0]['extraction_status']='complete';write_json(source,data)

    def execute(self,row):
        with patch.object(recovery.joint,'check_worker'),patch.object(recovery.joint,'context',return_value='exact unchanged context'),patch.object(recovery.joint,'taxonomies',return_value={}),patch.object(recovery.joint,'response_schema',return_value={}),patch.object(recovery,'read_source',return_value=('exact verified paper',{})),patch.object(recovery.joint,'run_worker',return_value=row) as worker,patch.object(recovery.joint,'intake',side_effect=self.fake_intake),patch.object(recovery,'take',side_effect=lambda:slots.take(self.root/'slots')):
            result=recovery.run(self.run,execute=True,probe=True,source=self.source,corpus=self.corpus,first=self.first)
            return result,worker

    def test_successful_probe_is_ingested_and_never_repeated(self):
        self.prepare()
        row={'state':'ready','paper':PAPER,'outcome':'skip','entries':[],'annotations':[],'infrastructure':False}
        result,worker=self.execute(row)
        self.assertEqual(result['phase'],'probe_completed');self.assertEqual(worker.call_count,1)
        self.assertEqual(worker.call_args.args[2],'exact verified paper')
        self.assertEqual(worker.call_args.args[4],'exact unchanged context')
        self.assertEqual(recovery.read(self.source)['papers'][0]['extraction_status'],'complete')
        _,worker=self.execute(row);worker.assert_not_called()

    def test_rate_limit_stops_without_automatic_paid_retry(self):
        self.prepare()
        row={'state':'retry','paper':PAPER,'reason':'Worker exited 1: 429 Too Many Requests','infrastructure':True}
        result,worker=self.execute(row)
        self.assertEqual(result['phase'],'blocked');self.assertEqual(worker.call_count,1)
        self.assertEqual(recovery.read(self.source)['papers'][0]['extraction_status'],'unresolved')
        _,worker=self.execute(row);worker.assert_not_called()

    def test_completed_group_is_journaled_then_ingested_once(self):
        from concurrent.futures import Future
        second={**PAPER,'id':'second','arxiv':'2401.00002v1'}
        write_json(self.source,{'papers':[{**p,'extraction_status':'unresolved'} for p in (PAPER,second)]})
        with patch.object(recovery,'read_index',return_value=[{'arxiv':'2401.00001','categories':['hep-ph']},{'arxiv':'2401.00002','categories':['hep-ph']}]),patch.object(recovery,'read_source',return_value=('source',{})):
            recovery.prepare(self.run,self.source,self.corpus,self.harvest)
        write_json(self.first/'status.json',{'phase':'completed'})
        class ImmediatePool:
            def __init__(self,**kwargs): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def submit(self,fn,*args):
                f=Future();f.set_result(fn(*args));return f
        def result(job,paper,*args):
            return {'state':'ready','paper':paper,'outcome':'skip','entries':[],'annotations':[]}
        def intake(directory,rows,source):
            self.assertEqual(len(rows),2)
            for row in rows:
                job=directory/'jobs'/recovery.job_id(row['paper']['arxiv'])
                self.assertTrue((job/'intake.json').exists())
                write_json(job/'state.json',{**row,'state':'ingested'})
                (job/'intake.json').unlink()
            data=recovery.read(source)
            for paper in data['papers']:paper['extraction_status']='complete'
            write_json(source,data)
        with patch.object(recovery.joint,'check_worker'),patch.object(recovery.joint,'context',return_value='unchanged'),patch.object(recovery.joint,'taxonomies',return_value={}),patch.object(recovery.joint,'response_schema',return_value={}),patch.object(recovery,'read_source',return_value=('source',{})),patch.object(recovery,'ThreadPoolExecutor',ImmediatePool),patch.object(recovery.joint,'run_worker',side_effect=result),patch.object(recovery.joint,'intake',side_effect=intake) as writer,patch.object(recovery,'take',side_effect=lambda:slots.take(self.root/'slots')):
            status=recovery.run(self.run,execute=True,source=self.source,corpus=self.corpus,first=self.first)
        self.assertEqual(status['phase'],'completed')
        self.assertEqual(status['counts'],{'ingested':2})
        self.assertEqual(writer.call_count,1)

    def test_durable_journal_replays_without_model_call(self):
        self.prepare();job=self.run/'jobs'/'2401.00001v1';job.mkdir(parents=True)
        row={'state':'ready','paper':PAPER,'outcome':'skip','entries':[],'annotations':[]}
        write_json(job/'intake.json',row)
        with patch.object(recovery.joint,'intake',side_effect=self.fake_intake),patch.object(recovery.joint,'run_worker') as worker:
            recovery.restore(self.run,self.source,self.corpus)
            worker.assert_not_called()
            self.assertEqual(recovery.read(job/'state.json')['state'],'ingested')

    def test_unknown_running_paid_worker_blocks_recovery(self):
        self.prepare();job=self.run/'jobs'/'2401.00001v1';job.mkdir(parents=True)
        write_json(job/'state.json',{'state':'running','paper':PAPER})
        with patch.object(recovery.joint,'run_worker') as worker:
            with self.assertRaisesRegex(ValueError,'possible live paid worker'):
                recovery.restore(self.run,self.source,self.corpus)
            worker.assert_not_called()

    def test_missing_catalogue_waits_without_stale_fallback_or_paid_call(self):
        self.prepare()
        original_read = recovery.read
        def missing(path):
            if Path(path).resolve()==self.source.resolve():
                raise FileNotFoundError(2,'temporary exact-source absence',str(path))
            return original_read(path)
        def stop_after_wait(_): (self.run/'STOP').touch()
        with patch.object(recovery.joint,'check_worker'),patch.object(recovery,'permission',return_value=(True,'spare capacity')),patch.object(recovery,'read',side_effect=missing),patch.object(recovery.time,'sleep',side_effect=stop_after_wait),patch.object(recovery.joint,'run_worker') as worker:
            result = recovery.run(self.run,execute=True,source=self.source,corpus=self.corpus,first=self.first)
            self.assertEqual(result['phase'],'blocked')
            self.assertEqual(result['counts'],{})
            worker.assert_not_called()
            self.assertEqual(original_read(self.source)['papers'][0]['extraction_status'],'unresolved')


if __name__=='__main__': unittest.main()
