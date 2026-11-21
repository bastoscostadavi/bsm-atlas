import importlib.util,tempfile,json,time
from pathlib import Path
from unittest.mock import Mock,patch
import unittest
from bsm_atlas import supervision as m
NOW=10000
DEAD={'alive':False,'matches':False};LIVE={'alive':True,'matches':True,'launched':'1970-01-01T02:46:30+00:00'}
def decision(reason='',phase='blocked',kind='engine',process=None,busy=False,state=None,**kwargs):
 return m.restart_decision(kind,{'phase':phase,'reason':reason,**kwargs},process or DEAD,busy,NOW,state or {},{'max_restarts_per_hour':3})
class PolicyTests(unittest.TestCase):
 def test_live_locked_engine_is_not_restarted(self):self.assertEqual(decision(process=LIVE,busy=True)['state'],'running')
 def test_pid_and_lock_disagreement_requires_agent(self):self.assertEqual(decision(busy=True)['state'],'attention')
 def test_pid_reuse_never_launches_duplicate(self):self.assertEqual(decision(process={'alive':True,'matches':False})['state'],'attention')
 def test_startup_grace_without_lock(self):self.assertEqual(decision(process=LIVE)['state'],'starting')
 def test_routing_failure_resumes(self):self.assertEqual(decision('workspace routing discovery failed')['state'],'restart')
 def test_stop_marker_wins_over_error(self):self.assertEqual(decision('workspace routing discovery failed',stop_marker=True)['state'],'paused')
 def test_intentional_drain_does_not_auto_restart(self):self.assertEqual(decision('Termination requested; active workers drain',phase='stopped')['state'],'paused')
 def test_quota_auth_and_credit_errors_need_input(self):
  for reason in ['usage limit exceeded','authentication failed','HTTP 403 forbidden','credits exhausted']:
   self.assertEqual(decision(reason)['state'],'attention')
 def test_unknown_error_escalates(self):self.assertEqual(decision('bad database schema')['state'],'attention')
 def test_backoff_deadline_honored(self):self.assertEqual(decision('temporary failure in name resolution',kind='mirror',retry_at=NOW+60)['state'],'backoff')
 def test_expired_explicit_rate_limit_can_resume_mirror(self):
  self.assertEqual(decision('HTTP 429',kind='mirror',retry_at=NOW-1)['state'],'restart')
  self.assertEqual(decision('HTTP 429',kind='mirror')['state'],'attention')
 def test_restart_budget_is_bounded(self):
  state={'restart_history':[{'component':'engine','time':NOW-100-i} for i in range(3)]}
  self.assertEqual(decision('workspace routing discovery failed',state=state)['state'],'attention')
 def test_restart_cooldown(self):
  state={'restart_history':[{'component':'engine','time':NOW-5}]}
  self.assertEqual(decision('workspace routing discovery failed',state=state)['state'],'backoff')
 def test_source_missing_never_uses_old_snapshot(self):
  result=m.restart_decision('engine',{'phase':'blocked','reason':'No such file or directory: atlas/catalogue.json'},DEAD,False,NOW,{}, {},False)
  self.assertEqual(result['state'],'attention')
 def test_only_missing_source_is_known_file_recovery(self):
  self.assertEqual(decision('No such file or directory: atlas/catalogue.json')['state'],'restart')
  self.assertEqual(decision('No such file or directory: something_else.txt')['state'],'attention')
