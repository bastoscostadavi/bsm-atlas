"""The authoritative catalogue: complete specifications and paper references."""
from copy import deepcopy
from contextlib import closing
from fractions import Fraction
import json
from pathlib import Path
import re
import sqlite3

from .catalogue_identity import (IncompleteContent, canonicalize, normalize_spec,
                                 object_keys, primitive_charge_scale)
from .symbolic_identity import canonicalize_family
from .scalar_conventions import CONVENTION as SCALAR_CONVENTION, uniform_scalar, is_scalar
from .parameterized_entry import SCHEMA as PARAMETER_SCHEMA, specialize, validation_report

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'atlas/catalogue.json'
DATABASE = ROOT / 'website/downloads/field-catalogue.sqlite'


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


def check(spec, database=DATABASE):
    """Read-only exact and same-algebra lookup against a built SQLite export."""
    if isinstance(spec, dict) and spec.get('schema_version') == PARAMETER_SCHEMA:
        report = validation_report(spec)
        if report['normalized_entry']['parameters']:
            with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as con:
                matches = [{'entry_id': row[0], 'name': row[1]} for row in con.execute(
                    'SELECT e.entry_id,e.name FROM entry_identity i JOIN entries e ON i.entry_id=e.entry_id WHERE i.fingerprint=?',
                    (report['fingerprint'],))]
            return {**report,
                    'status': 'exact_symbolic_template_match' if matches else 'no_exact_symbolic_template_match_review_required',
                    'matches': matches,
                    'action': 'Link the paper to the existing entry.' if matches else
                    'Review existing families before intake. A different normalized template or domain is not proof of a new family of physical models.'}
        spec = specialize(report['normalized_entry'], {})
    result = canonicalize(spec)
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        matches = [{'entry_id': row[0], 'name': row[1]} for row in con.execute(
            'SELECT e.entry_id,e.name FROM entry_identity i JOIN entries e ON i.entry_id=e.entry_id WHERE i.fingerprint=?',
            (result['fingerprint'],))]
        algebra = json.loads(result['canonical_json'])['gauge_factors']
        candidates = [{'entry_id': row[0], 'name': row[1], 'algebra': row[2]} for row in con.execute(
            'SELECT e.entry_id,e.name,a.algebra FROM entry_identity i JOIN entries e ON i.entry_id=e.entry_id JOIN full_gauge_algebras a ON a.full_algebra_id=e.full_algebra_id WHERE a.canonical_json=?',
            (json.dumps({'schema_version': 'full-gauge-algebra-1', 'gauge_factors': algebra},
                        sort_keys=True, separators=(',', ':')),))]
    return {'status': 'exact_field_content_match' if matches else 'no_exact_match_review_required',
            'fingerprint': result['fingerprint'], 'matches': matches,
            'same_algebra_candidates': [] if matches else candidates,
            'action': 'Link the paper to the existing entry; do not create a second field-content entry.' if matches else
            'Review same-algebra candidates before adding an entry. No exact match does not prove novelty.',
            'limits': 'Field-content identity only, not physical-theory equivalence. General U(1) basis mixing, simple-algebra outer automorphisms and different regimes require reconciliation. This is not an SM-embedding, anomaly or viability check.'}


def prepare(spec, database=None, values=None):
    """Normalize a source-established specification without writing any files."""
    if isinstance(spec, dict) and spec.get('schema_version') == PARAMETER_SCHEMA:
        if values is not None or not spec.get('parameters'):
            assignment = {} if values is None else values
            result = prepare(specialize(spec, assignment), database)
            result['parameter_assignment'] = deepcopy(assignment)
            result['constraint_check'] = 'passed'
            return result
        report = validation_report(spec)
        if database is not None:
            report['duplicate_check'] = check(spec, database)
        return report
    if values is not None:
        raise IncompleteContent('--values is only supported for field-content-3 entries')
    original = deepcopy(spec)
    normalized = normalize_spec(spec)
    transformations = []
    for factor in normalized['gauge_factors']:
        if factor['family'] != 'U1':
            continue
        scale = primitive_charge_scale(row['gauge_representations'][factor['id']]['charge']
                                       for row in original['matter'])
        transformations.append({
            'factor_id': factor['id'], 'normalization': 'primitive_integer_full_inventory',
            'positive_source_scale': str(scale) if scale is not None else None,
            'generator_orientation': 'retained',
            'note': 'All-zero assignments have no primitive nonzero unit.' if not any(
                Fraction(row['gauge_representations'][factor['id']]['charge']) for row in normalized['matter']) else
                'Scale may be combined with charge conjugation when converting source fermions.'})
    result = {'status': 'normalized_candidate_requires_source_review',
              'normalized_entry': normalized, 'transformations': transformations,
              'scalar_convention': SCALAR_CONVENTION,
              'fingerprint': canonicalize(normalized)['fingerprint'],
              'action': 'Verify every assignment against its paper and run duplicate reconciliation before ingestion. Scalar copies use irreducible real gauge modules; use source reality/counts correctly on intake. This tool is not a database writer or a source-extraction certificate.'}
    if database is not None:
        result['duplicate_check'] = check(normalized, database)
    if spec != original:
        raise AssertionError('Preparation mutated the extraction input')
    return result


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
