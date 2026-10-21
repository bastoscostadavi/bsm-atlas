"""Complete specifications, references and paper-demonstrated problem links."""
from copy import deepcopy
import json
from pathlib import Path
import re

from catalogue_identity import IncompleteContent, canonicalize, normalize_spec, object_keys
from symbolic_identity import canonicalize_family
from scalar_conventions import uniform_scalar, is_scalar
from parameterized_entry import specialize

SOURCE = Path(__file__).with_name('catalogue.json')
SCHEMA = 'bsm-atlas-2'


def identity(spec):
    return canonicalize_family(spec) if spec.get('schema_version') == 'field-content-3' else canonicalize(spec)


def normalize(spec):
    if not isinstance(spec,dict):
        raise IncompleteContent('A specification must be an object')
    if spec.get('schema_version') == 'field-content-3':
        if not spec.get('parameters'):
            return normalize_spec(specialize(spec,{}))
        result=canonicalize_family(spec)['normalized_entry']
        for row in result['matter']:
            if is_scalar(row['lorentz']): uniform_scalar(row,result['gauge_factors'],result['parameters'])
        return result
    return normalize_spec(spec)


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise IncompleteContent('Expected a nonempty string')


def validate_problems(data):
    """Check evidence shape and provenance links, not the truth of a paper's result."""
    if not isinstance(data['problems'],list) or not isinstance(data['entry_problems'],list):
        raise IncompleteContent('Problems and demonstrations must be lists')
    problems=set();names=set()
    for p in data['problems']:
        object_keys(p,{'id','name','description'})
        for value in p.values():text(value)
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',p['id']) or p['id'] in problems or p['name'].strip().casefold() in names:
            raise IncompleteContent('Problem IDs and names must be unique; use stable slugs')
        problems.add(p['id']);names.add(p['name'].strip().casefold())
    references={(e['id'],r['paper_id']) for e in data['entries'] for r in e['references']}
    seen=set()
    for claim in data['entry_problems']:
        object_keys(claim,{'entry_id','problem_id','paper_id','locators','result'})
        for key in ['entry_id','problem_id','paper_id','result']:text(claim[key])
        if claim['problem_id'] not in problems:
            raise IncompleteContent('Unknown problem')
        if (claim['entry_id'],claim['paper_id']) not in references:
            raise IncompleteContent('A demonstration must cite a paper linked to that exact entry')
        key=(claim['entry_id'],claim['problem_id'],claim['paper_id'])
        if key in seen:raise IncompleteContent('Repeated entry/problem/paper demonstration')
        seen.add(key)
        locators=claim['locators']
        if not isinstance(locators,list) or not locators:
            raise IncompleteContent('A demonstrated result needs source locations')
        for locator in locators:text(locator)
        if len(set(locators))!=len(locators):raise IncompleteContent('Repeated source location')


def validate(data):
    """Reject partial inputs, extra schema fields and duplicate identities."""
    object_keys(data, {'schema_version', 'papers', 'entries','problems','entry_problems'})
    if data['schema_version'] != SCHEMA:
        raise IncompleteContent('Unsupported catalogue schema')
    if not isinstance(data['papers'], list) or not isinstance(data['entries'], list):
        raise IncompleteContent('Papers and entries must be lists')
    papers, ids, fingerprints = set(), set(), set()
    for p in data['papers']:
        object_keys(p, {'id', 'arxiv', 'title', 'authors'})
        for value in p.values(): text(value)
        if p['id'] in papers or not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})v[1-9]\d*', p['arxiv']):
            raise IncompleteContent('Use unique paper IDs and versioned arXiv identifiers')
        papers.add(p['id'])
    if len({p['arxiv'] for p in data['papers']}) != len(papers):
        raise IncompleteContent('Repeated paper version')
    for e in data['entries']:
        object_keys(e, {'id', 'name', 'specification', 'references'}, {'aliases'})
        text(e['id']); text(e['name'])
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', e['id']) or e['id'] in ids:
            raise IncompleteContent('Entry IDs must be unique URL slugs')
        ids.add(e['id'])
        s=e['specification']
        if not isinstance(s,dict): raise IncompleteContent('A specification must be an object')
        if s.get('schema_version') not in {'field-content-2', 'field-content-3'}:
            raise IncompleteContent('Store field-content-2 or field-content-3 specifications')
        if set(s) - {'schema_version','inventory_complete','gauge_factors','matter','parameters','constraints'}:
            raise IncompleteContent('Names and references belong on the entry, not its specification')
        if normalize(s) != s:
            raise IncompleteContent('Stored specifications must already be normalized: '+e['id'])
        h=identity(s)['fingerprint']
        if h in fingerprints:
            raise IncompleteContent('Duplicate gauge–matter specification; combine paper references')
        fingerprints.add(h)
        if not isinstance(e['references'],list) or not e['references']:
            raise IncompleteContent('Every entry needs a paper reference')
        linked=set()
        for ref in e['references']:
            object_keys(ref, {'paper_id'}, {'locators','parameter_names'})
            if ref['paper_id'] not in papers or ref['paper_id'] in linked:
                raise IncompleteContent('Unknown or repeated paper reference')
            linked.add(ref['paper_id'])
            if 'locators' in ref:
                if not isinstance(ref['locators'],list): raise IncompleteContent('Locators must be a list')
                for value in ref['locators']: text(value)
            if 'parameter_names' in ref:
                mapping=ref['parameter_names']
                if not isinstance(mapping,dict): raise IncompleteContent('Parameter names must be a map')
                for source,target in mapping.items():
                    text(source)
                    if target not in s.get('parameters',{}): raise IncompleteContent('Undeclared mapped parameter')
        if not isinstance(e.get('aliases',[]),list): raise IncompleteContent('Aliases must be a list')
        for alias in e.get('aliases',[]):
            object_keys(alias, {'id','name'}); text(alias['id']); text(alias['name'])
            if alias['id'] in ids: raise IncompleteContent('Repeated entry or alias ID')
            ids.add(alias['id'])
    validate_problems(data)
    return data


