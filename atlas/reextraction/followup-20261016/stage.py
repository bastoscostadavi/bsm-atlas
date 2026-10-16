"""Additive follow-up intake: source evidence and explicit legacy-field maps.

Never writes historical extraction files or accepted/public catalogue data.
"""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
HISTORICAL=HERE.parent
sys.path.insert(0,str(ROOT/'atlas'))
from scalar_conventions import real_scalar

def utc():return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def emit(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def load(path):return json.loads(path.read_text())

def field(label,weight,kind='F',copies=1,reality=None,factor='unified'):
    return {'label':label,'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']] if kind=='S' else [['1/2','0']]},'reality':reality or ('complex' if kind=='S' else 'none'),'copies':copies,'gauge_representations':{factor:{'dynkin':weight}}}
def spec(pid,name,fields):return {'schema_version':'field-content-1','inventory_complete':True,'paper_ids':[pid],'name':name,'gauge_factors':[{'id':'unified','family':'A','rank':4}],'matter':fields}

def source(source_id,pdf,text,sections,text_pages,visual_pages=None,url=None):
    return {'id':source_id,'local_pdf':str(pdf.relative_to(ROOT)),'sha256':sha256(pdf.read_bytes()).hexdigest(),'bytes':pdf.stat().st_size,'local_text':str(text.relative_to(ROOT)),'sections':sections,'text_passages_pdf_pages':text_pages,'visually_inspected_pdf_pages':visual_pages or [],'whole_paper_read':False,'url':url}

def stage(entry,pid,version,raw,evidence,mapping,status='ready_for_curator_integration',limitations=None,regime=None):
    started=utc();tick=time.perf_counter();cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
    evidence.update({'target_entry_id':entry,'paper_id':pid,'arxiv_version':version,'review':'agent_source_checked_not_independent_physics_review','source_field_mapping':mapping,'limitations':limitations or [],'description_regime':regime,'no_anomaly_or_viability_gate':True})
    evidence_path=HERE/f'{entry}-evidence.json';emit(evidence_path,evidence)
    result={'target_entry_id':entry,'paper_id':pid,'arxiv_version':version,'status':status,'source_field_mapping':mapping,'evidence_path':str(evidence_path.relative_to(ROOT)),'limitations':limitations or [],'description_regime':regime,'accepted_or_published':False,'source_legacy_ids_preserved':True}
    if raw is not None:
        emit(HERE/f'{entry}-source-candidate.json',raw)
        db=ROOT/'website/downloads/field-catalogue.sqlite'
        command=[sys.executable,str(ROOT/'atlas/prepare_entry.py'),str(HERE/f'{entry}-source-candidate.json'),'--database',str(db)]
        prepared=load_result(command)
        emit(HERE/f'{entry}-preflight.json',prepared)
        normalized=prepared['normalized_entry'];emit(HERE/f'{entry}-normalized.json',normalized)
        strict=load_result([sys.executable,str(ROOT/'atlas/prepare_entry.py'),str(HERE/f'{entry}-normalized.json'),'--require-normalized','--database',str(db)])
        emit(HERE/f'{entry}-require-normalized.json',strict)
        duplicate=load_result([sys.executable,str(ROOT/'atlas/check_entry.py'),str(HERE/f'{entry}-normalized.json'),'--database',str(db)])
        emit(HERE/f'{entry}-duplicates.json',duplicate)
        result.update({'source_candidate_path':str((HERE/f'{entry}-source-candidate.json').relative_to(ROOT)),'normalized_candidate_path':str((HERE/f'{entry}-normalized.json').relative_to(ROOT)),'fingerprint':prepared['fingerprint'],'duplicate_status':duplicate['status'],'duplicate_matches':duplicate['matches'],'reconciliation':'Reuse/correct this known target entry after curator review; never infer novelty from an incomplete old row.'})
        mapped={x['candidate_label']:x for x in mapping if x.get('candidate_label')}
        if set(mapped)!={f['label'] for f in raw['matter']}:raise ValueError(f'{entry}: missing or extraneous source-field mapping')
        rows=[]
        for f in raw['matter']:
            rows.append({'source_row':f,'normalized_components':[n for n in normalized['matter'] if n['label']==f['label']],'mapping':mapped[f['label']]})
        emit(HERE/f'{entry}-field-evidence.json',{'target_entry_id':entry,'source_locator_evidence':result['evidence_path'],'rows':rows,'scalar_convention':'scalar-real-modules-1','fermion_convention':'all identified4D Weyl LH, conjugating all factors','gauge_convention':'dynkin-gauge-1 Bourbaki/Sage finite Cartan'})
        result['field_evidence_path']=str((HERE/f'{entry}-field-evidence.json').relative_to(ROOT))
    current=resource.getrusage(resource.RUSAGE_CHILDREN)
    result['measurement']={'started_utc':started,'ended_utc':utc(),'deterministic_preflight_and_staging_wall_seconds':time.perf_counter()-tick,'child_cpu_seconds':current.ru_utime+current.ru_stime-cpu.ru_utime-cpu.ru_stime,'input_tokens':None,'output_tokens':None,'api_dollars':None,'gpu_hours':None,'active_source_reading_seconds':None}
    path=HERE/'integration-manifest.json';manifest=load(path) if path.exists() else {'run_id':'followup-20261016','original_audit_immutable':True,'entries':[],'source_db_sha256':sha256((ROOT/'atlas/atlas.sqlite').read_bytes()).hexdigest()}
    manifest['entries']=[r for r in manifest['entries'] if r['target_entry_id']!=entry]+[result]
    manifest['generated_utc']=utc();emit(path,manifest)
    return result

def load_result(command):
    p=subprocess.run(command,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return json.loads(p.stdout)

def mapping(label,ids,claims,basis='direct_source_field',model=None,regime=None):
    return {'candidate_label':label,'source_field_ids':ids,'source_model_id':model,'source_regime_id':regime,'claim_ids':claims,'mapping_basis':basis}

def frozen_unchanged():
    original=load(HISTORICAL/'corpus-frozen-hashes.json')['files']
    changed=[name for name,digest in original.items() if sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    if changed:raise AssertionError(changed)
    return len(original)

if __name__=='__main__':print(json.dumps({'historical_files_unchanged':frozen_unchanged()}))