class SupervisorTests(unittest.TestCase):
 def make(self,folder):
  root=Path(folder);batch=root/'.harvest/batch';supervisor=batch/'supervisor';supervisor.mkdir(parents=True)
  (supervisor/'config.json').write_text(json.dumps({'schema_version':m.VERSION,'engine_sha256':'abc'}))
  with patch.object(m,'ROOT',root):instance=m.Supervisor(batch)
  return root,batch,instance
 def test_healthy_check_does_not_launch_anything(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);status={'phase':'running','updated':m.stamp(),'pid':42,'measured_attempts':10,'counts':{'ingested':10},'pipeline':{'active_workers':16}}
   with patch.object(m,'ROOT',root),patch.object(s,'observe',return_value=(status,{},LIVE,True)),patch.object(s,'restart') as restart:
    result=s.check(True);self.assertEqual(result['state'],'healthy');restart.assert_not_called()
 def test_maintenance_marker_prevents_actions(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);(b/'supervisor/MAINTENANCE').touch()
   with patch.object(s,'observe') as observe:result=s.check(True);observe.assert_not_called();self.assertEqual(result['state'],'maintenance')
 def test_unknown_failure_requires_agent_not_restart(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d)
   with patch.object(m,'ROOT',root),patch.object(s,'observe',return_value=({'phase':'blocked','reason':'unexpected exception'}, {}, DEAD,False)),patch.object(s,'restart') as restart:
    result=s.check(True);self.assertTrue(result['needs_agent']);restart.assert_not_called()
 def test_completed_paper_loss_prevents_restart(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);job=b/'rolling/run/jobs/id';job.mkdir(parents=True);(job/'state.json').write_text(json.dumps({'state':'ingested','paper':{'arxiv':'2401.00001v1'}}))
   with self.assertRaisesRegex(RuntimeError,'Completed paper is missing'):s.verify_completed_presence({'papers':[]})
 def test_unfinished_paid_call_requires_inspection(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);job=b/'rolling/run/jobs/id';job.mkdir(parents=True);(job/'state.json').write_text(json.dumps({'state':'running'}))
   self.assertEqual(s.unfinished_paid_jobs(),'id');(job/'intake.json').write_text('{}');self.assertIsNone(s.unfinished_paid_jobs())
 def test_stall_detection_uses_work_not_heartbeat(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);status={'pid':42,'measured_attempts':10,'counts':{'ingested':10,'running':16},'updated':m.stamp(),'producer':{'ready_usable_tex':3}}
   s.state['progress']={'engine':{'signature':[42,10,10],'last_progress':time.time()-1900,'last_progress_monotonic':time.monotonic()-1900}}
   result=s.progress('engine',status,{'state':'running'});self.assertEqual(result['state'],'attention')
 def test_backoff_is_not_reported_as_stall(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);status={'state':'cooldown','updated':m.stamp(),'retry_at':time.time()+1800}
   self.assertEqual(s.progress('mirror',status,{'state':'backoff'})['state'],'backoff')
 def test_completion_is_verified_against_all_reserved_papers(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);(b/'reserved-papers.json').write_text(json.dumps({'papers':[{'arxiv':'2401.00001v2'}]}))
   def observe(kind):return ({'phase':'completed'} if kind=='engine' else {'state':'requesting','updated':m.stamp()}, {}, DEAD if kind=='engine' else LIVE,kind!='engine')
   with patch.object(m,'ROOT',root),patch.object(s,'observe',side_effect=observe),patch.object(s,'verify_settings',return_value={'papers':[]}):
    result=s.check(False);self.assertEqual(result['state'],'attention')
   with patch.object(m,'ROOT',root),patch.object(s,'observe',side_effect=observe),patch.object(s,'verify_settings',return_value={'papers':[{'arxiv':'2401.00001v1'}]}):
    result=s.check(False);self.assertEqual(result['state'],'ingestion_completed')
 def test_recognized_restart_uses_pinned_command_and_records_budget(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);(root/'atlas').mkdir();(root/'atlas/catalogue.json').write_text('{}');s.config['python']='/trusted/python'
   observation={'phase':'blocked','reason':'workspace routing discovery failed'}
   child=Mock();child.pid=123
   with patch.object(m,'ROOT',root),patch.object(s,'verify_settings',return_value={'papers':[]}),patch.object(s,'verify_completed_presence'),patch.object(s,'unfinished_paid_jobs',return_value=None),patch.object(s,'observe',return_value=(observation,{},DEAD,False)),patch.object(m.subprocess,'Popen',return_value=child) as popen,patch.object(m.sys,'platform','linux'):
    result=s.restart('engine',observation)
   self.assertEqual(result['action'],'restarted');self.assertEqual(popen.call_args.args[0],['/trusted/python','-B','-u',str((b/'rolling_ready.py').resolve()),'--execute'])
   record=json.loads((b/'queue-process.json').read_text());self.assertEqual((record['model'],record['reasoning'],record['workers']),('gpt-6-luna','medium',16))
   self.assertEqual(len(json.loads((b/'supervisor/state.json').read_text())['restart_history']),1)
 def test_running_engine_cannot_be_restarted_after_lock_race(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);(root/'atlas').mkdir();(root/'atlas/catalogue.json').write_text('{}');s.config['python']='/trusted/python'
   with patch.object(m,'ROOT',root),patch.object(s,'verify_settings',return_value={'papers':[]}),patch.object(s,'verify_completed_presence'),patch.object(s,'unfinished_paid_jobs',return_value=None),patch.object(s,'observe',return_value=({'phase':'running'}, {},LIVE,True)),patch.object(m.subprocess,'Popen') as popen:
    result=s.restart('engine',{})
   self.assertEqual(result['action'],'not_started');popen.assert_not_called()

 def test_unchanged_issue_does_not_duplicate_events(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d)
   with patch.object(m,'ROOT',root),patch.object(s,'observe',return_value=({'phase':'blocked','reason':'unexpected exception'}, {},DEAD,False)):
    first=s.check(False);sequence=s.state['events_sequence'];second=s.check(False)
   self.assertTrue(first['meaningful_change']);self.assertFalse(second['meaningful_change']);self.assertEqual(s.state['events_sequence'],sequence)

 def test_wall_clock_pause_does_not_count_as_active_stall(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);status={'pid':42,'measured_attempts':10,'counts':{'ingested':10},'updated':'1970-01-01T02:46:40+00:00','producer':{'ready_usable_tex':3}}
   s.state['progress']={'engine':{'signature':[42,10,10],'last_progress':2800,'last_progress_monotonic':4990}}
   with patch.object(m.time,'time',return_value=10000),patch.object(m.time,'monotonic',return_value=5000):
    result=s.progress('engine',status,{'state':'running'})
   self.assertEqual(result['state'],'running')
   self.assertEqual(s.state['progress']['engine']['last_progress_monotonic'],4990)
 def test_legacy_progress_starts_monotonic_baseline_without_clearing_restart_history(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);status={'pid':42,'measured_attempts':10,'counts':{'ingested':10},'updated':'1970-01-01T02:46:40+00:00','producer':{'ready_usable_tex':3}}
   history=[{'component':'engine','time':9000,'pid':41}];s.state['restart_history']=history.copy()
   s.state['progress']={'engine':{'signature':[42,10,10],'last_progress':2800}}
   with patch.object(m.time,'time',return_value=10000),patch.object(m.time,'monotonic',return_value=5000):
    self.assertEqual(s.progress('engine',status,{'state':'running'})['state'],'running')
   self.assertEqual(s.state['progress']['engine']['last_progress_monotonic'],5000)
   self.assertEqual(s.state['restart_history'],history)
 def test_reset_monotonic_clock_starts_fresh_progress_baseline(self):
  with tempfile.TemporaryDirectory() as d:
   root,b,s=self.make(d);status={'pid':42,'measured_attempts':10,'counts':{'ingested':10},'updated':'1970-01-01T02:46:40+00:00','producer':{'ready_usable_tex':3}}
   s.state['progress']={'engine':{'signature':[42,10,10],'last_progress':2800,'last_progress_monotonic':9000}}
   with patch.object(m.time,'time',return_value=10000),patch.object(m.time,'monotonic',return_value=5000):
    self.assertEqual(s.progress('engine',status,{'state':'running'})['state'],'running')
   self.assertEqual(s.state['progress']['engine']['last_progress_monotonic'],5000)

if __name__=='__main__':unittest.main()
