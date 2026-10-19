#!/usr/bin/env python3
"""Read-only pre-ingestion validation of numerical or parameterized entries.

The extraction agent must establish source facts and provenance first. This
command emits the normalized candidate that may be considered for ingestion;
it never writes the original or generated database. Declared symbolic charges
use field-content-3. Unknown assignments are not free parameters or numbers.
"""
import argparse
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from catalogue_identity import normalize_spec,primitive_charge_scale,canonicalize,IncompleteContent
from check_entry import check
from scalar_conventions import CONVENTION as SCALAR_CONVENTION
from parameterized_entry import SCHEMA as PARAMETER_SCHEMA, specialize, validation_report

def prepare(spec,database=None,values=None):
    if isinstance(spec,dict) and spec.get('schema_version')==PARAMETER_SCHEMA:
        if values is not None or not spec.get('parameters'):
            assignment={} if values is None else values
            result=prepare(specialize(spec,assignment),database)
            result['parameter_assignment']=deepcopy(assignment)
            result['constraint_check']='passed'
            return result
        report=validation_report(spec)
        if database is not None:
            report['duplicate_check']=check(spec,database)
        return report
    if values is not None:
        raise IncompleteContent('--values is only supported for field-content-3 entries')
    original=deepcopy(spec)
    normalized=normalize_spec(spec)
    transformations=[]
    for a in normalized['gauge_factors']:
        if a['family']!='U1':continue
        # Charge conjugation changes signs, never the positive common unit.
        scale=primitive_charge_scale(f['gauge_representations'][a['id']]['charge'] for f in original['matter'])
        transformations.append({'factor_id':a['id'],'normalization':'primitive_integer_full_inventory','positive_source_scale':str(scale) if scale is not None else None,'generator_orientation':'retained','note':'All-zero assignments have no primitive nonzero unit.' if not any(Fraction(f['gauge_representations'][a['id']]['charge']) for f in normalized['matter']) else 'Scale may be combined with charge conjugation when converting source fermions.'})
    result={'status':'normalized_candidate_requires_source_review','normalized_entry':normalized,'transformations':transformations,'scalar_convention':SCALAR_CONVENTION,'fingerprint':canonicalize(normalized)['fingerprint'],'action':'Verify source evidence for every assignment and run duplicate reconciliation before ingestion. Scalar copies use irreducible real gauge modules; retain source reality/counts separately. This tool is not a database writer or a source-extraction certificate.'}
    if database is not None:result['duplicate_check']=check(normalized,database)
    if spec!=original:raise AssertionError('Preparation mutated the extraction input')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--database',type=Path,help='Also run the read-only duplicate check')
    parser.add_argument('--values',type=json.loads,help='Specialize declared parameters, e.g. \'{"z1":1,"z2":2}\'')
    parser.add_argument('--require-normalized',action='store_true',help='Reject inputs needing mathematical normalization; usable as a pre-write assertion')
    args=parser.parse_args()
    try:
        candidate=json.loads(args.candidate.read_text())
        result=prepare(candidate,args.database,args.values)
        if args.require_normalized and candidate!=result['normalized_entry']:
            raise IncompleteContent('Candidate needs normalization; use normalized_entry and preserve source notation in provenance before ingestion')
    except (IncompleteContent,KeyError,ValueError,TypeError,AttributeError,IndexError) as error:
        print(json.dumps({'status':'blocked_before_ingestion','reason':str(error),'action':'Correct the schema or extraction. Declare source-free charge parameters using field-content-3; source omissions remain partial, not invented parameter values.'},ensure_ascii=False,indent=2))
        raise SystemExit(2)
    print(json.dumps(result,ensure_ascii=False,indent=2))
