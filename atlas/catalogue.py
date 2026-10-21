"""The authoritative catalogue: complete specifications and paper references."""
from copy import deepcopy
import json
from pathlib import Path
import re

from catalogue_identity import IncompleteContent, canonicalize, normalize_spec, object_keys
from symbolic_identity import canonicalize_family
from scalar_conventions import uniform_scalar, is_scalar
from parameterized_entry import specialize

SOURCE = Path(__file__).with_name('catalogue.json')


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


def validate(data):
    """Reject partial inputs, extra schema fields and duplicate identities."""
    object_keys(data, {'schema_version', 'papers', 'entries'})
    if data['schema_version'] != 'bsm-atlas-1':
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
    validate({'schema_version':'bsm-atlas-1','papers':result['papers'],'entries':[candidate]})
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


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Validate or add a source-checked entry; exact matches merge references.')
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--add',type=Path,help='Entry object with specification and references; referenced papers must already be listed')
    parser.add_argument('--write',action='store_true',help='Save the validated addition; otherwise dry-run only')
    args=parser.parse_args()
    try:
        data=load(args.source)
        if args.add:
            data,target=ingest(data,json.loads(args.add.read_text()))
            if args.write:
                temporary=args.source.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                temporary.replace(args.source)
            print(('Saved ' if args.write else 'Validated dry run: ')+target)
        elif args.write: parser.error('--write requires --add')
        else: print(f"Valid catalogue: {len(data['entries'])} entries, {len(data['papers'])} papers")
    except (ValueError,TypeError,KeyError) as error:
        parser.exit(2,str(error)+'\n')
