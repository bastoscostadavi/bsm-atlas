"""Selective Terra re-extraction and paper-level disagreement tracking.

No Luna answer is shown to Terra. The same local paper, conventions and fixed
vocabularies are supplied. One Terra attempt per selected paper; no automatic
retry or full-corpus switch. Missing/unusable sources wait for source repair.
"""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from threading import Event

from .catalogue import ROOT, SOURCE, load, identity, write_json, exclusive_lock
from .corpus import CORPUS
from .corpus_queue import read_source, AwaitingSource
from .extraction_quality import assessment, audit_decision
from .joint_harvest import (read, now, context, taxonomies, response_schema, run_worker,
                            intake, compact, check_worker, DEFAULT_EXECUTABLE)
from .papers import job_id

MODEL='gpt-6.1-terra'
VERSION='selective-terra-followup-1'


def original_rows(runs):
    result={}
    for run in map(Path,runs):
        for path in sorted((run/'jobs').glob('*/state.json')):
            row=read(path)
            if row.get('state') in ('running','already_recorded','pending'):continue
            paper=row.get('paper',{})
            if not paper.get('arxiv'):continue
            row=deepcopy(row);row['baseline_job']=str(path.parent.resolve())
            row.setdefault('quality',assessment(row))
            result[paper['arxiv']]=row
    return result


def comparison_snapshot(identifier, baseline, source=SOURCE):
    """Compact accepted model identities and positive associations for this paper."""
    from .literature import load_links,path_for
    data=load(source);paper=next((p for p in data['papers'] if p['arxiv']==identifier),None)
    if paper is None:return {'fingerprints':[],'problems':[],'mechanisms':[]}
    entries=[e for e in data['entries'] if any(r['paper_id']==paper['id'] for r in e['references'])]
    fp={e['id']:identity(e['specification'])['fingerprint'] for e in entries}
    snapshot={'fingerprints':sorted(set(fp.values())),'problems':[],'mechanisms':[]}
    links=load_links(path_for(source))['papers'].get(paper['id'],{})
    for model in links.get('models',[]):
        if model['entry_id'] not in fp:continue
        for kind in ('problems','mechanisms'):
            snapshot[kind].extend((fp[model['entry_id']],l['term_id']) for l in model[kind])
    for kind in ('problems','mechanisms'):snapshot[kind]=[list(pair) for pair in sorted(set(snapshot[kind]))]
    return snapshot


def extracted_snapshot(row):
    fingerprints={e['id']:identity(e['specification'])['fingerprint'] for e in row.get('entries',[])}
    result={'fingerprints':sorted(set(fingerprints.values())),'problems':[],'mechanisms':[]}
    for model in row.get('annotations',[]):
        for kind in ('problems','mechanisms'):
            result[kind].extend((fingerprints[model['local_id']],link['term_id']) for link in model[kind])
    for kind in ('problems','mechanisms'):result[kind]=[list(pair) for pair in sorted(set(result[kind]))]
    return result


def finish(directory, row, baseline, baseline_snapshot, decision, source=SOURCE):
    """Only unopposed recoveries enter automatically; disagreement is not proof."""
    directory=Path(directory);job=directory/'jobs'/job_id(row['paper']['arxiv'])
    quality=row.get('quality') or assessment(row)
    accepted=row['state']=='ready' and row.get('outcome') in ('entries','skip')
    terra=extracted_snapshot(row) if accepted else None
    inventory_agrees=bool(accepted and terra['fingerprints']==baseline_snapshot['fingerprints'])
    associations_agree=bool(accepted and all(terra[k]==baseline_snapshot[k] for k in ('problems','mechanisms')))
    clean=accepted and quality['confidence']=='high' and not quality['needs_followup']
    # Recover failed attempts or a missed inventory from a Luna skip. Never
    # silently union conflicting spectra, delete established entries or promote
    # a stronger model's disagreement to certified ground truth.
    can_apply=clean and (baseline['state'] in ('invalid','retry','interrupted') or
        (baseline.get('outcome')=='skip' and bool(terra['fingerprints'])))
    summary={'schema_version':VERSION,'paper':row['paper'],'selection':decision,
        'baseline_job':baseline['baseline_job'],'baseline_quality':baseline['quality'],
        'baseline':baseline_snapshot,'terra':terra,'model':MODEL,'quality':quality,
        'inventory_agrees':inventory_agrees,'associations_agree':associations_agree,
        'applied':False,'finished':now(),'reason':row.get('reason')}
    if can_apply:
        intake(directory,[row],source);summary['applied']=True;summary['state']='recovered'
    elif not accepted:
        summary['state']='unresolved'
    elif not clean:
        summary['state']='uncertain'
    elif inventory_agrees and associations_agree:
        summary['state']='agreement'
    else:
        summary['state']='disagreement'
    summary['needs_reconciliation']=summary['state'] in ('disagreement','uncertain','unresolved')
    write_json(job/'comparison.json',summary)
    write_json(job/'state.json',summary)
    compact(job)
    write_json(Path(baseline['baseline_job'])/'followup.json',{
        'model':MODEL,'comparison':str((job/'comparison.json').resolve()),
        'state':summary['state'],'applied':summary['applied'],
        'needs_reconciliation':summary['needs_reconciliation'],'finished':summary['finished']})
    return summary


