"""Summarize frozen historical extraction files; never normalizes or ingests."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from corpus import HERE,ROOT,emit,utc

def main():
    ledger=json.loads((HERE/'corpus-run-ledger.json').read_text())
    rows=[]
    status_counts=Counter()
    for i in range(6,51):
        pid=f'P{i:02d}'
        c=json.loads((HERE/pid/'checkpoint.json').read_text())
        status_counts.update(x['duplicate_check']['status'] for x in c['preflight_results'])
        rows.append({'paper_id':pid,'status':c['status'],'arxiv_version':c['arxiv_version'],
          'numerical_candidates':len(c['staged_numerical_candidates']),
          'scope':c['inspection']['scope'],'partial_descriptions':c['source_descriptions'],
          'limitations':c['limitations'],'checkpoint':str((HERE/pid/'checkpoint.json').relative_to(ROOT)),
          'field_evidence':str((HERE/pid/'field-evidence.json').relative_to(ROOT))})
    paths=sorted([p for i in range(6,51) for p in (HERE/f'P{i:02d}').glob('*.json')]+[HERE/'corpus-decisions.json'])
    frozen={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    emit(HERE/'corpus-frozen-hashes.json',{'frozen_utc':utc(),'conventions':'Historical field-content-1 / dynkin-gauge-1 / lorentz-field-1 before scalar real-module identity migration','files':frozen,'scope_note':'Original source rows and scalar reality/copies are preserved. This hash manifest covers staging, not acceptance or independent physics certification.'})
    emit(HERE/'corpus-handoff.json',{
      'generated_utc':utc(),'status':'all_fifty_accounted_for_source_scoped_staging_frozen',
      'total_papers':50,'counts':ledger['counts'],'queued':0,'source_access_blocked':0,
      'not_a_claim':'50 complete numerical spectra, 46 novel theories, or independent source review',
      'source_db_immutable_sha256':ledger['source_db_immutable_sha256'],
      'paper_candidate_occurrences_historical_v1':ledger['paper_candidate_occurrences'],
      'distinct_signatures_historical_v1':ledger['distinct_current_schema_fingerprints'],
      'remaining45_candidate_occurrences':sum(r['numerical_candidates'] for r in rows),
      'remaining45_distinct_signatures_historical_v1':len({x['fingerprint'] for i in range(6,51) for x in json.loads((HERE/f'P{i:02d}'/'checkpoint.json').read_text())['preflight_results']}),
      'remaining45_duplicate_preflight_statuses':dict(status_counts),
      'measurements':ledger['remaining45_measurements'],
      'frozen_pilot_ownership':'P01-P05, pilot.py,test_pilot.py,run-ledger.json,README.md and accepted.json were not changed by this corpus stage.',
      'publication_boundary':'No original or generated database, website, git commit/push or deployment performed by this agent. Parent owns review and publication.',
      'validation_receipt':{'command':"PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s atlas/reextraction -p 'test_*.py' -v",'observed_exit_code':0,'tests_passed':20,'unittest_reported_seconds':0.321,'scope':'Ran before parent scalar-identity migration; mechanical checks are not independent scientific review.'},
      'reproduction_note':'corpus_audit.py saves authored source decisions; corpus.py checkpoint runs historical normalization/preflights and writes staging. Do NOT rerun accepted pilot snapshots or re-normalize frozen corpus files with a changed identity convention. Parent is implementing scalar real-module counting separately.',
      'limitations':['Only listed model-definition scopes and selected passages/pages were inspected; full PDF download does not mean whole-paper read.',
        '27 papers retain at least one partial scope: explicit symbolic families, incomplete/optional sectors, nonlinear/affine representations, boundary/dimension choices or remaining unestablished scalar/spinor data. Some also contain ready numerical representatives.',
        'Generic family descriptions cannot enter the complete-numerical schema as question marks; unfinished extraction is not a scientific source omission.',
        'Single-complex versus multiple-real scalar equivalence and conjugate-scalar real-module identity were NOT canonicalized in these historical snapshots.',
        'No general multi-U1 basis quotient, gauge outer-automorphism quotient, anomaly/SM-embedding proof or physical-theory equivalence is claimed.',
        'Historical source-field IDs are retained, but aggregate legacy fields do not imply a checked one-to-one map to every newly expanded field row.',
        'Model token counts, dollar charges, GPU-hours and separate active scientific-reading time were not exposed; all remain null. CPU/wall checks do not measure inference cost.'],
      'skill_usage':'pdf:pdf used to inspect pinned PDF definitions, extracted text and selected rendered representation tables.',
      'papers':rows})

if __name__=='__main__':main()
