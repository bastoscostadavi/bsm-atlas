#!/usr/bin/env python3
"""Read-only pre-ingestion normalization of a complete numerical extraction.

The extraction agent must establish source facts and provenance first. This
command emits the normalized candidate that may be considered for ingestion;
it never writes the original or generated database. Unknown/symbolic inputs
remain outside this complete numerical path, not silently guessed or erased.
"""
import argparse
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from catalogue_identity import normalize_spec,primitive_charge_scale,canonicalize,IncompleteContent
from check_entry import check

def prepare(spec,database=None):
    original=deepcopy(spec)
    normalized=normalize_spec(spec)
    transformations=[]
    for a in normalized['gauge_factors']:
        if a['family']!='U1':continue
        # Charge conjugation changes signs, never the positive common unit.
        scale=primitive_charge_scale(f['gauge_representations'][a['id']]['charge'] for f in original['matter'])
        transformations.append({'factor_id':a['id'],'normalization':'primitive_integer_full_inventory','positive_source_scale':str(scale) if scale is not None else None,'generator_orientation':'retained','note':'All-zero assignments have no primitive nonzero unit.' if not any(Fraction(f['gauge_representations'][a['id']]['charge']) for f in normalized['matter']) else 'Scale may be combined with charge conjugation when converting source fermions.'})
    result={'status':'normalized_candidate_requires_source_review','normalized_entry':normalized,'transformations':transformations,'fingerprint':canonicalize(normalized)['fingerprint'],'action':'Verify source evidence for every assignment and run duplicate reconciliation before ingestion. This tool is not a database writer or a source-extraction certificate.'}
    if database is not None:result['duplicate_check']=check(normalized,database)
    if spec!=original:raise AssertionError('Preparation mutated the extraction input')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--database',type=Path,help='Also run the read-only duplicate check')
    parser.add_argument('--require-normalized',action='store_true',help='Reject inputs needing mathematical normalization; usable as a pre-write assertion')
    args=parser.parse_args()
    try:
        candidate=json.loads(args.candidate.read_text())
        result=prepare(candidate,args.database)
        if args.require_normalized and candidate!=result['normalized_entry']:
            raise IncompleteContent('Candidate needs normalization; use normalized_entry and preserve source notation in provenance before ingestion')
    except (IncompleteContent,KeyError,ValueError,TypeError,AttributeError,IndexError) as error:
        print(json.dumps({'status':'blocked_before_ingestion','reason':str(error),'action':'Complete or correct the extraction. Explicit source omissions/free parameters require their separate partial/family representation, not invented numeric values.'},ensure_ascii=False,indent=2))
        raise SystemExit(2)
    print(json.dumps(result,ensure_ascii=False,indent=2))
