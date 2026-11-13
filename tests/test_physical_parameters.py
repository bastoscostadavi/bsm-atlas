"""Known quotients and independent identities for the generic orbit solver."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from bsm_atlas.characters import CountingLimit
from bsm_atlas.parameter_counts import assess as parameters
from bsm_atlas.physical_parameters import (METHOD, MassSlice, assess, sparse_rank,
                                          schur_dimension, symbolic_rank, young_basis)
from tests.test_properties import field, sm, spectrum


class GenericPhysicalParameters(TestCase):
    def calculate(self, spec):
        total = parameters(spec)['total']
        result = assess(spec, total)
        self.assertEqual(result['method'], METHOD)
        self.assertEqual(result['value'] + result['orbit_rank'], total['value'])
        return total, result

    def test_standard_model_and_extensions_without_lookup(self):
        source = sm()
        singlet = {a['id']: {'charge': '0'} if a['family'] == 'U1'
                   else {'dynkin': [0] * a['rank']} for a in source['gauge_factors']}
        cases = [(source, 61, 19)]
        extra = deepcopy(source)
        extra['matter'].append(field(singlet, scalar=True))
        cases.append((extra, 67, 24))
        extra = deepcopy(source)
        extra['matter'].append(field(singlet, copies=3))
        cases.append((extra, 91, 37))
        extra = deepcopy(source)
        extra['matter'][-1]['copies'] = 2
        cases.append((extra, 127, 80))
        # Disable all previous spectrum-specific shortcuts. These are actual
        # coupling-module calculations, not table values or model-name matches.
        with patch('bsm_atlas.parameter_counts.sm_orbit', return_value=None), \
             patch('bsm_atlas.parameter_counts.certificates', return_value={}):
            for spec, raw, physical in cases:
                with self.subTest(expected=physical):
                    total, result = self.calculate(spec)
                    self.assertEqual(total['value'], raw)
                    self.assertEqual(result['value'], physical)
                    self.assertEqual(result['proof'], 'exact universal-kernel bound saturated by a finite-field minor')

    def test_multi_higgs_scalar_potentials(self):
        # General 2HDM potential: 14 real coefficients, 11 physical.
        # General 3HDM potential: 54 real coefficients, 46 physical.
        factors = [{'id': 'w', 'family': 'A', 'rank': 1}, {'id': 'y', 'family': 'U1', 'rank': 1}]
        for n, raw, physical in [(1, 2, 2), (2, 14, 11), (3, 54, 46),
                                  (4, 152, 137), (5, 350, 326)]:
            source = spectrum(factors, [field({'w': {'dynkin': [1]}, 'y': {'charge': '1'}}, n, scalar=True)])
            total, result = self.calculate(source)
            self.assertEqual(sum(total['scalar_potential_by_degree']), raw)
            self.assertEqual(result['value'] - 3, physical)  # g, g', theta_weak

    def test_real_singlets_translations_and_free_maxwell_normalization(self):
        for n, raw, physical in [(1, 4, 3), (2, 14, 11), (3, 34, 28)]:
            source = spectrum([{'id': 'free', 'family': 'U1', 'rank': 1}],
                              [field({'free': {'charge': '0'}}, n, scalar=True)])
            total, result = self.calculate(source)
            self.assertEqual(total['value'], raw + 1)
            self.assertEqual(result['value'], physical)
            self.assertEqual(result['free_abelian_normalizations'], 1)

    def test_quaternionic_scalar_commutant(self):
        # One SU(2) doublet without hypercharge has accidental custodial Sp(1).
        # It must not acquire three spurious removable coupling directions.
        factors = [{'id': 'w', 'family': 'A', 'rank': 1}]
        source = spectrum(factors, [field({'w': {'dynkin': [1]}}, scalar=True)])
        total, result = self.calculate(source)
        self.assertEqual((total['value'], result['value']), (4, 4))
        self.assertEqual(result['generic_stabilizer_dimension'], 3)
        source['matter'][0]['copies'] = 2
        total, result = self.calculate(source)
        self.assertEqual((total['value'], result['value']), (28, 18))

    def test_antisymmetric_color_contraction_and_full_flavor_breaking(self):
        source = spectrum([{'id': 'c', 'family': 'A', 'rank': 2}],
                          [field({'c': {'dynkin': [1, 0]}}, copies=3, scalar=True)])
        total, result = self.calculate(source)
        self.assertEqual(total['scalar_potential_by_degree'], [0, 9, 2, 45])
        self.assertEqual((total['value'], result['value'], result['orbit_rank']), (58, 49, 9))

    def test_pseudoreal_weyl_mass_and_symmetric_yukawa_flavors(self):
        # An SU(2) adjoint scalar and two Weyl doublets: a skew-flavor mass
        # leaves Sp(1), while a generic symmetric-flavor adjoint Yukawa and
        # its conjugate break that remaining three-dimensional group.
        source = spectrum([{'id': 'w', 'family': 'A', 'rank': 1}],
                          [field({'w': {'dynkin': [2]}}, scalar=True),
                           field({'w': {'dynkin': [1]}}, copies=2)])
        total, result = self.calculate(source)
        self.assertEqual(total['fermion_mass_complex_coefficients'], 1)
        self.assertEqual(total['yukawa_complex_coefficients'], 3)
        self.assertEqual((total['value'], result['orbit_rank'], result['value']), (12, 4, 8))

    def test_invariance_under_charge_units_factor_names_and_split_rows(self):
        source = sm()
        expected = self.calculate(source)[1]['value']
        renamed = deepcopy(source)
        mapping = {a['id']: 'factor' + str(i) for i, a in enumerate(renamed['gauge_factors'])}
        for a in renamed['gauge_factors']:
            a['id'] = mapping[a['id']]
        renamed['gauge_factors'].reverse()
        for row in renamed['matter']:
            row['gauge_representations'] = {mapping[k]: v for k, v in row['gauge_representations'].items()}
            for rep in row['gauge_representations'].values():
                if 'charge' in rep:
                    rep['charge'] = str(2 * int(rep['charge']))
        first = renamed['matter'][0]
        first['copies'] -= 1
        renamed['matter'].append(dict(deepcopy(first), copies=1))
        self.assertEqual(self.calculate(renamed)[1]['value'], expected)

    def test_conjugate_scalar_labels_are_the_same_real_module(self):
        factors = [{'id': 'y', 'family': 'U1', 'rank': 1}]
        source = spectrum(factors, [field({'y': {'charge': '1'}}, scalar=True),
                                    field({'y': {'charge': '-1'}}, scalar=True)])
        total, result = self.calculate(source)
        # Hermitian 2x2 masses (4), Hermitian 3x3 quartics in
        # (phi_1^2,phi_1 phi_2,phi_2^2) (9), plus one gauge coupling.
        self.assertEqual((total['value'], result['value']), (14, 11))
        source['matter'][1]['gauge_representations']['y']['charge'] = '1'
        self.assertEqual(self.calculate(source)[1]['value'], 11)

    def test_schur_basis_hook_dimensions(self):
        for n, shape, dimension in [(3, (2,), 6), (3, (1, 1), 3),
                                    (3, (2, 1), 8), (3, (2, 2), 6),
                                    (2, (4,), 5), (2, (1, 1, 1), 0)]:
            self.assertEqual(len(young_basis(n, shape)), dimension)
            self.assertEqual(schur_dimension(n, shape), dimension)

    def test_large_flavor_spaces_are_not_expanded_into_fields(self):
        # Independent SM+n-sterile formula: 16+7n physical for n>=1.
        source = sm()
        reps = {a['id']: {'charge': '0'} if a['family'] == 'U1'
                else {'dynkin': [0] * a['rank']} for a in source['gauge_factors']}
        source['matter'].append(field(reps, copies=100))
        with patch('bsm_atlas.parameter_counts.sm_orbit', return_value=None):
            _, result = self.calculate(source)
        self.assertEqual(result['value'], 716)
        self.assertTrue(result['selected_subspace'])
        # General N-doublet potential, from arXiv:2102.13120 table 1.
        source = sm()
        source['matter'] = [source['matter'][-1]]
        source['matter'][0]['copies'] = 100
        _, result = self.calculate(source)
        self.assertEqual(result['value'] - 5, (100**4 + 100**2 + 2) // 2)

    def test_exact_rank_and_resource_limit_never_become_guesses(self):
        self.assertEqual(sparse_rank([{0: 1, 1: 2}, {0: 2, 1: 4}]), 1)
        self.assertEqual(sparse_rank([{0: 1, 1: 2}, {0: 2, 1: 4}], 1000000007), 1)
        with self.assertRaises(CountingLimit), patch('bsm_atlas.physical_parameters.MAX_BLOCKS', 0):
            MassSlice(sm())
        # Matrix [[x,y],[2x,2y]] has symbolic rank one, independently of samples.
        try:
            import sympy  # noqa: F401
        except ImportError:
            with self.assertRaises(CountingLimit):
                symbolic_rank([], 0, 0)
        else:
            self.assertEqual(symbolic_rank([{0: {0: 1}, 1: {1: 1}},
                                            {0: {0: 2}, 1: {1: 2}}], 2, 2), 1)
