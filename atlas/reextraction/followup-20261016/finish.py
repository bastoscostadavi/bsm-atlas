"""Freeze an additive research handoff and explicit fifty-paper remaining map."""
from collections import Counter
from stage import *

NEW_READS={
 'P09':'SectionVIII Eq42 and full adjoining paragraphs re-read; actual PDFp7 visually inspected at /tmp/octet-P09-07.png. Indexed Pauli/adjoint contractions resolve disclosed prose misprints.',
 'P11':'Sections1.1,1.4,1.7,1.8,1.11-1.13,2.1 and3.3 vector-EFT caveat read; SU5 definition pp18-22 and actual table/tensor context checked. Auxiliary cited ref74 AppendixA/TableI inspected for adjoint scalar counting.',
 'P18':'SectionII inventory/tensor/Yukawa definitions and SectionIII TableI re-read; actual PDFpp2-3 visually inspected. Real24 counting no longer left unestablished.',
 'P19':'SectionsIIA-C andIVA-B, TableII, scalar coordinate counts,complex10 contrast, source b=-12 re-read; actual PDFpp4,12 visually inspected. Explicit D5/A4/Z weight map and count derivations supplied.',
 'P22':'Section2.6 Eqs2.66-2.68 and footnote13 re-read; actual PDFp46 visually inspected. Operator-sector fields filled, no invented GUT-breaking model.',
 'P28':'Introduction SUSY statement, Section3.2, Section7 full/reduced heavy quarks and AppendixA heavy-lepton alternatives re-read. Quark high-energy example is SUSY, so scalar partners must not be dropped. Source AppendixA permits six E-pairs or a reduced three-pair lepton extension; full quark/lepton variant must be selected explicitly, not silently combined.'
}

def category(d):
    status=d.get('value_status','')
    if 'not_extracted' in status:return 'unfinished_agent_extraction_not_source_omission'
    if 'symbolic' in status or 'family' in status:return 'explicit_family_or_unselected_parameters_not_unknown'
    if 'nonlinear' in status or 'affine' in status:return 'nonlinear_or_affine_representation_scope'
    if 'not_specified' in status:return 'source_omission_or_explicit_scope_boundary'
    return 'source_scoped_sector_or_unselected_completion'

