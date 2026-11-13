"""Deterministic 4D fermion anomaly assessment, without a consistency intake gate.

The perturbative coefficients are those of the recorded Weyl spectrum alone.
Global tests cover the ordinary pi_4 Witten tests on the simply connected
semisimple cover on spin manifolds, not arbitrary global forms or inflow.
"""
from fractions import Fraction
from hashlib import sha256
from itertools import combinations_with_replacement
import json
from math import prod

from .charge_expressions import parse_charge
from .field_conventions import weyl_dimension
from .lie_indices import cubic_index, twice_index

METHOD = 'weyl-anomalies-1'
PERTURBATIVE_SCOPE = ('Four-dimensional left-handed spin-1/2 fermion spectrum; '
    'pure gauge and mixed gauge-gravitational anomalies. No extra cancellation sectors or inflow assumed.')
GLOBAL_SCOPE = ('Ordinary Witten tests for SU(2) and Sp factors of the simply connected '
    'semisimple cover, on spin manifolds. Global gauge group, centre quotients, '
    'non-spin structures and other global anomalies are not certified.')
MAX_ANOMALY_TERMS = 16384


class AnomalyLimit(ValueError):
    pass


def specification_hash(spec):
    return sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def add(left, right, scale=1):
    result = dict(left)
    for powers, value in right.items():
        result[powers] = result.get(powers, 0) + scale * value
        if not result[powers]:
            del result[powers]
        if len(result) > MAX_ANOMALY_TERMS:
            raise AnomalyLimit('Anomaly polynomial term limit exceeded')
    return result


def multiply(left, right):
    if len(left) * len(right) > 2000000:
        raise AnomalyLimit('Anomaly polynomial multiplication budget exceeded')
    result = {}
    for p, x in left.items():
        for q, y in right.items():
            key = tuple(a + b for a, b in zip(p, q))
            result[key] = result.get(key, 0) + x * y
            if len(result) > MAX_ANOMALY_TERMS:
                raise AnomalyLimit('Anomaly polynomial term limit exceeded')
    return {p: x for p, x in result.items() if x}


def render(terms, names):
    pieces = []
    for powers, value in sorted(terms.items(), reverse=True):
        monomial = '*'.join(name if p == 1 else f'{name}**{p}'
                            for name, p in zip(names, powers) if p)
        magnitude = abs(value)
        body = (('' if magnitude == 1 else str(magnitude) + '*') + monomial
                if monomial else str(magnitude))
        pieces.append(('-' if value < 0 else '+' if pieces else '') + body)
    return ''.join(pieces) or '0'


def unsupported_reason(spec):
    for row in spec['matter']:
        lorentz = row['lorentz']
        if lorentz['dimension'] != 4 or lorentz['scheme'] != 'jL_jR':
            return 'Only four-dimensional jL_jR spectra are supported.'
        # Ordinary bosonic tensor fields do not generate the chiral fermion
        # anomaly. Higher-spin fermions and self-dual tensor formulations need
        # a dedicated calculation; do not infer them from the Weyl formula.
        if lorentz['irreps'] not in ([['0', '0']], [['1/2', '0']], [['1/2', '1/2']]):
            return 'Higher-spin or tensor matter is outside this checker.'
    return None