def candidates(rows, policy, pilot):
    selected={}
    for identifier,row in rows.items():
        reason=pilot.get(identifier) or audit_decision(identifier,row,
            fraction=policy['audit_fraction'],seed=policy['seed'])
        if reason and reason!='source_repair':selected[identifier]=(row,reason)
    return selected


def freeze_pilot(rows, directory, per_stratum=10):
    """A bounded diagnostic panel, explicitly separate from the 2% random audit."""
    target=Path(directory)/'pilot-selection.json'
    if target.exists():return read(target)
    groups={'flagged':[],'entries':[],'skip':[]}
    for identifier,row in rows.items():
        decision=audit_decision(identifier,row)
        if decision=='source_repair':continue
        if decision=='flagged':group='flagged'
        elif row.get('state')=='ingested':group='skip' if row.get('outcome')=='skip' else 'entries'
        else:continue
        groups[group].append(identifier)
    chosen={}
    for group,identifiers in groups.items():
        for identifier in sorted(identifiers,key=lambda i:sha256(('diagnostic-20261108|'+i).encode()).digest())[:per_stratum]:
            chosen[identifier]='pilot_'+group
    write_json(target,chosen);return chosen


def run(runs,directory,*,workers=4,audit_fraction=0.02,execute=False,source=SOURCE,
        corpus=CORPUS,executable=DEFAULT_EXECUTABLE,once=False):
    runs=[Path(p).resolve() for p in runs];directory=Path(directory).resolve()
    policy={'schema_version':VERSION,'model':MODEL,'reasoning':'medium','workers':workers,
        'audit_fraction':audit_fraction,'seed':'atlas-luna-terra-20261108','runs':list(map(str,runs)),
        'source':str(Path(source).resolve()),'corpus':str(Path(corpus).resolve()),
        'executable':str(executable),'timeout':900,'once':once}
    if not 1<=workers<=8 or not 0<=audit_fraction<=1:raise ValueError('Invalid follow-up policy')
    if not execute:return {'dry_run':True,**policy}
    check_worker(executable);directory.mkdir(parents=True,exist_ok=True);(directory/'jobs').mkdir(exist_ok=True)
    with exclusive_lock(directory/'run.lock'):
        path=directory/'policy.json'
        if path.exists() and read(path)!=policy:raise ValueError('Frozen follow-up policy changed')
        write_json(path,policy);write_json(directory/'response.schema.json',response_schema())
        definitions=taxonomies();instructions=context()
        write_json(directory/'taxonomies.json',definitions)
        # Fixed paper/context/code hashes are kept independently of raw call data.
        for name,value in [('context.sha256',sha256(instructions.encode()).hexdigest()),
                           ('runner.sha256',sha256(Path(__file__).read_bytes()).hexdigest())]:
            p=directory/name
            if p.exists() and p.read_text()!=value:raise ValueError('Follow-up scientific inputs/code changed')
            p.write_text(value)
        rows=original_rows(runs);pilot=freeze_pilot(rows,directory)
        # Recover an accepted response only with its original baseline snapshot;
        # a half-written comparison is replayed without another paid call.
        for job in (directory/'jobs').iterdir():
            state=read(job/'state.json') if (job/'state.json').exists() else {}
            if state.get('state')=='running':
                if (job/'validated.json').exists():
                    saved=read(job/'validated.json');finish(directory,saved['row'],saved['baseline'],saved['snapshot'],saved['decision'],source)
                    (job/'validated.json').unlink(missing_ok=True)
                else:
                    write_json(job/'state.json',{'state':'interrupted','reason':'Preserve paid attempt; no automatic retry'})
                    compact(job)
        active={};stop=None;last_checkpoint=0;terminating=Event()
        previous={sig:signal.signal(sig,lambda *_:terminating.set()) for sig in (signal.SIGTERM,signal.SIGINT)}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while True:
                if (directory/'STOP').exists() or (directory.parent/'STOP').exists() or terminating.is_set():stop='Stop requested; active calls draining'
                rows=original_rows(runs);choices=candidates(rows,policy,pilot)
                for future,record in list(active.items()):
                    if not future.done():continue
                    row=future.result();baseline,snapshot,decision=record
                    job=directory/'jobs'/job_id(row['paper']['arxiv'])
                    saved={'row':row,'baseline':baseline,'snapshot':snapshot,'decision':decision}
                    write_json(job/'validated.json',saved)
                    finish(directory,row,baseline,snapshot,decision,source);(job/'validated.json').unlink(missing_ok=True)
                    if row.get('infrastructure'):stop=row['reason']
                    del active[future]
                waiting=0
                if not stop:
                    # Flagged scientific failures have priority over audit samples.
                    ordered=sorted(choices.items(),key=lambda item:(not ('flagged' in item[1][1]),item[0]))
                    for identifier,(baseline,decision) in ordered:
                        if len(active)>=workers:break
                        job=directory/'jobs'/job_id(identifier)
                        if (job/'state.json').exists():continue
                        try:body,provenance=read_source(identifier,corpus)
                        except (AwaitingSource,ValueError,OSError):waiting+=1;continue
                        paper=deepcopy(baseline['paper']);paper.setdefault('id','arxiv-'+job_id(identifier).replace('.','-'))
                        snapshot=comparison_snapshot(identifier,baseline,source)
                        job.mkdir(parents=True,exist_ok=True)
                        write_json(job/'baseline.json',{'baseline':baseline,'snapshot':snapshot,'decision':decision})
                        write_json(job/'state.json',{'state':'running','paper':paper,'selection':decision})
                        future=pool.submit(run_worker,job,paper,body,provenance,instructions,definitions,
                            {'model':MODEL,'reasoning':'medium','timeout':900,'executable':executable})
                        active[future]=(baseline,snapshot,decision)
                if time.monotonic()-last_checkpoint>10:
                    states=Counter();usage=Counter()
                    for p in (directory/'jobs').glob('*/state.json'):states[read(p)['state']]+=1
                    for p in (directory/'jobs').glob('*/metrics.json'):
                        u=read(p).get('usage')
                        if u:usage.update(u)
                    write_json(directory/'status.json',{'phase':'draining' if stop else 'running',
                        'pid':os.getpid(),'model':MODEL,'workers':workers,'counts':dict(states),'usage':dict(usage),
                        'selected':len(choices),'source_repair_required':sum(audit_decision(i,r)=='source_repair' for i,r in rows.items()),
                        'waiting_for_source':waiting,'reason':stop,'updated':now()});last_checkpoint=time.monotonic()
                all_finished=all((run/'status.json').exists() and read(run/'status.json')['phase'] in ('completed','stopped') for run in runs)
                if not active and (stop or once or all_finished):break
                if active:wait(active,timeout=2,return_when=FIRST_COMPLETED)
                else:time.sleep(10)
        for sig,handler in previous.items():signal.signal(sig,handler)
        summary=read(directory/'status.json');summary.update(phase='stopped' if stop else 'completed',reason=stop,updated=now())
        write_json(directory/'status.json',summary);return summary


def main():
    p=ArgumentParser(description=__doc__);p.add_argument('runs',nargs='+');p.add_argument('--run-dir',required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--workers',type=int,default=4)
    p.add_argument('--audit-fraction',type=float,default=0.02);p.add_argument('--once',action='store_true')
    a=p.parse_args();print(json.dumps(run(a.runs,a.run_dir,workers=a.workers,audit_fraction=a.audit_fraction,execute=a.execute,once=a.once),indent=2))


if __name__=='__main__':main()
