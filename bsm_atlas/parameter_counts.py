"""Counts for the unrestricted renormalizable component Lagrangian.

This counts real coefficient components, not operator types. It does not
attribute a paper's additional Z2, SUSY, CP or flavor assumptions to an entry.
Physical dimensions are only reported when an exact orbit certificate exists.
"""
from functools import lru_cache
import json
from pathlib import Path

from .characters import Algebra, CountingLimit
from .scalar_conventions import conjugate_reps, representation_type
from .field_conventions import weyl_dimension
from .lie_indices import twice_index

METHOD = 'renormalizable-characters-1'
ASSUMPTIONS = ('Generic four-dimensional renormalizable scalar/Weyl component theory, '
    'canonical kinetic terms; no imposed SUSY, CP or extra discrete/global symmetry. '
    'Counts real coefficient components, including scalar tadpoles, gauge couplings, '
    'Abelian kinetic mixing and non-Abelian theta angles. Vacuum energy, gravity '
    'and Abelian theta terms excluded. This is not a count of a paper-specific restricted model.')
ROOT = Path(__file__).resolve().parent.parent


def _merge(target, source, copies):
    for weight, value in source.items():
        target[weight] = target.get(weight, 0) + copies * value


@lru_cache(maxsize=1)
def certificates():
    path = ROOT / 'atlas/parameter_certificates.json'
    return json.loads(path.read_text()) if path.exists() else {}


def sm_orbit(spec):
    """Generic orbit for SM generations + Higgs doublets + real/sterile singlets.

    Match the full spectrum, never names or paper labels. The rank includes
    anomalous weak-theta shifts and neutral real-scalar translations.
    """
    factors = spec['gauge_factors']
    if sorted((a['family'], a['rank']) for a in factors) != [('A', 1), ('A', 2), ('U1', 1)]:
        return None
    colour = next(a['id'] for a in factors if a['family'] == 'A' and a['rank'] == 2)
    weak = next(a['id'] for a in factors if a['family'] == 'A' and a['rank'] == 1)
    charge = next(a['id'] for a in factors if a['family'] == 'U1')
    for sign in (1, -1):
        for conjugated in (False, True):
            expected = {((1, 0) if not conjugated else (0, 1), (1,), 1): 3,
                        ((0, 1) if not conjugated else (1, 0), (0,), -4): 3,
                        ((0, 1) if not conjugated else (1, 0), (0,), 2): 3,
                        ((0, 0), (1,), -3): 3, ((0, 0), (0,), 6): 3}
            actual = {}
            higgs = singlets = sterile = 0
            valid = True
            for row in spec['matter']:
                reps = row['gauge_representations']
                key = (tuple(reps[colour]['dynkin']), tuple(reps[weak]['dynkin']), sign * int(reps[charge]['charge']))
                if row['lorentz']['irreps'] == [['1/2', '0']]:
                    if key == ((0, 0), (0,), 0):
                        sterile += row['copies']
                    else:
                        actual[key] = actual.get(key, 0) + row['copies']
                elif key[:2] == ((0, 0), (1,)) and abs(key[2]) == 3:
                    higgs += row['copies']
                elif key == ((0, 0), (0,), 0):
                    singlets += row['copies']
                else:
                    valid = False
            if valid and higgs and actual == expected:
                group = 45 + higgs ** 2 + sterile ** 2 + singlets * (singlets - 1) // 2 + singlets
                stabilizer = 2 if sterile else 5 if higgs == 1 else 3
                return {'orbit_rank': group - stabilizer + 1,
                    'connected_redefinition_dimension': group,
                    'classical_stabilizer_dimension': stabilizer,
                    'theta_shift_rank_increment': 1,
                    'source': 'atlas/DERIVED_PROPERTIES.md#sm-component-family'}
    return None


def _rank(rows):
    from fractions import Fraction
    rows = [list(map(Fraction, row)) for row in rows]
    rank = 0
    for column in range(len(rows[0]) if rows else 0):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        scale = rows[rank][column]
        rows[rank] = [x / scale for x in rows[rank]]
        for i in range(rank + 1, len(rows)):
            scale = rows[i][column]
            rows[i] = [x - scale * y for x, y in zip(rows[i], rows[rank])]
        rank += 1
    return rank


