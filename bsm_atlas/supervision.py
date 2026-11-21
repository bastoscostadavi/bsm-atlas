"""Bounded local supervision for the existing primary-hep-ph Luna first pass.

Healthy checks only read small operational files. Restarts require a recognized
failure, released OS locks, pinned scientific settings, and a restart budget.
No catalogue content, paper outcomes, prompts or model responses are modified.
"""
from argparse import ArgumentParser
from contextlib import contextmanager
from datetime import datetime,timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_BATCH=ROOT/'.harvest/luna-tex-first-primary-20261109'
VERSION='bsm-atlas-supervisor-1'


def read(path,default=None):
 try:return json.loads(Path(path).read_text())
 except FileNotFoundError:
  if default is not None:return default
  raise

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'-',delete=False) as handle:
  temporary=Path(handle.name)
  try:
   json.dump(value,handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno());temporary.replace(path)
  finally:temporary.unlink(missing_ok=True)

def stamp():return datetime.now(timezone.utc).isoformat()

def epoch(value):
 try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
 except (AttributeError,TypeError,ValueError):return 0

@contextmanager
def lock(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a') as handle:
  fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:fcntl.flock(handle,fcntl.LOCK_UN)

def held(path):
 path=Path(path)
 if not path.exists():return False
 with path.open('r') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return True
  fcntl.flock(handle,fcntl.LOCK_UN);return False

def alive(pid):
 if type(pid) is not int or pid<1:return False
 try:os.kill(pid,0);return True
 except ProcessLookupError:return False
 except PermissionError:raise RuntimeError('Cannot inspect recorded process; refusing a duplicate')

def command_matches(pid,needle):
 try:value=subprocess.check_output(['/bin/ps','-p',str(pid),'-o','command='],text=True,timeout=5)
 except subprocess.CalledProcessError:return False
 return needle in value

def tail(path,limit=6000):
 try:
  with Path(path).open('rb') as handle:handle.seek(0,2);size=handle.tell();handle.seek(max(0,size-limit));return handle.read().decode(errors='replace')
 except (FileNotFoundError,IsADirectoryError):return ''

def classify(reason):
 text=(reason or '').lower()
 if any(term in text for term in ['quota','usage limit','usage_limit','credits','authentication','unauthorized','login','http 401','http 403','forbidden','billing']):return 'access_or_quota'
 if 'http 429' in text or 'too many requests' in text:return 'rate_limit'
 if 'workspace routing discovery failed' in text:return 'routing'
 if 'no such file or directory' in text and 'atlas/catalogue.json' in text:return 'source_temporarily_missing'
 if any(term in text for term in ['nodename nor servname','temporary failure in name resolution','eaddrnotavail','connection reset','handshake operation timed out','network is unreachable','urlopen error']):return 'transport'
 if 'termination requested' in text or 'stop marker' in text:return 'intentional_stop'
 return 'unexpected'


def restart_decision(kind,status,process,locks_busy,now,state,config,source_present=True):
 """Pure policy; unknown/live cases are diagnosed by the scheduled agent."""
 phase=status.get('phase',status.get('state','unknown'));reason=status.get('reason','')
 if status.get('stop_marker'):return {'state':'paused','reason':'STOP marker present'}
 if locks_busy:
  if not process.get('alive') or not process.get('matches'):return {'state':'attention','reason':'Held lock and process record do not agree'}
  if isinstance(status.get('retry_at'),(int,float)) and status['retry_at']>now:return {'state':'backoff','reason':status.get('reason'),'retry_at':status['retry_at']}
  return {'state':'running','reason':None}
 if process.get('alive'):
  if not process.get('matches'):return {'state':'attention','reason':'Recorded PID belongs to another process'}
  age=max(0,now-epoch(process.get('launched')))
  return {'state':'starting' if age<180 else 'attention','reason':None if age<180 else 'Process is alive without its ownership lock'}
 if phase in ['completed','finished']:return {'state':'complete_candidate','reason':None}
 category=classify(reason)
 if category=='intentional_stop':return {'state':'paused','reason':reason}
 if category=='access_or_quota':return {'state':'attention','reason':reason,'category':category}
 retry_at=status.get('retry_at',0)
 if isinstance(retry_at,(int,float)) and retry_at>now:return {'state':'backoff','reason':reason,'retry_at':retry_at}
 if category=='rate_limit' and (not isinstance(retry_at,(int,float)) or retry_at<=0):return {'state':'attention','reason':'Rate limit has no explicit retry deadline'}
 allowed={'routing','source_temporarily_missing'} if kind=='engine' else {'transport','rate_limit'}
 if category not in allowed:return {'state':'attention','reason':reason or 'Process exited without a recognized terminal reason','category':category}
 if kind=='engine' and not source_present:return {'state':'attention','reason':'Working catalogue is missing; do not restore an old snapshot'}
 history=[value for value in state.get('restart_history',[]) if value['component']==kind and value['time']>now-3600]
 if len(history)>=config.get('max_restarts_per_hour',3):return {'state':'attention','reason':'Automatic restart budget exhausted','category':category}
 if history:
  deadline=history[-1]['time']+[60,300,900][min(len(history)-1,2)]
  if deadline>now:return {'state':'backoff','reason':'Restart cooldown','retry_at':deadline}
 return {'state':'restart','reason':reason,'category':category}


class Supervisor:
 def __init__(self,batch=DEFAULT_BATCH):
  self.batch=Path(batch).resolve();self.folder=self.batch/'supervisor'
  if not self.batch.is_relative_to(ROOT.resolve()/'.harvest'):raise ValueError('Supervisor batch must be under this project .harvest')
  self.config=read(self.folder/'config.json')
  if self.config.get('schema_version')!=VERSION:raise ValueError('Unsupported supervisor configuration')
  self.state=read(self.folder/'state.json',{'restart_history':[],'progress':{},'events_sequence':0})
 def event(self,kind,**fields):
  self.state['events_sequence']=self.state.get('events_sequence',0)+1
  value={'sequence':self.state['events_sequence'],'time':stamp(),'type':kind,**fields};path=self.folder/'events.jsonl'
  if path.exists() and path.stat().st_size>1024**2:path.replace(self.folder/'events.previous.jsonl')
  with path.open('a') as handle:handle.write(json.dumps(value)+'\n')
  return value
 def verify_settings(self):
  plan=read(self.batch/'plan.json')
  if (plan.get('model'),plan.get('reasoning'),plan.get('workers'))!=('gpt-6-luna','medium',16):raise ValueError('Frozen model, effort or worker settings changed')
  checks=[(self.batch/'reserved-papers.json',plan['manifest_sha256']),
          (ROOT/'bsm_atlas/joint_harvest.py',plan['runner_sha256']),
          (self.batch/'rolling_ready.py',self.config['engine_sha256'])]
  for path,digest in checks:
   if sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Pinned file changed; agent must inspect: '+str(path))
  source=read(ROOT/'atlas/catalogue.json')
  if source.get('schema_version')!='bsm-atlas-1' or not isinstance(source.get('papers'),list) or not isinstance(source.get('entries'),list):raise ValueError('Working catalogue is invalid')
  return source
 def verify_completed_presence(self,source):
  known={paper['arxiv'].rsplit('v',1)[0] for paper in source['papers']}
  for path in (self.batch/'rolling/run/jobs').glob('*/state.json'):
   value=read(path)
   if value.get('state') in {'ingested','invalid','retry','source_unavailable','interrupted'} and value['paper']['arxiv'].rsplit('v',1)[0] not in known:
    raise RuntimeError('Completed paper is missing from working catalogue; agent recovery required: '+path.parent.name)

 def unfinished_paid_jobs(self):
  # Only needed before restarting a stopped engine, never on healthy checks.
  for path in (self.batch/'rolling/run/jobs').glob('*/state.json'):
   value=read(path)
   if value.get('state')!='running':continue
   job=path.parent
   if (job/'intake.json').exists() or (job/'metrics.json').exists():continue
   return job.name
  return None
 def observe(self,kind):
  if kind=='engine':
   status=read(self.batch/'status.json',{});record=read(self.batch/'queue-process.json',{})
   marker=(self.batch/'STOP').exists() or (self.batch/'rolling/run/STOP').exists()
   locks_busy=held(self.batch/'queue.lock') or held(self.batch/'rolling/engine.lock');needle=str(self.batch/'rolling_ready.py')
  else:
   directory=ROOT/'corpus/hep-ph';status=read(directory/'transfer-state.json',{});record=read(directory/'mirror-process.json',{})
   marker=(directory/'STOP').exists();locks_busy=held(directory/'mirror-run/.lock') or held(directory/'.lock');needle='scripts/mirror_hepph.py'
   if not locks_busy and classify(status.get('reason',''))=='unexpected':
    status={**status,'reason':tail(directory/'mirror.log',2000)}
  pid=record.get('pid');is_alive=alive(pid);matches=command_matches(pid,needle) if is_alive else False
  observation={**status,'stop_marker':marker}
  process={'pid':pid,'alive':is_alive,'matches':matches,'launched':record.get('launched',status.get('updated'))}
  return observation,record,process,locks_busy
 def restart(self,kind,status):
  if kind=='engine':
   source=self.verify_settings();self.verify_completed_presence(source);unfinished=self.unfinished_paid_jobs()
   if unfinished:raise RuntimeError('Possible orphan paid call; agent must inspect: '+unfinished)
   parent=self.batch;locks=[parent/'launch.lock'];script=self.batch/'rolling_ready.py';args=[self.config['python'],'-B','-u',str(script),'--execute'];target=parent/'queue-process.json'
  else:
   parent=ROOT/'corpus/hep-ph';locks=[self.folder/'mirror-launch.lock'];args=[self.config['python'],'-B','-u',str(ROOT/'scripts/mirror_hepph.py')];target=parent/'mirror-process.json'
  with lock(locks[0]):
   observation,record,process,busy=self.observe(kind)
   decision=restart_decision(kind,observation,process,busy,time.time(),self.state,self.config,(ROOT/'atlas/catalogue.json').exists())
   if decision['state']!='restart':return {'action':'not_started','decision':decision}
   if any(path.exists() for path in [self.batch/'STOP',self.batch/'rolling/run/STOP',ROOT/'corpus/hep-ph/STOP',self.folder/'MAINTENANCE']):return {'action':'not_started','reason':'STOP or maintenance marker'}
   logfile=self.folder/(kind+'-resume-'+str(time.time_ns())+'.log') if kind=='engine' else ROOT/'corpus/hep-ph/mirror.log'
   environment=dict(os.environ)
   if self.config.get('runtime_path'):environment['PATH']=self.config['runtime_path']
   with logfile.open('a') as log:child=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=environment)
   guard=None
   if sys.platform=='darwin':guard=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(child.pid)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True).pid
   value={'pid':child.pid,'idle_sleep_guard_pid':guard,'command':args,'log':str(logfile),'launched':stamp(),'supervised':True,'resume_reason':decision.get('reason')}
   if kind=='engine':value.update(scheduler='continuous-ready-tex',model='gpt-6-luna',reasoning='medium',workers=16)
   atomic(target,value);self.state.setdefault('restart_history',[]).append({'component':kind,'time':time.time(),'pid':child.pid})
   atomic(self.folder/'state.json',self.state)
   self.event('routine_restart',component=kind,pid=child.pid,reason=decision.get('reason'))
   return {'action':'restarted','pid':child.pid}
 def progress(self,kind,status,decision):
  now=time.time();awake_now=time.monotonic();old=self.state.setdefault('progress',{}).get(kind,{})
  if kind=='engine':
   signature=[status.get('pid'),status.get('measured_attempts'),sum(n for k,n in (status.get('counts') or {}).items() if k!='running')]
  else:signature=[status.get('url'),status.get('last_url'),status.get('updated')]
  # Do not use a changing heartbeat or running-worker count as proof of work.
  changed=old.get('signature')!=signature
  latest=now if changed or not old else old.get('last_progress',now)
  # Wall-clock pauses must not count as active processing time. Keep wall
  # timestamps for inspection and quota deadlines; stall checks use the
  # monotonic clock, which excludes system sleep on this macOS host.
  prior_awake=old.get('last_progress_monotonic')
  awake_latest=awake_now if changed or type(prior_awake) not in (int,float) or not 0<=prior_awake<=awake_now else prior_awake
  self.state['progress'][kind]={'signature':signature,'last_progress':latest,'last_progress_monotonic':awake_latest}
  age=now-epoch(status.get('updated'))
  if decision['state']=='running' and kind=='engine':
   metadata=read(self.batch/'transfer-state.json',{})
   if metadata.get('state')=='cooldown' and metadata.get('retry_at',0)>now and not (status.get('pipeline') or {}).get('active_workers') and not (status.get('pipeline') or {}).get('writer_busy'):
    return {'state':'backoff','reason':'Bibliographic metadata backoff','retry_at':metadata['retry_at']}
   if age>180:decision={'state':'attention','reason':'Engine heartbeat is stale; inspect active calls before any restart'}
   elif awake_now-awake_latest>self.config.get('stall_seconds',1800):
    producer=status.get('producer') or {};pipeline=status.get('pipeline') or {}
    if producer.get('ready_usable_tex',0)>0 or pipeline.get('writer_busy') or pipeline.get('active_workers',0)>0:
     decision={'state':'attention','reason':'No completed-paper progress for 30 minutes; agent diagnosis required'}
  return decision
 def check(self,execute=False):
  self.folder.mkdir(exist_ok=True)
  with lock(self.folder/'check.lock'):
   result={'schema_version':VERSION,'checked_utc':stamp(),'batch':str(self.batch),'execute':execute,'components':{},'actions':[],'needs_agent':False}
   if not self.config.get('enabled',True):
    result.update(state='disabled',reason='Supervision has been disabled');atomic(self.folder/'health.json',result);return result
   if (self.folder/'MAINTENANCE').exists():
    result.update(state='maintenance',reason='Maintenance marker present; no automatic restarts');atomic(self.folder/'health.json',result);return result
   for kind in ['engine','mirror']:
    status,record,process,busy=self.observe(kind)
    decision=restart_decision(kind,status,process,busy,time.time(),self.state,self.config,(ROOT/'atlas/catalogue.json').exists())
    decision=self.progress(kind,status,decision)
    if decision['state']=='complete_candidate' and kind=='engine':
     source=self.verify_settings();known={paper['arxiv'].rsplit('v',1)[0] for paper in source['papers']}
     targets=read(self.batch/'reserved-papers.json')['papers'];missing=[paper['arxiv'] for paper in targets if paper['arxiv'].rsplit('v',1)[0] not in known]
     decision={'state':'completed','reason':None} if not missing else {'state':'attention','reason':'Engine claims completion but reserved papers are missing','missing_papers':len(missing)}
    elif decision['state']=='complete_candidate':decision={'state':'completed','reason':None}
    if decision['state']=='restart' and execute:
     try:result['actions'].append({'component':kind,**self.restart(kind,status)});decision={**decision,'state':'restarting'}
     except Exception as error:decision={'state':'attention','reason':str(error)}
    result['components'][kind]={'decision':decision,'pid':process.get('pid'),'process_alive':process['alive'],'lock_held':busy,
     'phase':status.get('phase',status.get('state')),'heartbeat_utc':status.get('updated'),
     'active_workers':(status.get('pipeline') or {}).get('active_workers'),
     'measured_attempts':status.get('measured_attempts'),'counts':status.get('counts'),
     'ready_usable_tex':(status.get('producer') or {}).get('ready_usable_tex'),'retry_at':status.get('retry_at')}
    if decision['state']=='attention':result['needs_agent']=True
   if all(value['decision']['state']=='completed' for value in result['components'].values()):result['state']='completed'
   elif result['components']['engine']['decision']['state']=='completed':result['state']='ingestion_completed'
   elif result['needs_agent']:result['state']='attention'
   elif any(value['decision']['state']=='paused' for value in result['components'].values()):result['state']='paused'
   else:result['state']='healthy'
   previous=read(self.folder/'health.json',{})
   fingerprint=sha256(json.dumps({'state':result['state'],'issues':{kind:component['decision'] for kind,component in result['components'].items() if component['decision']['state'] in ['attention','completed','paused']}},sort_keys=True).encode()).hexdigest()
   if previous.get('issue_fingerprint')!=fingerprint and result['state'] in ['attention','completed','ingestion_completed']:
    self.event('needs_agent' if result['needs_agent'] else 'completion_candidate',details=result['components'])
   result['meaningful_change']=previous.get('issue_fingerprint')!=fingerprint
   result['issue_fingerprint']=fingerprint
   self.state['restart_history']=[item for item in self.state.get('restart_history',[]) if item['time']>time.time()-86400]
   atomic(self.folder/'state.json',self.state);atomic(self.folder/'health.json',result);return result


def main():
 parser=ArgumentParser(description=__doc__);parser.add_argument('--batch',type=Path,default=DEFAULT_BATCH);parser.add_argument('--execute',action='store_true');parser.add_argument('--quiet',action='store_true');args=parser.parse_args()
 try:
  result=Supervisor(args.batch).check(args.execute)
  if not args.quiet:print(json.dumps(result,indent=2))
  elif result.get('actions') or result.get('meaningful_change') and result['state'] in ['attention','completed','ingestion_completed']:print(json.dumps({'checked_utc':result['checked_utc'],'state':result['state'],'actions':result['actions'],'needs_agent':result['needs_agent']}))
 except BlockingIOError:print(json.dumps({'state':'check_already_running'}))
 except Exception as error:
  result={'schema_version':VERSION,'checked_utc':stamp(),'state':'attention','needs_agent':True,'reason':str(error),'batch':str(args.batch)}
  try:atomic(args.batch/'supervisor/health.json',result)
  except OSError:pass
  print(json.dumps(result,indent=2));return 1
 return 0

if __name__=='__main__':raise SystemExit(main())
