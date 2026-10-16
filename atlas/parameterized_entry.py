"""Validated symbolic U(1) charge inputs in the same gauge/matter entry format.

Family validation proves syntax and integer-valuedness, not existence of a
parameter point, equivalence of families, anomaly cancellation or viability.
Numerical specializations use the existing full-inventory identity convention.
"""
from copy import deepcopy
from fractions import Fraction

from catalogue_identity import normalize_spec, IncompleteContent, object_keys
from charge_expressions import (parameter_names, parse_charge, parse_constraints,
                                constraint_text, validate_values, check_constraints)
from scalar_conventions import is_scalar

SCHEMA = 'field-content-3'
EXPRESSION_CONVENTION = 'integer-polynomial-1'


def normalize_parameterized(spec):
    object_keys(spec, {'schema_version', 'inventory_complete', 'gauge_factors', 'matter', 'parameters'},
                {'name', 'paper_ids', 'constraints'})
    if spec['schema_version'] != SCHEMA:
        raise IncompleteContent('Parameterized entries require field-content-3')
    names = parameter_names(spec['parameters'])
    atoms = parse_constraints(spec.get('constraints', []), names)
    result = deepcopy(spec)
    result['parameters'] = {name: {'domain': 'integer'} for name in names}
    result['constraints'] = sorted(set(constraint_text(atom) for atom in atoms))
    probe = deepcopy(result)
    probe['schema_version'] = 'field-content-2'
    del probe['parameters'], probe['constraints']
    factors = result['gauge_factors']
    if not isinstance(factors, list) or not isinstance(result['matter'], list):
        raise IncompleteContent('Gauge factors and matter must be lists')
    for factor in factors:
        object_keys(factor, {'id', 'family', 'rank'})
    if names and not any(a['family'] == 'U1' for a in factors):
        raise IncompleteContent('Charge parameters need at least one explicit U(1) factor')
    used = set()
    polynomials = []
    for field, placeholder in zip(result['matter'], probe['matter']):
        object_keys(field, {'lorentz', 'reality', 'copies', 'gauge_representations'}, {'label'})
        object_keys(field['lorentz'], {'dimension', 'scheme', 'irreps'})
        field_polynomials = []
        reps = field['gauge_representations']
        if not isinstance(reps, dict) or set(reps) != {a['id'] for a in factors}:
            raise IncompleteContent('Assign every gauge factor explicitly')
        for factor in factors:
            if factor['family'] != 'U1':
                continue
            rep = reps[factor['id']]
            object_keys(rep, {'charge'})
            polynomial = parse_charge(rep['charge'], names)
            field_polynomials.append(polynomial)
            used.update(polynomial.symbols)
            rep['charge'] = polynomial.render()
            # Validate all other conventions using a neutral placeholder only;
            # this is never returned or treated as an actual specialization.
            placeholder['gauge_representations'][factor['id']]['charge'] = (
                '0' if polynomial.symbols else polynomial.render())
        if names and field['lorentz'].get('dimension') == 4:
            irreps = field['lorentz'].get('irreps')
            try:
                weights = [[str(Fraction(x)) for x in w] for w in irreps]
            except (ValueError, TypeError, ZeroDivisionError) as error:
                raise IncompleteContent('Invalid Lorentz representation') from error
            if weights == [['0', '1/2']] or sorted(weights) == sorted([['1/2', '0'], ['0', '1/2']]):
                raise IncompleteContent('Symbolic intake requires explicit LH Weyl rows; conjugate every gauge factor and negate charges for RH fields')
            if weights == [['1/2', '0']] and field['reality'] != 'none':
                raise IncompleteContent('Use reality=none for independent symbolic LH Weyl rows')
        polynomials.append(field_polynomials)
    if set(names) - used:
        raise IncompleteContent('Every declared parameter must occur in a charge polynomial: ' + ', '.join(sorted(set(names) - used)))
    # Reuse exact Dynkin/rank/Lorentz/count validation. Do not use its normalized
    # matter: scalar realification can change on a zero-charge locus.
    checked = normalize_spec(probe)
    if names:
        # Symbolic inputs contain no unsplit 4D Dirac fields, so source rows and
        # validated rows correspond one-to-one. Preserve source scalar counts.
        for field, validated, charges in zip(result['matter'], checked['matter'], polynomials):
            field['lorentz'] = validated['lorentz']
            if is_scalar(validated['lorentz']):
                for polynomial in charges:
                    if polynomial.terms and field['reality'] == 'real':
                        raise IncompleteContent('A source real scalar cannot carry a nonzero U(1) polynomial; use a complex source field')
                    if polynomial.symbols and field['reality'] == 'real_module':
                        raise IncompleteContent('A symbolic scalar needs its source complex-field count; real-module counts are assigned after specialization')
    return result


def specialize(spec, values):
    result = normalize_parameterized(spec)
    names = parameter_names(result['parameters'])
    validate_values(values, names)
    check_constraints(parse_constraints(result['constraints'], names), values)
    result['schema_version'] = 'field-content-2'
    del result['parameters'], result['constraints']
    for field in result['matter']:
        for factor in result['gauge_factors']:
            if factor['family'] == 'U1':
                rep = field['gauge_representations'][factor['id']]
                rep['charge'] = str(parse_charge(rep['charge'], names).evaluate(values))
    # Keep evaluated source units here: prepare_entry reports the actual common
    # scale, then applies scalar realification and numerical duplicate checks.
    return result


def validation_report(spec):
    normalized = normalize_parameterized(spec)
    return {
        'status': 'valid_parameterized_entry_requires_source_review',
        'normalized_entry': normalized,
        'expression_convention': EXPRESSION_CONVENTION,
        'fingerprint': None,
        'validation': {
            'syntax': 'passed', 'integer_valued_charges': 'guaranteed_by_integer_polynomial_language',
            'parameter_domain_nonempty': 'not_proven', 'anomalies': 'not_checked_not_an_intake_requirement',
            'family_equivalence': 'not_certified',
        },
        'action': 'Review source evidence before intake. Keep this as one parameterized entry, not an enumeration. Specialize with --values for primitive normalization and numerical duplicate reconciliation.',
        'limits': 'Valid mathematical input is not a physical-consistency certificate. General family reparameterizations, overlaps, U(1) basis mixing and parameter-domain satisfiability require separate reconciliation.',
    }