def fermion_only_physical(spec, total):
    """Mass-only theories via ordinary and skew Takagi / singular values."""
    factors = spec['gauge_factors']
    simple = [a for a in factors if a['family'] != 'U1']

    def key(reps):
        return tuple((int(reps[a['id']]['charge']),) if a['family'] == 'U1'
                     else tuple(reps[a['id']]['dynkin']) for a in factors)

    species = {}
    for row in spec['matter']:
        reps = row['gauge_representations']
        signature = key(reps)
        old = species.get(signature, (reps, 0))
        species[signature] = (reps, old[1] + row['copies'])
    done = set()
    masses, massless = 0, []
    for signature, (reps, copies) in species.items():
        if signature in done:
            continue
        done.add(signature)
        kind = representation_type(factors, reps)
        if kind == 'real':
            masses += copies
        elif kind == 'pseudoreal':
            masses += copies // 2
            if copies % 2:
                massless.append(reps)
        else:
            dual = key(conjugate_reps(reps, factors))
            other = species.get(dual, (None, 0))[1]
            done.add(dual)
            masses += min(copies, other)
            if copies != other:
                massless.append(reps)
    # Only a massless chiral rotation can shift theta without changing masses.
    anomaly_rows = []
    for reps in massless:
        dimensions = {a['id']: weyl_dimension(a['family'], reps[a['id']]['dynkin']) for a in simple}
        from math import prod
        dimension = prod(dimensions.values())
        anomaly_rows.append([twice_index(a['family'], tuple(reps[a['id']]['dynkin']))
                             * dimension // dimensions[a['id']] for a in simple])
    n = len(factors) - len(simple)
    physical = masses + len(simple) + n * (n + 1) // 2 + len(simple) - _rank(anomaly_rows)
    return {'status': 'certified', 'value': physical, 'orbit_rank': total - physical,
        'source': 'atlas/DERIVED_PROPERTIES.md#mass-only-fermion-theories'}


def assess(spec, fingerprint=None):
    result = {'method': METHOD, 'assumptions': ASSUMPTIONS,
              'total': {'status': 'not_computed', 'value': None},
              'physical': {'status': 'not_computed', 'value': None,
                  'reason': 'A generic field-redefinition orbit-rank certificate is not available for this spectrum.'}}
    certificate = certificates().get(fingerprint)
    if certificate:
        result['total'] = {'status': 'computed', 'value': certificate['total'],
                           'matter_real_coefficients': certificate['matter'],
                           'source': certificate['source'], **certificate.get('breakdown', {})}
        result['physical'] = {'status': 'certified', 'value': certificate['physical'],
                              'orbit_rank': certificate['orbit_rank'], 'source': certificate['source']}
        return result
    if spec.get('parameters'):
        result['total']['reason'] = 'Symbolic charge families need separate interaction counts on their charge loci.'
        return result
    if any(row['lorentz']['dimension'] != 4 or row['lorentz']['scheme'] != 'jL_jR'
           or row['lorentz']['irreps'] not in ([['0', '0']], [['1/2', '0']])
           for row in spec['matter']):
        result['total']['reason'] = 'Only four-dimensional scalars and left-handed Weyl matter are supported.'
        return result
    try:
        algebra = Algebra(spec['gauge_factors'])
        scalar, fermion = {}, {}
        for row in spec['matter']:
            reps = row['gauge_representations']
            char = algebra.representation(reps)
            if row['lorentz']['irreps'] == [['1/2', '0']]:
                _merge(fermion, char, row['copies'])
            else:
                _merge(scalar, char, row['copies'])
                if representation_type(spec['gauge_factors'], reps) != 'real':
                    _merge(scalar, algebra.representation(conjugate_reps(reps, spec['gauge_factors'])), row['copies'])
        powers = algebra.symmetric(scalar, 4)
        potential = [algebra.singlets(char) for char in powers[1:]]
        fermion_pair = algebra.symmetric(fermion, 2)[2]
        masses = algebra.singlets(fermion_pair)
        yukawa = algebra.singlets(algebra.multiply(scalar, fermion_pair))
        matter = sum(potential) + 2 * (masses + yukawa)
        n = sum(a['family'] == 'U1' for a in spec['gauge_factors'])
        simple = len(spec['gauge_factors']) - n
        gauge = simple + n * (n + 1) // 2
        result['total'] = {'status': 'computed', 'value': matter + gauge + simple,
            'matter_real_coefficients': matter, 'scalar_potential_by_degree': potential,
            'fermion_mass_complex_coefficients': masses, 'yukawa_complex_coefficients': yukawa,
            'gauge_kinetic_coefficients': gauge, 'nonabelian_theta_angles': simple}
        orbit = sm_orbit(spec)
        if not fermion and all(all(not x for x in w) for w in scalar):
            # A generic quartic polynomial breaks scalar rotations and translations
            # completely. Gauge factors act trivially on singlets.
            nscalar = scalar.get(algebra.zero, 0)
            rank = nscalar * (nscalar - 1) // 2 + nscalar
            result['physical'] = {'status': 'certified', 'value': result['total']['value'] - rank,
                'orbit_rank': rank, 'source': 'Generic real-singlet quartic potential: rotations and translations have discrete stabilizer.'}
        elif not scalar:
            result['physical'] = fermion_only_physical(spec, result['total']['value'])
        else:
            from .physical_parameters import assess as physical_parameters
            try:
                result['physical'] = physical_parameters(spec, result['total'])
            except CountingLimit as error:
                if orbit:
                    # Independently established closed form remains available
                    # when a large character/flavor calculation hits a budget.
                    result['physical'] = {'status': 'certified', 'value': result['total']['value'] - orbit['orbit_rank'], **orbit}
                else:
                    result['physical']['reason'] = str(error)
    except CountingLimit as error:
        result['total'].update(status='resource_limit', reason=str(error))
    if result['physical']['status'] == 'certified':
        abelian = [a['id'] for a in spec['gauge_factors'] if a['family'] == 'U1']
        charges = [[int(row['gauge_representations'][key]['charge']) for key in abelian]
                   for row in spec['matter']]
        if 'free_abelian_normalizations' not in result['physical']:
            active = _rank(charges)
            free = (len(abelian) * (len(abelian) + 1) - active * (active + 1)) // 2
            result['physical']['free_abelian_normalizations'] = free
            result['physical']['value'] -= free
            result['physical']['orbit_rank'] += free
    return result