def _assess(spec):
    result = {'method': METHOD, 'specification_sha256': specification_hash(spec),
              'perturbative': {'scope': PERTURBATIVE_SCOPE},
              'global': {'scope': GLOBAL_SCOPE, 'complete': False}}
    reason = unsupported_reason(spec)
    if reason:
        for key in ('perturbative', 'global'):
            result[key].update(status='unsupported', reason=reason, checks=[])
        return result
    factors = spec['gauge_factors']
    simple = [a for a in factors if a['family'] != 'U1']
    abelian = [a for a in factors if a['family'] == 'U1']
    names = tuple(sorted(spec.get('parameters', {})))
    zero = (0,) * len(names)
    totals = {}

    def accumulate(kind, ids, polynomial, scale):
        key = (kind, tuple(ids))
        totals[key] = add(totals.get(key, {}), polynomial, scale)

    parities = {a['id']: 0 for a in simple if a['family'] == 'C'
                or (a['family'] == 'A' and a['rank'] == 1)}
    # Initialize zero tests even for purely bosonic entries.
    for a in simple:
        accumulate('nonabelian_cubic', [a['id']], {}, 0)
        for b in abelian:
            accumulate('nonabelian_squared_u1', [a['id'], b['id']], {}, 0)
    for b in abelian:
        accumulate('gravitational_u1', [b['id']], {}, 0)
    for triple in combinations_with_replacement(abelian, 3):
        accumulate('abelian_cubic', [a['id'] for a in triple], {}, 0)

    for row in spec['matter']:
        if row['lorentz']['irreps'] != [['1/2', '0']]:
            continue
        reps = row['gauge_representations']
        dimensions = {a['id']: weyl_dimension(a['family'], reps[a['id']]['dynkin']) for a in simple}
        dimension = prod(dimensions.values())
        charges = {a['id']: (parse_charge(reps[a['id']]['charge'], names).terms if names
                            else {zero: Fraction(reps[a['id']]['charge'])}) for a in abelian}
        for a in simple:
            labels = tuple(reps[a['id']]['dynkin'])
            spectators = row['copies'] * (dimension // dimensions[a['id']])
            accumulate('nonabelian_cubic', [a['id']], {zero: cubic_index(a['family'], labels)}, spectators)
            index = twice_index(a['family'], labels)
            for b in abelian:
                accumulate('nonabelian_squared_u1', [a['id'], b['id']], charges[b['id']], spectators * index)
            if a['id'] in parities:
                parities[a['id']] = (parities[a['id']] + spectators * index) % 2
        for b in abelian:
            accumulate('gravitational_u1', [b['id']], charges[b['id']], row['copies'] * dimension)
        for triple in combinations_with_replacement(abelian, 3):
            polynomial = {zero: 1}
            for a in triple:
                polynomial = multiply(polynomial, charges[a['id']])
            accumulate('abelian_cubic', [a['id'] for a in triple], polynomial, row['copies'] * dimension)
    checks = [{'kind': kind, 'factors': list(ids), 'coefficient': render(value, names),
               'vanishes_identically': not value}
              for (kind, ids), value in totals.items()]
    nonzero = [p for p in totals.values() if p]
    status = ('nonzero' if any(set(p) == {zero} for p in nonzero)
              else 'conditions_not_resolved' if nonzero else 'cancels')
    result['perturbative'].update(status=status, checks=checks,
        normalization='A(SU fundamental)=1; mixed non-Abelian checks use 2T, with long roots squared=2.',
        cancellation_conditions=[render(p, names) + ' == 0' for p in nonzero],
        family_constraints=spec.get('constraints', []),
        constraints_solved=False if names else None)
    result['global'].update(status='witten_anomaly' if any(parities.values()) else 'cover_tests_pass',
        checks=[{'kind': 'witten_mod2', 'factor': key, 'parity': parity, 'passes': not parity}
                for key, parity in parities.items()])
    return result


def assess(spec):
    try:
        return _assess(spec)
    except AnomalyLimit as error:
        # Charge polynomials can grow cubically. Keep their failure separate
        # from the charge-independent Witten test instead of losing all entries
        # in a catalogue build. A zero-charge probe has the same cover parities.
        from copy import deepcopy
        probe = deepcopy(spec)
        probe.pop('parameters', None)
        probe.pop('constraints', None)
        for row in probe['matter']:
            for a in probe['gauge_factors']:
                if a['family'] == 'U1':
                    row['gauge_representations'][a['id']]['charge'] = '0'
        result = _assess(probe)
        result['specification_sha256'] = specification_hash(spec)
        result['perturbative'] = {'status': 'resource_limit', 'scope': PERTURBATIVE_SCOPE,
                                   'checks': [], 'reason': str(error)}
        return result
