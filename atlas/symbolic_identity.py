"""Exact syntactic identity for integer-polynomial charge templates.

Quotient parameter names, factor/row order and repeated-factor permutations.
Constraints remain an explicit part of identity: no domain solver, parameter
shifts, charge-basis changes or general family-equivalence claim is made.
"""
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from itertools import permutations, product
from math import factorial
import json

from catalogue_identity import IncompleteContent
from charge_expressions import Polynomial, parameter_names, parse_charge, parse_constraints
from parameterized_entry import normalize_parameterized

CONVENTION = 'symbolic-template-2'
MAX_CANONICAL_CHOICES = 4096


def _rename(polynomial, mapping, names):
    positions = {name: i for i, name in enumerate(names)}
    terms = {}
    for powers, coefficient in polynomial.terms.items():
        renamed = [0] * len(names)
        for old, power in zip(polynomial.names, powers):
            renamed[positions[mapping[old]]] = power
        terms[tuple(renamed)] = coefficient
    return Polynomial(names, terms).render()


@lru_cache(maxsize=128)
def _canonicalize(encoded):
    spec = json.loads(encoded)
    source_names = parameter_names(spec['parameters'])
    names = tuple('z' + str(i + 1) for i in range(len(source_names)))
    groups = defaultdict(list)
    for factor in spec['gauge_factors']:
        groups[(factor['family'], factor['rank'])].append(factor)
    groups = [groups[k] for k in sorted(groups, key=lambda k: (k[0] == 'U1', k[0], -k[1]))]
    choices = factorial(len(names))
    for group in groups:
        choices *= factorial(len(group))
    if choices > MAX_CANONICAL_CHOICES:
        raise IncompleteContent('Symbolic parameter/factor canonicalization exceeds the safe search bound; explicit reconciliation is required')
    atoms = parse_constraints(spec['constraints'], source_names)
    charges = [{a['id']: parse_charge(row['gauge_representations'][a['id']]['charge'], source_names)
                for a in spec['gauge_factors'] if a['family'] == 'U1'} for row in spec['matter']]
    best, best_mapping, best_constraints, best_charges = None, None, None, None
    for ordering in permutations(source_names):
        mapping = dict(zip(ordering, names))
        constraints = sorted({_rename(a, mapping, names) + ' ' + op + ' ' + _rename(b, mapping, names)
                              for a, op, b, _ in atoms})
        renamed = [{key: _rename(p, mapping, names) for key, p in row.items()} for row in charges]
        for factor_choices in product(*(permutations(group) for group in groups)):
            factors = [a for group in factor_choices for a in group]
            merged = defaultdict(int)
            for row, qs in zip(spec['matter'], renamed):
                content = {'lorentz': row['lorentz'], 'reality': row['reality'],
                           'gauge': [({'charge': qs[a['id']]} if a['family'] == 'U1' else
                                      row['gauge_representations'][a['id']]) for a in factors]}
                merged[json.dumps(content, sort_keys=True, separators=(',', ':'))] += row['copies']
            payload = {'identity_convention': CONVENTION, 'schema_version': 'field-content-3',
                       'gauge_factors': [{k: a[k] for k in ['family', 'rank']} for a in factors],
                       'parameters': {name: {'domain': 'integer'} for name in names},
                       'constraints': constraints,
                       'matter': [{**json.loads(row), 'copies': n} for row, n in sorted(merged.items())]}
            candidate = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            if best is None or candidate < best:
                best, best_mapping = candidate, mapping
                best_constraints, best_charges = constraints, renamed
    # The public specification preserves factor IDs, source row order and labels
    # for readable source correspondence. Only the identity payload removes those identifiers.
    spec['parameters'] = {name: {'domain': 'integer'} for name in names}
    spec['constraints'] = best_constraints
    for row, charges in zip(spec['matter'], best_charges):
        for key, charge in charges.items():
            row['gauge_representations'][key]['charge'] = charge
    spec = normalize_parameterized(spec)
    return {'fingerprint': sha256(best.encode()).hexdigest(), 'canonical_json': best,
            'normalized_entry': spec, 'parameter_renaming': best_mapping,
            'identity_convention': CONVENTION}


def canonicalize_family(spec):
    normalized = normalize_parameterized(spec)
    result = _canonicalize(json.dumps(normalized, sort_keys=True, separators=(',', ':')))
    return deepcopy(result)
