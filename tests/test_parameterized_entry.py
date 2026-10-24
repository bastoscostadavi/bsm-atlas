"""Charge-schema validation, safe evaluation and numerical specialization."""
from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import unittest

from bsm_atlas.catalogue_identity import canonicalize, IncompleteContent
from bsm_atlas.charge_expressions import parse_charge, parameter_names
from bsm_atlas.parameterized_entry import normalize_parameterized, specialize
from bsm_atlas.catalogue import prepare, check
from bsm_atlas.nonabelian_core import restrict_nonabelian

ROOT = Path(__file__).resolve().parent.parent


def family(charges=('z1**2 + z2', 'z2 - z1'), constraints=None):
    return {
        'schema_version': 'field-content-3', 'inventory_complete': True,
        'parameters': {'z1': {'domain': 'integer'}, 'z2': {'domain': 'integer'}},
        'constraints': ['0 < z1 < z2 < 3'] if constraints is None else constraints,
        'gauge_factors': [{'id': 'X', 'family': 'U1', 'rank': 1}],
        'matter': [{'lorentz': {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['1/2', '0']]},
                    'reality': 'none', 'copies': 1, 'gauge_representations': {'X': {'charge': q}}}
                   for q in charges],
    }


class ParameterizedEntries(unittest.TestCase):
    def test_schema_example_and_anomaly_not_an_intake_gate(self):
        source = json.loads((ROOT / 'atlas/examples/parameterized-charges.json').read_text())
        report = prepare(source)
        self.assertEqual(report['validation']['anomalies'], 'not_checked_not_an_intake_requirement')
        numerical = prepare(source, values={'z1': 1, 'z2': 2})
        charges = [int(f['gauge_representations']['X']['charge']) for f in numerical['normalized_entry']['matter'][-2:]]
        self.assertEqual(charges, [3, 1])
        self.assertNotEqual(sum(charges), 0)
        self.assertNotEqual(sum(q**3 for q in charges), 0)
        self.assertEqual(numerical['constraint_check'], 'passed')

    def test_normalization_no_mutation_and_idempotence(self):
        source = family((' (z1 + z2)**2 ', 'z1*z2 + z2*z1'))
        before = deepcopy(source)
        result = normalize_parameterized(source)
        self.assertEqual(source, before)
        self.assertEqual(result, normalize_parameterized(result))
        self.assertEqual(result['matter'][0]['gauge_representations']['X']['charge'], 'z1**2 + 2*z1*z2 + z2**2')
        self.assertEqual(result['matter'][1]['gauge_representations']['X']['charge'], '2*z1*z2')
        self.assertEqual(result['constraints'], ['0 < z1', 'z1 < z2', 'z2 < 3'])

    def test_polynomial_exact_evaluation(self):
        p = parse_charge('(z1 + z2)**3 - z1**3', ('z1', 'z2'))
        for a, b in product(range(-3, 4), repeat=2):
            self.assertEqual(p.evaluate({'z1': a, 'z2': b}), (a + b)**3 - a**3)
        self.assertEqual(parse_charge('z1-z1', ('z1',)).render(), '0')
        self.assertEqual(parse_charge('z1**0', ('z1',)).evaluate({}), 1)
        rendered = parse_charge('z1**16*z1**16', ('z1',)).render()
        self.assertEqual(rendered, 'z1**32')
        self.assertEqual(parse_charge(rendered, ('z1',)).render(), rendered)

    def test_concrete_entry_empty_metadata_uses_existing_identity(self):
        source = json.loads((ROOT / 'atlas/examples/two-higgs-doublets.json').read_text())
        extended = {**deepcopy(source), 'schema_version': 'field-content-3', 'parameters': {}, 'constraints': []}
        self.assertEqual(prepare(source)['fingerprint'], prepare(extended)['fingerprint'])
        self.assertEqual(check(source, ROOT/'website/downloads/field-catalogue.sqlite')['fingerprint'],
                         check(extended, ROOT/'website/downloads/field-catalogue.sqlite')['fingerprint'])

    def test_primitive_scale_is_pointwise_not_a_generic_gcd_guess(self):
        source = family(('2*z1', '2*z2'), [])
        a = prepare(source, values={'z1': 2, 'z2': 4})
        b = prepare(source, values={'z1': 1, 'z2': 2})
        self.assertEqual([f['gauge_representations']['X']['charge'] for f in a['normalized_entry']['matter']], ['1', '2'])
        self.assertEqual(a['transformations'][0]['positive_source_scale'], '1/4')
        self.assertEqual(a['fingerprint'], b['fingerprint'])

    def test_all_zero_assignment_has_no_invented_unit(self):
        result = prepare(family(('z1', 'z2'), []), values={'z1': 0, 'z2': 0})
        self.assertIsNone(result['transformations'][0]['positive_source_scale'])
        self.assertEqual([f['gauge_representations']['X']['charge'] for f in result['normalized_entry']['matter']], ['0', '0'])

    def test_constraint_assignment_validation(self):
        for values in ({'z1': 0, 'z2': 2}, {'z1': 2, 'z2': 1}, {'z1': 1, 'z2': 3},
                       {'z1': 1}, {'z1': 1, 'z2': 2, 'extra': 0}, {'z1': True, 'z2': 2},
                       {'z1': 1.0, 'z2': 2}, {'z1': '1', 'z2': 2}, []):
            with self.subTest(values=values), self.assertRaises(IncompleteContent):
                specialize(family(), values)
        self.assertEqual(specialize(family(), {'z1': 1, 'z2': 2})['schema_version'], 'field-content-2')

    def test_equalities_and_unbounded_integer_domains(self):
        source = family(('z1', 'z2'), ['z2 == z1**2', 'z1 != 0', '-5 <= z1', 'z2 >= 1'])
        prepare(source, values={'z1': -3, 'z2': 9})
        with self.assertRaises(IncompleteContent):
            prepare(source, values={'z1': -3, 'z2': 8})

    def test_no_claim_of_domain_satisfiability(self):
        report = prepare(family(constraints=['z1 > z2', 'z1 < z2']))
        self.assertEqual(report['validation']['parameter_domain_nonempty'], 'not_proven')
        with self.assertRaises(IncompleteContent):
            prepare(family(constraints=['1 > 2']))
        self.assertEqual(len(prepare(family(constraints=['1 < 2']))['normalized_entry']['constraints']), 0)

    def test_symbolic_template_fingerprint_is_not_a_numerical_identity(self):
        source = family()
        report = prepare(source, ROOT/'website/downloads/field-catalogue.sqlite')
        self.assertTrue(report['fingerprint'])
        self.assertEqual(report['identity_convention'], 'symbolic-template-2')
        self.assertEqual(report['duplicate_check']['status'], 'no_exact_symbolic_template_match')
        self.assertEqual(report['validation']['family_equivalence'], 'not_certified')
        with self.assertRaises(IncompleteContent):
            canonicalize(source)

    def test_single_charge_per_row_no_arrays_or_code(self):
        for expression in ('[0,-3,3]', 'z1.real', 'z1[0]', 'int(z1)', '__import__("os")',
                           'sum([z1,z2])', '(lambda: 1)()', 'z3', '?', 'source:2',
                           '1.0', 'True', 'z1/2', 'z1//2', 'z1%2', 'z1**-1', 'z1**z2',
                           '2**1000000', 'z1 if z2 else 0', 1, ['z1', 'z2']):
            with self.subTest(expression=expression), self.assertRaises(IncompleteContent):
                prepare(family((expression, 'z1+z2')))

    def test_constraint_grammar_rejects_code_functions_and_disjunction(self):
        for constraint in ('z1', 'z1 in [1,2]', 'z1 > 0 or z2 > 0', 'abs(z1) < 3',
                           'z1 > 0 and z2 > 0', 'z1 < unknown', 'z1 < 1.5', 'z1 = 2',
                           'z1 < __import__("os")'):
            with self.subTest(constraint=constraint), self.assertRaises(IncompleteContent):
                prepare(family(constraints=[constraint]))

    def test_parameter_declarations(self):
        for declarations in (['z1', 'z2'], {'z1': {'domain': 'real'}}, {'z1': {'domain': 'integer', 'min': 0}},
                             {'z1()': {'domain': 'integer'}}, {'for': {'domain': 'integer'}},
                             {'_private': {'domain': 'integer'}}):
            source = family(); source['parameters'] = declarations
            with self.subTest(parameters=declarations), self.assertRaises(IncompleteContent):
                prepare(source)
        with self.assertRaises(IncompleteContent):
            prepare(family(('1', '2')))
        with self.assertRaises(IncompleteContent):
            parameter_names({f'z{i}': {'domain': 'integer'} for i in range(17)})

    def test_nonabelian_and_inventory_validation_still_apply(self):
        source = json.loads((ROOT / 'atlas/examples/parameterized-charges.json').read_text())
        for change in ('weight', 'copies', 'inventory', 'factor', 'charge-type'):
            bad = deepcopy(source)
            if change == 'weight': bad['matter'][0]['gauge_representations']['colour']['dynkin'] = [1]
            if change == 'copies': bad['matter'][0]['copies'] = True
            if change == 'inventory': bad['inventory_complete'] = False
            if change == 'factor': bad['gauge_factors'][0]['rank'] = 0
            if change == 'charge-type': bad['matter'][0]['gauge_representations']['colour'] = {'charge': 'z1'}
            with self.subTest(change=change), self.assertRaises(IncompleteContent):
                prepare(bad)

    def test_symbolic_fermions_must_already_be_lh(self):
        for irreps in ([['0', '1/2']], [['1/2', '0'], ['0', '1/2']]):
            source = family(); source['matter'][0]['lorentz']['irreps'] = irreps
            with self.assertRaises(IncompleteContent): prepare(source)

    def test_scalar_zero_locus_reality_and_core_preserve_degrees_of_freedom(self):
        source = family(('z1', 'z2'), [])
        source['matter'][0].update(lorentz={'dimension':4, 'scheme':'jL_jR', 'irreps':[[0, 0]]}, reality='complex')
        charged = prepare(source, values={'z1': 1, 'z2': 1})['normalized_entry']
        neutral = prepare(source, values={'z1': 0, 'z2': 1})['normalized_entry']
        self.assertEqual(charged['matter'][0]['copies'], 1)
        self.assertEqual(neutral['matter'][0]['copies'], 2)
        self.assertEqual(restrict_nonabelian(charged)['id'], restrict_nonabelian(neutral)['id'])
        for reality in ('real', 'real_module'):
            bad = deepcopy(source); bad['matter'][0]['reality'] = reality
            with self.assertRaises(IncompleteContent): prepare(bad)

    def test_bounded_parser_and_value_size(self):
        for expression in ('z1' * 1025, '+'.join(['z1'] * 130), '(z1+z2)**16 * (z1+z2)**16 * z1'):
            with self.subTest(expression=expression[:50]), self.assertRaises(IncompleteContent):
                prepare(family((expression, 'z2')))
        with self.assertRaises(IncompleteContent):
            prepare(family(constraints=[]), values={'z1': 2**300, 'z2': 1})
        with self.assertRaises(IncompleteContent):
            prepare(family(constraints=['z1 > 0'] * 65))

    def test_versions_do_not_silently_accept_symbolic_metadata(self):
        source = family(); source['schema_version'] = 'field-content-2'
        with self.assertRaises(IncompleteContent): prepare(source)
        numerical = json.loads((ROOT / 'atlas/examples/two-higgs-doublets.json').read_text())
        with self.assertRaises(IncompleteContent): prepare(numerical, values={})

    def test_cli_good_and_bad_assignments(self):
        command = [sys.executable, '-B', '-m', 'bsm_atlas', 'prepare', str(ROOT/'atlas/examples/parameterized-charges.json'), '--values']
        good = subprocess.run([*command, '{"z1":1,"z2":2}'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)['parameter_assignment'], {'z1':1, 'z2':2})
        bad = subprocess.run([*command, '{"z1":0,"z2":2}'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2, bad.stderr)
        self.assertEqual(json.loads(bad.stdout)['status'], 'blocked_before_ingestion')


if __name__ == '__main__':
    unittest.main()
