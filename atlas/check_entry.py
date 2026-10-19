#!/usr/bin/env python3
"""Read-only canonical duplicate check before adding a model or paper link."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from catalogue_identity import canonicalize,IncompleteContent
from parameterized_entry import SCHEMA as PARAMETER_SCHEMA, validation_report, specialize

def check(spec,database):
    if isinstance(spec,dict) and spec.get('schema_version')==PARAMETER_SCHEMA:
        report=validation_report(spec)
        if report['normalized_entry']['parameters']:
            with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as c:
                matches=[{'entry_id':r[0],'name':r[1]} for r in c.execute('SELECT e.entry_id,e.name FROM entry_identity i JOIN entries e ON i.entry_id=e.entry_id WHERE i.fingerprint=?',(report['fingerprint'],))]
            return {**report,'status':'exact_symbolic_template_match' if matches else 'no_exact_symbolic_template_match_review_required',
                    'matches':matches,
                    'action':'Link the paper to the existing entry.' if matches else 'Review existing families before intake. A different normalized template or domain is not proof of a new family of physical models.'}
        spec=specialize(report['normalized_entry'],{})
    result=canonicalize(spec)
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        matches=[{'entry_id':r[0],'name':r[1]} for r in c.execute('SELECT e.entry_id,e.name FROM entry_identity i JOIN entries e ON i.entry_id=e.entry_id WHERE i.fingerprint=?',(result['fingerprint'],))]
        algebra=json.loads(result['canonical_json'])['gauge_factors']
        candidates=[{'entry_id':r[0],'name':r[1],'algebra':r[2]} for r in c.execute('SELECT e.entry_id,e.name,a.algebra FROM entry_identity i JOIN entries e ON i.entry_id=e.entry_id JOIN full_gauge_algebras a ON a.full_algebra_id=e.full_algebra_id WHERE a.canonical_json=?',(json.dumps({'schema_version':'full-gauge-algebra-1','gauge_factors':algebra},sort_keys=True,separators=(',',':')),))]
    return {'status':'exact_field_content_match' if matches else 'no_exact_match_review_required','fingerprint':result['fingerprint'],'matches':matches,'same_algebra_candidates':[] if matches else candidates,'action':'Link the paper to the existing entry; do not create a second field-content entry.' if matches else 'Review same-algebra candidates before adding an entry. No exact match does not prove novelty.','limits':'Field-content identity only, not physical-theory equivalence. General U(1) basis mixing, simple-algebra outer automorphisms and different regimes require reconciliation. This is not an SM-embedding, anomaly or viability check.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--database',type=Path,default=Path(__file__).resolve().parent.parent/'website/downloads/field-catalogue.sqlite')
    args=parser.parse_args()
    invalid=False
    try:result=check(json.loads(args.candidate.read_text()),args.database)
    except (IncompleteContent,KeyError,ValueError,TypeError) as e:
        result={'status':'unresolved_or_invalid_input','reason':str(e),'action':'Resolve missing conventions/data; do not declare this a new model.'}
        invalid=True
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if invalid:raise SystemExit(2)
