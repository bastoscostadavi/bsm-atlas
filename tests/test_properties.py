"""Independent anomaly examples, character identities and certified quotients."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bsm_atlas.anomalies import assess as anomalies
from bsm_atlas.catalogue import identity
from bsm_atlas.characters import Algebra, irrep_character
from bsm_atlas.lie_indices import cubic_index, twice_index
from bsm_atlas.parameter_counts import assess as parameters, _rank
from bsm_atlas.properties import assess

ROOT = Path(__file__).resolve().parent.parent


def spectrum(factors, rows):
    return {'schema_version': 'field-content-2', 'inventory_complete': True,
            'gauge_factors': factors, 'matter': rows}


def field(reps, copies=1, scalar=False):
    return {'lorentz': {'dimension': 4, 'scheme': 'jL_jR',
                       'irreps': [['0', '0']] if scalar else [['1/2', '0']]},
            'reality': 'real_module' if scalar else 'none', 'copies': copies,
            'gauge_representations': reps}


def sm():
    return json.loads((ROOT / 'atlas/reference_spectra.json').read_text())['R_SM']['specification']


class AnomalyTests(unittest.TestCase):
    def test_standard_model_and_missing_colour_spectator(self):
        source = sm()
        result = anomalies(source)
        self.assertEqual(result['perturbative']['status'], 'cancels')
        self.assertEqual(result['global']['status'], 'cover_tests_pass')
        self.assertFalse(result['global']['complete'])
        self.assertTrue(all(c['coefficient'] == '0' for c in result['perturbative']['checks']))
        # Removing one generation of colour triplet quark doublets changes
        # the weak-doublet parity by three, not one representation dimension.
        source['matter'][0]['copies'] -= 1
        result = anomalies(source)
        self.assertEqual(result['perturbative']['status'], 'nonzero')
        self.assertEqual(result['global']['status'], 'witten_anomaly')

    def test_multiple_abelian_factors_and_vectorlike_cancellation(self):
        factors = [{'id': 'x', 'family': 'U1', 'rank': 1}, {'id': 'y', 'family': 'U1', 'rank': 1}]
        row = field({'x': {'charge': '1'}, 'y': {'charge': '2'}})
        source = spectrum(factors, [row])
        checks = anomalies(source)['perturbative']['checks']
        self.assertEqual([c['coefficient'] for c in checks if c['kind'] == 'abelian_cubic'], ['1', '2', '4', '8'])
        source['matter'].append(field({'x': {'charge': '-1'}, 'y': {'charge': '-2'}}))
        self.assertEqual(anomalies(source)['perturbative']['status'], 'cancels')

    def test_global_higher_su2_representations_and_sp(self):
        for family, weight, parity in [('A', [1], 1), ('A', [3], 0), ('A', [5], 1),
                                       ('C', [1, 0], 1), ('C', [0, 1], 0)]:
            with self.subTest(family=family, weight=weight):
                source = spectrum([{'id': 'g', 'family': family, 'rank': len(weight)}],
                                  [field({'g': {'dynkin': weight}})])
                result = anomalies(source)
                self.assertEqual(result['perturbative']['status'], 'cancels')
                self.assertEqual(result['global']['checks'][0]['parity'], parity)

    def test_symbolic_polynomials_and_unresolved_domain_constraints(self):
        source = spectrum([{'id': 'x', 'family': 'U1', 'rank': 1}], [field({'x': {'charge': 'z1'}})])
        source.update(schema_version='field-content-3', parameters={'z1': {'domain': 'integer'}}, constraints=['z1 == 0'])
        result = anomalies(source)['perturbative']
        self.assertEqual(result['status'], 'conditions_not_resolved')
        self.assertEqual(result['cancellation_conditions'], ['z1 == 0', 'z1**3 == 0'])
        source['matter'].append(field({'x': {'charge': '-z1'}}))
        self.assertEqual(anomalies(source)['perturbative']['status'], 'cancels')

    def test_scalar_does_not_affect_anomalies_and_unsupported_is_not_pass(self):
        source = sm()
        before = anomalies(source)
        source['matter'][-1]['copies'] = 99
        self.assertEqual(anomalies(source)['perturbative'], before['perturbative'])
        self.assertNotEqual(anomalies(source)['specification_sha256'], before['specification_sha256'])
        source['matter'][0]['lorentz']['dimension'] = 5
        self.assertEqual(anomalies(source)['perturbative']['status'], 'unsupported')

    def test_symbolic_budget_preserves_global_test(self):
        source = spectrum([{'id': 'x', 'family': 'U1', 'rank': 1},
                           {'id': 'w', 'family': 'A', 'rank': 1}],
                          [field({'x': {'charge': 'z1+z2'}, 'w': {'dynkin': [1]}})])
        source.update(schema_version='field-content-3', parameters={k: {'domain': 'integer'} for k in ['z1', 'z2']}, constraints=[])
        with patch('bsm_atlas.anomalies.MAX_ANOMALY_TERMS', 1):
            result = anomalies(source)
        self.assertEqual(result['perturbative']['status'], 'resource_limit')
        self.assertEqual(result['global']['status'], 'witten_anomaly')

    def test_indices_against_independent_weight_traces(self):
        for family, labels in [('A', (2, 0)), ('A', (0, 1, 0, 0)), ('C', (1, 0)),
                               ('B', (1, 0, 0)), ('D', (0, 0, 0, 0, 1)),
                               ('E', (1, 0, 0, 0, 0, 0)), ('G', (1, 0))]:
            # C's last node and G2's second node are long.
            node = len(labels) - 1 if family in {'C', 'G'} else 0
            trace = sum(mult * weight[node] ** 2 for weight, mult in irrep_character(family, labels))
            self.assertEqual(twice_index(family, labels), Fraction(trace, 2))
        self.assertEqual(cubic_index('A', (2, 0)), 7)
        self.assertEqual(cubic_index('A', (0, 2)), -7)
        self.assertEqual(cubic_index('A', (0, 1, 0, 0)), 1)
        self.assertEqual(cubic_index('E', (1, 0, 0, 0, 0, 0)), 0)
        # A Cartan element diag(1,1,-2) has eigenvalue -w1-2w2 in
        # Dynkin coordinates; its cubic trace in the sextet is seven times 3.
        traces = [sum(mult * (-w[0] - 2 * w[1]) ** 3 for w, mult in irrep_character('A', labels))
                  for labels in [(1, 0), (2, 0)]]
        self.assertEqual(traces[1], 7 * traces[0])


class ParameterTests(unittest.TestCase):
    def test_sm_singlet_sterile_and_multiple_higgs(self):
        source = sm()
        result = parameters(source)
        self.assertEqual(result['total']['matter_real_coefficients'], 56)
        self.assertEqual(result['total']['scalar_potential_by_degree'], [0, 1, 0, 1])
        self.assertEqual(result['total']['value'], 61)
        self.assertEqual(result['physical']['value'], 19)
        source['matter'][-1]['copies'] = 2
        self.assertEqual(parameters(source)['total']['value'], 127)
        self.assertEqual(parameters(source)['physical']['value'], 80)
        source = sm()
        singlet_reps = {a['id']: {'charge': '0'} if a['family'] == 'U1' else {'dynkin': [0] * a['rank']}
                        for a in source['gauge_factors']}
        source['matter'].append(field(singlet_reps, scalar=True))
        self.assertEqual(parameters(source)['total']['value'], 67)
        self.assertEqual(parameters(source)['physical']['value'], 24)
        source['matter'][-1] = field(singlet_reps, copies=3)
        self.assertEqual(parameters(source)['total']['value'], 91)
        self.assertEqual(parameters(source)['physical']['value'], 37)

    def test_real_and_pseudoreal_statistics(self):
        su2 = [{'id': 'g', 'family': 'A', 'rank': 1}]
        for copies, expected in [(1, 0), (2, 1), (3, 3)]:
            source = spectrum(su2, [field({'g': {'dynkin': [1]}}, copies=copies)])
            self.assertEqual(parameters(source)['total']['fermion_mass_complex_coefficients'], expected)
        scalar = spectrum(su2, [field({'g': {'dynkin': [1]}}, scalar=True)])
        self.assertEqual(parameters(scalar)['total']['scalar_potential_by_degree'], [0, 1, 0, 1])
        self.assertEqual(parameters(scalar)['physical']['value'], 4)
        # One complex-neutral scalar is two real modules, not one.
        source = spectrum([{'id': 'x', 'family': 'U1', 'rank': 1}],
                          [field({'x': {'charge': '0'}}, copies=2, scalar=True)])
        self.assertEqual(parameters(source)['total']['scalar_potential_by_degree'], [2, 3, 4, 5])
        self.assertEqual(parameters(source)['physical']['value'], 11)
        self.assertEqual(parameters(source)['physical']['free_abelian_normalizations'], 1)
        source = spectrum(su2, [field({'g': {'dynkin': [0]}}, copies=2, scalar=True)])
        self.assertEqual(parameters(source)['physical']['value'], 13)

    def test_mass_only_physical_counts_and_consistency_gate(self):
        source = spectrum([{'id': 'x', 'family': 'U1', 'rank': 1}],
                          [field({'x': {'charge': '1'}}, 2), field({'x': {'charge': '-1'}}, 2)])
        self.assertEqual(parameters(source)['physical']['value'], 3)  # two masses + g
        su2 = [{'id': 'g', 'family': 'A', 'rank': 1}]
        source = spectrum(su2, [field({'g': {'dynkin': [1]}}, copies=2)])
        self.assertEqual(assess(source)['parameters']['physical']['value'], 3)  # m,g,theta
        source['matter'][0]['copies'] = 1
        # The atlas classifies Lie-algebra representations: an auxiliary cover
        # test must not gate this perturbative component-theory quotient.
        self.assertEqual(assess(source)['parameters']['physical']['value'], 1)  # g; massless rotation removes theta
        source = spectrum([{'id': 'x', 'family': 'U1', 'rank': 1}],
                          [field({'x': {'charge': '1'}})])
        self.assertEqual(assess(source)['parameters']['physical']['status'], 'anomalous_spectrum')

    def test_abelian_kinetic_mixing_and_resource_limits(self):
        source = spectrum([{'id': k, 'family': 'U1', 'rank': 1} for k in ['x', 'y']],
                          [field({'x': {'charge': '1'}, 'y': {'charge': '0'}}, scalar=True)])
        self.assertEqual(parameters(source)['total']['gauge_kinetic_coefficients'], 3)
        with patch('bsm_atlas.characters.MAX_OPERATIONS', 1):
            result = parameters(sm())
        self.assertEqual(result['total']['status'], 'resource_limit')
        self.assertIsNone(result['total']['value'])

    def test_scalar_baryon_statistics_and_hermitian_coefficients(self):
        # Three colour triplets have a complex determinant (two real cubic
        # coefficients), nine Hermitian bilinears and 45 real quartics.
        source = spectrum([{'id': 'c', 'family': 'A', 'rank': 2}],
                          [field({'c': {'dynkin': [1, 0]}}, copies=3, scalar=True)])
        self.assertEqual(parameters(source)['total']['scalar_potential_by_degree'], [0, 9, 2, 45])
        source['matter'][0]['copies'] = 1
        self.assertEqual(parameters(source)['total']['scalar_potential_by_degree'], [0, 1, 0, 1])

    def test_e6_certificate_and_exact_rank_reproduction(self):
        certificate = next(iter(json.loads((ROOT / 'atlas/parameter_certificates.json').read_text()).values()))
        source = certificate['specification']
        fingerprint = identity(source)['fingerprint']
        self.assertIn(fingerprint, json.loads((ROOT / 'atlas/parameter_certificates.json').read_text()))
        self.assertEqual(sum(op['coefficients'] * (1 if op['self_conjugate'] else 2)
                             for op in certificate['coefficient_inventory']), 315)
        # Reconstruct infinitesimal tensor variations from the portable integer
        # coupling point. No Mathematica or untracked experiment is required.
        fields = certificate['flavor_dimensions']
        generators = []
        for field_name, n in fields.items():
            for i in range(n):
                generators.append((field_name, True, {(i, i): 1}))
                for j in range(i):
                    generators.append((field_name, False, {(i, j): 1, (j, i): -1}))
                    generators.append((field_name, True, {(i, j): 1, (j, i): 1}))
        columns = []
        for field_name, imaginary, matrix in generators:
            real, imag = [], []
            for tensor in certificate['selected_coupling_tensors']:
                values = {tuple(e['indices']): e['value'] for e in tensor['nonzero_integer_entries']}
                slots = tensor['slots']
                for indices in product(*(range(fields[f]) for f, _ in slots)):
                    value = 0
                    for i, (slot_field, conjugated) in enumerate(slots):
                        if slot_field != field_name:
                            continue
                        sign = -1 if imaginary and conjugated else 1
                        for j in range(fields[field_name]):
                            replaced = indices[:i] + (j,) + indices[i+1:]
                            value += sign * matrix.get((j, indices[i]), 0) * values.get(replaced, 0)
                    real.append(0 if imaginary else value)
                    imag.append(value if imaginary else 0)
            columns.append(real + imag)
        self.assertEqual(len(generators), 23)
        self.assertEqual(_rank(columns), len(generators))
        result = parameters(source, fingerprint)
        self.assertEqual(result['physical']['value'], 294)
        self.assertEqual(result['total']['value'], 317)

    def test_new_cli_report_and_nonmutation(self):
        source = {'entries': [{'id': 'sm', 'specification': sm()}]}
        before = deepcopy(source)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.json'
            path.write_text(json.dumps(source))
            output = Path(directory) / 'properties.json'
            subprocess.run([sys.executable, '-B', '-m', 'bsm_atlas.properties', '--catalogue', str(path),
                            '--output', str(output)], cwd=ROOT, capture_output=True, check=True)
            report = json.loads(output.read_text())
            self.assertEqual(report['source_sha256'], sha256(path.read_bytes()).hexdigest())
            self.assertEqual(report['summary']['perturbative'], {'cancels': 1})
            self.assertEqual(report['entries'][0]['properties']['parameters']['physical']['value'], 19)
            self.assertEqual(json.loads(path.read_text()), before)

    def test_large_flavor_counts_survive_browser_json_exactly(self):
        source = spectrum([{'id': 'x', 'family': 'U1', 'rank': 1}],
                          [field({'x': {'charge': '0'}}, copies=100000, scalar=True)])
        count = parameters(source)['total']['value']
        exported = assess(source)['parameters']['total']['value']
        self.assertGreater(count, 2 ** 53)
        self.assertEqual(exported, str(count))


if __name__ == '__main__':
    unittest.main()