def main():
    historical_count=frozen_unchanged()
    m=load(HERE/'integration-manifest.json');entries=m['entries']
    accepted=load(ROOT/'atlas/reextraction/accepted-followup.json')['reviews']
    for review in accepted:
        e=next(x for x in entries if x['target_entry_id']==review['entry'])
        if e['fingerprint']!=review['fingerprint']:raise AssertionError(review['entry'])
        for item in review['files'].values():
            if sha256((ROOT/item['path']).read_bytes()).hexdigest()!=item['sha256']:raise AssertionError(item['path'])
        e.update(accepted_or_published=True,acceptance_manifest='atlas/reextraction/accepted-followup.json',publication_commit='c2fb130',publication_status='parent_confirmed_pushed')
    emit(HERE/'integration-manifest.json',m)
    ready={x['target_entry_id'] for x in entries if x['status']=='ready_for_curator_integration'}
    staged={x['target_entry_id']:x for x in entries}
    public=load(ROOT/'website/field-catalogue.json')['entries']
    previously_resolved={x['id'] for x in public if x['identity']['status']!='unresolved'}
    corpus=load(HISTORICAL/'corpus-run-ledger.json')['papers']
    rows=[]
    for p in corpus:
        pid=p['paper_id'];c=load(HISTORICAL/pid/'checkpoint.json')
        linked=[e for e in public if pid in e['paperIds']]
        followups=[]
        for e in entries:
            ids=[e['paper_id']]
            if e.get('source_candidate_path'):ids=load(ROOT/e['source_candidate_path']).get('paper_ids',ids)
            if pid in ids:followups.append({'target_entry_id':e['target_entry_id'],'status':e['status'],'normalized_candidate_path':e.get('normalized_candidate_path'),'evidence_path':e['evidence_path'],'limitations':e['limitations']})
        pending=[]
        for e in linked:
            if e['id'] in ready or e['id'] in previously_resolved:continue
            ds=[d for d in c.get('source_descriptions',[]) if e['id']==d.get('target_entry_id') or e['id'] in d.get('target_entry_ids',[])]
            if e['id'] in staged:
                reason=staged[e['id']]['limitations'];kind='source_sector_filled_full_inventory_not_specified'
            elif ds:reason=[d.get('reason') for d in ds if d.get('reason')];kind=category(ds[0])
            else:reason=['Refer to frozen scope/claims and full original source field inventory; no additional complete candidate staged in this followup.'];kind='requires_targeted_source_scope_review'
            pending.append({'target_entry_id':e['id'],'category':kind,'exact_remaining_limitations':reason,'source_descriptions':ds,'source_field_ids':[f['sourceFieldId'] for v in e['variants'] for r in v['regimes'] for f in r['fields']],'next_action':'Retain source scope. Resolve the specified missing choice/fact or use a typed partial/family representation; do not insert guessed numbers.'})
        residual_families=[d for d in c.get('source_descriptions',[]) if ('symbolic' in d.get('value_status','') or 'family' in d.get('value_status','')) and (d.get('target_entry_id') in ready or any(t in ready for t in d.get('target_entry_ids',[])))]
        rows.append({'paper_id':pid,'arxiv_version':p['arxiv_version'],'historical_inspection_status':p['status'],'source_check_in_this_followup':'new_definition_passages_reread' if pid in NEW_READS else 'frozen_source_checks_reused_for_staging' if followups else 'no_new_source_reinspection','new_inspection_note':NEW_READS.get(pid),'followup_entries':followups,'remaining_entry_scopes':pending,'remaining_generic_or_alternative_scopes_even_with_ready_numeric_member':residual_families,'reference_only_no_bsm_row_expected':p['status']=='reference_only_scoped_reextraction','frozen_checkpoint_path':p['checkpoint'],'whole_paper_read_claimed':False})
    remaining_ids={x['target_entry_id'] for r in rows for x in r['remaining_entry_scopes']}
    for row in rows:
        for e in row['followup_entries']:e['accepted_or_published']=staged[e['target_entry_id']]['accepted_or_published']
    emit(HERE/'remaining-work-by-paper.json',{'generated_utc':utc(),'total_seed_papers':50,'papers':rows,'remaining_target_entry_count':len(remaining_ids),'remaining_target_entries':sorted(remaining_ids),'note':'Source-scoped completeness, source omissions, explicit families and unfinished agent extraction are distinct. A fixed ready representative does not erase its generic family/regime alternatives.'})
    measurements=[e['measurement'] for e in entries]
    emit(HERE/'handoff.json',{'generated_utc':utc(),'status':'frozen_followup_research_handoff_not_automatic_public_acceptance','counts':{'staged_full_numerical_candidates':len(ready),'distinct_numerical_fingerprints':len({e['fingerprint'] for e in entries if e.get('fingerprint')}),'explicitly_filled_partial_sectors':sum(e['status']=='source_sector_filled_full_inventory_not_specified' for e in entries),'remaining_target_entry_scopes_not_full_staged':len(remaining_ids),'newly_reread_seed_papers':len(NEW_READS),'new_auxiliary_sources':1,'ready_candidates_reusing_frozen_source_checks_without_new_independent_reread':sum('source_review_reused_from_frozen_checkpoint' in load(ROOT/e['evidence_path']) for e in entries),'seed_papers_accounted_for':50},
      'new_read_papers':NEW_READS,'auxiliary_source':{'id':'AUX-P11-ref74','arxiv_version':'hep-ph/0504276v1','url':'https://arxiv.org/pdf/hep-ph/0504276v1','local_pdf':'atlas/reextraction/followup-20261016/sources/hep-ph_0504276v1.pdf','sha256':sha256((HERE/'sources/hep-ph_0504276v1.pdf').read_bytes()).hexdigest(),'bytes':(HERE/'sources/hep-ph_0504276v1.pdf').stat().st_size,'observed_download_command_wall_seconds':0.183267834,'retrievals':1,'retries':0,'seed_corpus_expanded':False},
      'original_audit_files_verified_unchanged':historical_count,'original_source_db_sha256':m['source_db_sha256'],
      'tests':{'command':'PYTHONDONTWRITEBYTECODE=1 python3 atlas/reextraction/followup-20261016/test_followup.py -v','passed':6,'observed_exit_code':0,'reported_unittest_seconds':0.364,'meaning':'Data/convention/source-map checks, not independent physics certification.'},
      'measurement':{'deterministic_staging_and_preflight_wall_seconds_sum':sum(x['deterministic_preflight_and_staging_wall_seconds'] for x in measurements),'child_cpu_seconds_sum':sum(x['child_cpu_seconds'] for x in measurements),'input_tokens':None,'output_tokens':None,'api_dollars':None,'gpu_hours':None,'active_scientific_reading_seconds':None},
      'key_resolutions':['Four SU5 inventories completed with mapped inherited fields, scalar-count evidence and exact tensors; parent owns acceptance.','P22SU5-RPV and SO10 scalar-only entries are genuine sectors, not manufactured full models.','SO10 full SectionIV complex10 model now has explicit spinor-node and scalar/count derivations.','Four vector-LQ EFTs are finite source-defined inventories; absence of a renormalizable UV completion does not block their stated EFT scope.','P09triplet extension notation conflicts resolved from indexed invariant, while misprints remain disclosed.','31additional full candidate inputs reuse actual frozen source checks and add explicit legacy-container/component maps; this is not a second independent reread.','KSVZ duplicate labelQ was disambiguated only in the additive copy to Q_KSVZ; original field rows/fingerprints untouched.'],
      'limits':['Staged candidates require curator review and explicit public acceptance. This agent did not mutate original/generated DBs or website, commit or push.','The four SU5 tranche files were held stable while parent integrated them. Extraction-stage accepted_or_published=false is a historical stage statement, not a claim that parent never publishes.','Scalar real-module copies usefield-content-2; source reality/counting are preserved. No anomaly/viability gate.','No full inventory is fabricated for an operator sector, free-rank family, affine shift field, missing source count or unselected completion.','Exact legacy IDs map old containers to newly expanded rows. Declared inherited baseline rows with no old field ID say so, rather than inventing IDs.','Model token/cost/GPU and active-reading telemetry are unavailable and remain null. Retrieval and deterministic CPU timings are not inference cost.'],
      'integration_manifest':'atlas/reextraction/followup-20261016/integration-manifest.json','remaining_work_map':'atlas/reextraction/followup-20261016/remaining-work-by-paper.json'})
    report=load(HERE/'handoff.json')
    report['counts']['full_numerical_candidates_produced']=len(ready)
    report['counts']['accepted_published_candidates']=sum(e['accepted_or_published'] for e in entries)
    report['counts']['staged_full_numerical_candidates']=sum(e['status']=='ready_for_curator_integration' and not e['accepted_or_published'] for e in entries)
    report['accepted_public_intake']={'entries':[r['entry'] for r in accepted],'acceptance_manifest':'atlas/reextraction/accepted-followup.json','parent_confirmed_push':'c2fb130','other_candidates_are_staging_only':True}
    report['tests']['reported_unittest_seconds']=0.360
    report['limits'][1]='Four SU5 candidates are now accepted/published by parent at c2fb130; integration-manifest.json marks these four true and the other candidates false. Their hash-pinned source/evidence files were not altered.'
    emit(HERE/'handoff.json',report)
    paths=sorted(p for p in HERE.iterdir() if p.is_file() and p.name!='frozen-files.json')
    emit(HERE/'frozen-files.json',{'frozen_utc':utc(),'files':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths},'note':'Additive followup source/candidate/evidence and handoff snapshot. Ignored PDFs are separately hash-pinned in source evidence. Do not overwrite accepted source artifacts.'})

if __name__=='__main__':main()