def load(path=SOURCE):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def ingest(data, candidate):
    """Normalize before writing; an exact match only gains paper references."""
    result=deepcopy(data)
    validate(result)
    candidate=deepcopy(candidate)
    # Validate shape before duplicate reconciliation; reject unrelated extras.
    object_keys(candidate, {'id','name','specification','references'}, {'aliases'})
    candidate['specification']=normalize(candidate['specification'])
    validate({'schema_version':SCHEMA,'papers':result['papers'],'entries':[candidate],
              'problems':result['problems'],'entry_problems':[]})
    h=identity(candidate['specification'])['fingerprint']
    existing=next((e for e in result['entries'] if identity(e['specification'])['fingerprint']==h),None)
    if existing:
        for alias in [{'id':candidate['id'],'name':candidate['name']},*candidate.get('aliases',[])]:
            if alias['id'] != existing['id'] and not any(a['id']==alias['id'] for a in existing.get('aliases',[])):
                existing.setdefault('aliases',[]).append(alias)
        for ref in candidate['references']:
            old=next((r for r in existing['references'] if r['paper_id']==ref['paper_id']),None)
            if old is None: existing['references'].append(ref)
            else:
                for locator in ref.get('locators',[]):
                    if locator not in old.get('locators',[]): old.setdefault('locators',[]).append(locator)
                if ref.get('parameter_names'):
                    if old.get('parameter_names') not in (None,ref['parameter_names']):
                        raise IncompleteContent('Conflicting source parameter names')
                    old['parameter_names']=ref['parameter_names']
        target=existing['id']
    else:
        result['entries'].append(candidate); target=candidate['id']
    validate(result)
    return result,target


def ingest_demonstration(data,candidate):
    """Add source-reviewed evidence; never infer it from field content alone."""
    result=deepcopy(data)
    validate(result)
    candidate=deepcopy(candidate)
    object_keys(candidate,{'entry_id','problem_id','paper_id','locators','result'})
    key=tuple(candidate[k] for k in ['entry_id','problem_id','paper_id'])
    previous=next((c for c in result['entry_problems'] if
                   tuple(c[k] for k in ['entry_id','problem_id','paper_id'])==key),None)
    if previous is None:result['entry_problems'].append(candidate)
    elif previous!=candidate:raise IncompleteContent('Conflicting demonstration; review the existing result explicitly')
    validate(result)
    return result,' / '.join(key)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Validate or add a source-checked entry; exact matches merge references.')
    parser.add_argument('--source',type=Path,default=SOURCE)
    additions=parser.add_mutually_exclusive_group()
    additions.add_argument('--add',type=Path,help='Entry object with specification and references; referenced papers must already be listed')
    additions.add_argument('--add-demonstration',type=Path,help='Source-reviewed problem demonstration; entry, problem and paper link must exist')
    parser.add_argument('--write',action='store_true',help='Save the validated addition; otherwise dry-run only')
    args=parser.parse_args()
    try:
        data=load(args.source)
        if args.add or args.add_demonstration:
            action,path=(ingest,args.add) if args.add else (ingest_demonstration,args.add_demonstration)
            data,target=action(data,json.loads(path.read_text()))
            if args.write:
                temporary=args.source.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                temporary.replace(args.source)
            print(('Saved ' if args.write else 'Validated dry run: ')+target)
        elif args.write: parser.error('--write requires --add or --add-demonstration')
        else: print(f"Valid catalogue: {len(data['entries'])} entries, {len(data['papers'])} papers, {len(data['entry_problems'])} demonstrations")
    except (ValueError,TypeError,KeyError) as error:
        parser.exit(2,str(error)+'\n')
