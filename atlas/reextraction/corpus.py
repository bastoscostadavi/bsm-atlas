#!/usr/bin/env python3
"""Resumable public-source acquisition/checkpointing for the remaining corpus.

No accepted atlas writes; extraction decisions are supplied separately in
corpus-decisions.json after reading actual pinned source passages.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
import resource
import sqlite3
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_HASH = 'd4dbf023b667fe810296c43c8f72e0d0b3f6559e66b344a2920c9e2e520e6c4c'
RUN = '2026-10-16-full-corpus-1'

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def emit(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def manifest():
    text = (ROOT/'BSM_ATLAS_SEED.md').read_text()
    sections = {m.group(1): {'title':m.group(2),'scope':m.group(3).strip()} for m in re.finditer(r'^### (P\d\d) — ([^\n]+)\n(.*?)(?=^### |^## Coverage|\Z)',text,re.M|re.S)}
    pattern = r'\| (P\d\d) \| \[([^]]+)\]\([^)]+\) \| ([^|]+) \| \[PDF\]\(([^)]+)\) \| `([^`]+)` \|'
    return {pid:{'paper_id':pid,'arxiv_version':version,'kind':kind.strip(),'pdf_url':url,'filename':filename,**sections[pid]} for pid,version,kind,url,filename in re.findall(pattern,text)}

def acquire(pid):
    item = manifest()[pid]
    folder = HERE/pid
    folder.mkdir(exist_ok=True)
    source = HERE/'sources'/item['filename']
    text = source.with_suffix('.txt')
    retrieval = folder/'retrieval.json'
    record = json.loads(retrieval.read_text()) if retrieval.exists() else {'paper_id':pid,'arxiv_version':item['arxiv_version'],'started_utc':utc(),'attempts':[]}
    if not source.exists():
        start=time.perf_counter()
        attempt={'url':item['pdf_url'],'started_utc':utc(),'method':'bounded_public_curl'}
        result=subprocess.run(['curl','-L','--fail','--connect-timeout','10','--max-time','45','-o',str(source),item['pdf_url']],capture_output=True,text=True)
        attempt.update({'ended_utc':utc(),'wall_seconds':time.perf_counter()-start,'returncode':result.returncode,'error':result.stderr[-1200:] if result.returncode else None})
        record['attempts'].append(attempt)
        if result.returncode:
            record['status']='blocked_source_access'
            emit(retrieval,record)
            return {'paper_id':pid,'status':record['status']}
    if source.read_bytes()[:4]!=b'%PDF':
        record['status']='blocked_not_pdf'
        emit(retrieval,record)
        return {'paper_id':pid,'status':record['status']}
    if not text.exists():
        conversion=subprocess.run(['pdftotext','-layout',str(source),str(text)],capture_output=True,text=True)
        record['text_conversion_stderr']=conversion.stderr[-2000:]
        record['text_conversion_returncode']=conversion.returncode
    info=subprocess.run(['pdfinfo',str(source)],capture_output=True,text=True,check=True).stdout
    pages=re.search(r'^Pages:\s+(\d+)',info,re.M)
    record.update({'status':'source_available_not_yet_reextracted','ended_utc':utc(),'bytes':source.stat().st_size,'sha256':sha256(source.read_bytes()).hexdigest(),'local_pdf':str(source.relative_to(ROOT)),'local_text':str(text.relative_to(ROOT)),'pdf_pages':int(pages[1]) if pages else None,'pdfinfo':info,'text_bytes':text.stat().st_size if text.exists() else None})
    emit(retrieval,record)
    return {'paper_id':pid,'status':record['status'],'bytes':record['bytes'],'pages':record['pdf_pages']}

def old_records(pid):
    with sqlite3.connect((ROOT/'atlas/atlas.sqlite').as_uri()+'?mode=ro',uri=True) as connection:
        connection.row_factory=sqlite3.Row
        models=[dict(r) for r in connection.execute('select distinct model_id,model_revision from paper_theory_links where paper_version_id=?',(pid,))]
        # Some source schemas use full version PKs; resolve through paper IDs.
        if not models:
            models=[dict(r) for r in connection.execute('select distinct l.model_id,l.model_revision from paper_theory_links l join paper_versions v on v.paper_version_id=l.paper_version_id where v.paper_id=?',(pid,))]
        fields=[]
        for model in models:
            for field in connection.execute('select * from theory_fields where model_id=? and model_revision=?',(model['model_id'],model['model_revision'])):
                f=dict(field)
                f['representations']=[dict(r) for r in connection.execute('select * from theory_field_representations where field_id=?',(f['field_id'],))]
                fields.append(f)
    public=json.loads((ROOT/'website/field-catalogue.json').read_text())
    entries=[{'entry_id':e['id'],'name':e['name'],'identity_status':e['identity']['status'],'source_model_ids':[v['id'] for v in e['variants']]} for e in public['entries'] if pid in e['paperIds']]
    return {'review_status':'legacy_unchecked_not_freshly_verified','paper_id':pid,'source_models':models,'public_entries':entries,'source_fields':fields}

def refresh_queue():
    old=json.loads((HERE/'queue.json').read_text())
    for item in old['papers']:
        pid=item['paper_id']
        checkpoint=HERE/pid/'checkpoint.json'
        if checkpoint.exists():
            c=json.loads(checkpoint.read_text())
            item['reextraction_status']=c['status']
            item['checkpoint']=str(checkpoint.relative_to(ROOT))
            item['next_action']='Curator review of staged source evidence; no automatic ingestion.'
    old['generated_utc']=utc()
    emit(HERE/'queue.json',old)

def ledger():
    papers=[]
    for pid,item in manifest().items():
        path=HERE/pid/'checkpoint.json'
        if path.exists():
            c=json.loads(path.read_text())
            papers.append({'paper_id':pid,'arxiv_version':item['arxiv_version'],'status':c['status'],'checkpoint':str(path.relative_to(ROOT)),
                           'source':c.get('source'),'inspection':c.get('inspection'),
                           'measurement':c.get('measurement'),'candidate_count':len(c.get('staged_numerical_candidates',[]))})
        else:
            papers.append({'paper_id':pid,'arxiv_version':item['arxiv_version'],'status':'queued_not_reextracted'})
    counts={}
    for p in papers:counts[p['status']]=counts.get(p['status'],0)+1
    staged=[c for pid in manifest() if (HERE/pid/'checkpoint.json').exists() for c in json.loads((HERE/pid/'checkpoint.json').read_text()).get('staged_numerical_candidates',[])]
    fingerprints={}
    for pid in manifest():
        folder=HERE/pid
        for path in folder.glob('*-preflight.json'):
            result=json.loads(path.read_text())
            if 'fingerprint' in result:fingerprints.setdefault(result['fingerprint'],[]).append(str(path.relative_to(ROOT)))
    remaining=[p for p in papers if p['paper_id']>='P06']
    sources=[p['source'] for p in remaining if p.get('source')]
    observed_checks=[]
    for p in remaining:
        path=HERE/p['paper_id']/'preflight-runs.json'
        if path.exists():observed_checks.extend(json.loads(path.read_text()))
    emit(HERE/'corpus-run-ledger.json',{'run_id':RUN,'generated_utc':utc(),'total_papers':50,'counts':counts,
         'all_papers_accounted_for':len(papers)==50,'queued':counts.get('queued_not_reextracted',0),
         'paper_candidate_occurrences':len(staged),'distinct_current_schema_fingerprints':len(fingerprints),
         'cross_paper_fingerprint_groups':{k:v for k,v in fingerprints.items() if len(v)>1},
         'remaining45_measurements':{'source_pdf_bytes':sum(s['bytes'] for s in sources),
           'retrieval_attempts':sum(len(s['attempts']) for s in sources),'failed_retrieval_attempts':sum(a['returncode']!=0 for s in sources for a in s['attempts']),
           'retrieval_command_wall_seconds_sum_not_parallel_elapsed':sum(a['wall_seconds'] for s in sources for a in s['attempts']),
           'recorded_preflight_run_count':len(observed_checks),'recorded_preflight_wall_seconds':sum(m['preflight_and_checkpoint_wall_seconds'] for m in observed_checks),
           'recorded_child_cpu_seconds':sum(m['child_user_cpu_seconds']+m['child_system_cpu_seconds'] for m in observed_checks),
           'scientific_extraction_active_seconds':None,'model_input_tokens':None,'model_output_tokens':None,'api_dollars':None,'gpu_hours':None},
         'tokens':None,'api_dollars':None,'gpu_hours':None,'source_db_immutable_sha256':SOURCE_HASH,
         'note':'Completed scopes, actual source omissions, symbolic families and unfinished extraction stay distinct. No accepted database writes. UTC observation windows are not inference compute; no fabricated cost telemetry.',
         'papers':papers})

def checkpoint(pid):
    decisions=json.loads((HERE/'corpus-decisions.json').read_text())
    data=decisions[pid]
    folder=HERE/pid
    retrieval=json.loads((folder/'retrieval.json').read_text())
    assert sha256((ROOT/'atlas/atlas.sqlite').read_bytes()).hexdigest()==SOURCE_HASH
    start=time.perf_counter()
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    results=[]
    field_evidence=[]
    legacy=old_records(pid)
    claim_map={c['id']:c for c in data['claims']}
    for candidate in data.get('candidates',[]):
        stem=candidate['stem']
        emit(folder/f'{stem}-source-candidate.json',candidate['spec'])
        cmd=[sys.executable,str(ROOT/'atlas/prepare_entry.py'),str(folder/f'{stem}-source-candidate.json'),'--database',str(ROOT/'website/downloads/field-catalogue.sqlite')]
        p=subprocess.run(cmd,capture_output=True,text=True,check=True)
        prepared=json.loads(p.stdout)
        emit(folder/f'{stem}-preflight.json',prepared)
        emit(folder/f'{stem}-normalized-candidate.json',prepared['normalized_entry'])
        strict=subprocess.run([sys.executable,str(ROOT/'atlas/prepare_entry.py'),str(folder/f'{stem}-normalized-candidate.json'),'--require-normalized','--database',str(ROOT/'website/downloads/field-catalogue.sqlite')],capture_output=True,text=True,check=True)
        emit(folder/f'{stem}-require-normalized.json',json.loads(strict.stdout))
        check=subprocess.run([sys.executable,str(ROOT/'atlas/check_entry.py'),str(folder/f'{stem}-normalized-candidate.json'),'--database',str(ROOT/'website/downloads/field-catalogue.sqlite')],capture_output=True,text=True,check=True)
        emit(folder/f'{stem}-duplicate-check.json',json.loads(check.stdout))
        target=candidate.get('target_existing_entry_id')
        target_models={m for e in legacy['public_entries'] if e['entry_id']==target for m in e['source_model_ids']}
        linked_fields=[{'field_id':f['field_id'],'source_model_id':f['model_id'],'source_model_revision':f['model_revision'],'regime_id':f['regime_id'],'field_label':f['field_label']} for f in legacy['source_fields'] if f['model_id'] in target_models]
        field_evidence.append({'candidate_stem':stem,'target_existing_entry_id':target,
            'legacy_inventory_reference':linked_fields,
            'legacy_mapping_note':'These are original source-field IDs in the target model inventory, retained for curation. No unverified one-to-one mapping between legacy aggregate fields and newly expanded rows is asserted.',
            'fields':[{'source_coordinate_row':f,
                       'normalized_rows':[n for n in prepared['normalized_entry']['matter'] if n['label']==f['label']],
                       'claim_ids':candidate['field_evidence_claim_ids'][f['label']],
                       'attribute_evidence_claim_ids':{a:candidate['field_evidence_claim_ids'][f['label']] for a in ['gauge_algebra','nonabelian_irreps','source_charge','copies','lorentz_and_reality','conversion']},
                       'claims':[claim_map[x] for x in candidate['field_evidence_claim_ids'][f['label']]],
                       'derivation':'Exact highest weights use dynkin-gauge-1. prepare_entry expands identified 4D Dirac/RH fermions into LH conjugates of every factor, and applies one primitive positive charge unit over the entire inventory. Retain source-coordinate row above; scalar-realification equivalence is NOT implemented.'}
                      for f in candidate['spec']['matter']]})
        results.append({'stem':stem,'fingerprint':prepared['fingerprint'],'target_existing_entry_id':target,'duplicate_check':prepared['duplicate_check'],'candidate':f'{stem}-normalized-candidate.json',
            'reconciliation_action':'Link source to exact-match existing entry; do not add duplicate.' if prepared['duplicate_check']['matches'] else 'Correct/reuse the known existing target after scientific review; unmatched old incomplete content is not a novelty claim.'})
    emit(folder/'legacy-records.json',legacy)
    emit(folder/'field-evidence.json',{'paper_id':pid,'arxiv_version':manifest()[pid]['arxiv_version'],'source_sha256':retrieval['sha256'],'candidates':field_evidence,'partial_source_descriptions':data['source_descriptions'],'legacy_source_models':legacy['source_models'],'legacy_records_file':'legacy-records.json','independent_review_performed':False})
    evidence={k:v for k,v in data.items() if k!='candidates'}
    evidence['inspection']['text_pages_with_claim_anchors']=sorted({p for c in data['claims'] for p in c.get('locator',{}).get('pdf_pages',[])})
    evidence['inspection']['coverage_note']='These are passages and model-definition sections actually inspected, not a claim that every sentence on each page or the entire PDF was read. Field claims are retained separately in field-evidence.json; legacy records remain unchecked reference material.'
    cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
    evidence.update({'paper_id':pid,'arxiv_version':manifest()[pid]['arxiv_version'],'run_id':RUN,
       'source':retrieval,'legacy_targets':{'source_model_ids':[m['model_id'] for m in legacy['source_models']],'source_field_ids':[f['field_id'] for f in legacy['source_fields']],'public_entry_ids':[e['entry_id'] for e in legacy['public_entries']]},
       'staged_numerical_candidates':[r['candidate'] for r in results],'preflight_results':results,
       'database_write_performed':False,'independent_review_performed':False,
       'measurement':{'checkpoint_utc':utc(),'source_access_started_utc':retrieval['started_utc'],'source_access_ended_utc':retrieval['ended_utc'],'scientific_read_started_observed_utc':None,'scientific_extraction_active_seconds':None,'source_access_command_wall_seconds':sum(a['wall_seconds'] for a in retrieval['attempts']),'preflight_and_checkpoint_wall_seconds':time.perf_counter()-start,'child_user_cpu_seconds':cpu.ru_utime-usage.ru_utime,'child_system_cpu_seconds':cpu.ru_stime-usage.ru_stime,'input_tokens':None,'cached_input_tokens':None,'output_tokens':None,'api_dollars':None,'gpu_hours':None,'note':'Access window and checkpoint timestamps are observations, not model compute; separate active scientific reading time is not instrumented.'}})
    runs_path=folder/'preflight-runs.json'
    runs=json.loads(runs_path.read_text()) if runs_path.exists() else []
    previous_path=folder/'checkpoint.json'
    if not runs and previous_path.exists():runs.append(json.loads(previous_path.read_text())['measurement'])
    runs.append(evidence['measurement'])
    emit(runs_path,runs)
    emit(folder/'checkpoint.json',evidence)
    refresh_queue()
    ledger()
    print(json.dumps({'paper':pid,'status':evidence['status'],'candidates':len(results)},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['acquire','checkpoint','ledger'])
    parser.add_argument('papers',nargs='*')
    args=parser.parse_args()
    if args.action=='acquire':
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(acquire,args.papers):print(json.dumps(result))
    elif args.action=='checkpoint':
        for pid in args.papers:checkpoint(pid)
    else:
        refresh_queue();ledger()
