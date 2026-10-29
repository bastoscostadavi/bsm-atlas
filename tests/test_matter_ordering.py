"""Exact matter dimensions and stable algebra–representation browsing order."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bsm_atlas.catalogue_identity import canonicalize
from bsm_atlas.build import main_data
from bsm_atlas.core_projection import attach_layers, spectrum_sort_key
from bsm_atlas.matter_ordering import matter_dimension, matter_sort_key
from bsm_atlas.nonabelian_core import restrict_nonabelian
from bsm_atlas.parameterized_entry import specialize
from bsm_atlas.symbolic_identity import canonicalize_family


ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / 'website/field-catalogue.json').read_text())
ENTRIES = {entry['id']: entry for entry in DATA['entries']}


def single(weight=(0,), charge='0', reality='complex', copies=1, lorentz=None):
    return {
        'schema_version': 'field-content-2', 'inventory_complete': True,
        'gauge_factors': [{'id': 'g', 'family': 'A', 'rank': len(weight)},
                          {'id': 'q', 'family': 'U1', 'rank': 1}],
        'matter': [{
            'lorentz': lorentz or {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['0', '0']]},
            'reality': reality, 'copies': copies,
            'gauge_representations': {'g': {'dynkin': list(weight)}, 'q': {'charge': charge}},
        }],
    }


def canonical(spec):
    identify = canonicalize_family if spec['schema_version'] == 'field-content-3' else canonicalize
    return json.loads(identify(spec)['canonical_json'])


class MatterDimensions(unittest.TestCase):
    def test_standard_model_and_simple_extensions(self):
        sm = json.loads((ROOT / 'atlas/reference_spectra.json').read_text())['R_SM']['specification']
        # 45 Weyl gauge components contribute 4 real field components each;
        # the Higgs contributes four. Gauge connections are not matter rows.
        self.assertEqual(matter_dimension(canonical(sm)), 184)
        for entry_id, expected in [('real-singlet-z2', 185),
                                   ('complex-singlet-portal', 186),
                                   ('two-higgs-doublets', 188)]:
            with self.subTest(entry=entry_id):
                entry = ENTRIES[entry_id]
                self.assertEqual(matter_dimension(entry['identity']['canonical']), expected)
                self.assertEqual(matter_dimension(restrict_nonabelian(entry['specification'])['canonical']), expected)

    def test_scalar_reality_and_multiplicity_count_real_components(self):
        cases = [
            (single(reality='real'), 1),
            (single(reality='complex'), 2),
            (single(reality='real', copies=7), 7),
            (single(weight=(2,), reality='real', copies=2), 6),
            (single(weight=(2,), reality='complex', copies=2), 12),
            (single(weight=(1,)), 4),  # Pseudoreal doublet: one real module.
            (single(weight=(1, 0)), 6),  # Complex SU(3) fundamental.
        ]
        for spec, expected in cases:
            with self.subTest(spec=spec):
                self.assertEqual(matter_dimension(canonical(spec)), expected)
        self.assertEqual(matter_sort_key(canonical(single(reality='complex'))),
                         matter_sort_key(canonical(single(reality='real', copies=2))))

    def test_lorentz_representations_are_not_on_shell_polarizations(self):
        for irreps, reality, expected in [
            ([['1/2', '0']], 'none', 4),
            ([['1/2', '1/2']], 'real', 4),
            ([['1/2', '1/2']], 'complex', 8),
            ([['1/2', '0'], ['0', '1/2']], 'none', 8),
            ([['1/2', '0'], ['0', '1/2']], 'majorana', 4),
        ]:
            with self.subTest(irreps=irreps, reality=reality):
                spec = single(reality=reality, lorentz={'dimension': 4, 'scheme': 'jL_jR', 'irreps': irreps})
                self.assertEqual(matter_dimension(canonical(spec)), expected)

    def test_higher_dimensional_lorentz_modules(self):
        for dimension, scheme, irreps, reality, expected in [
            (5, 'B2_Dynkin', [[1, 0]], 'real', 5),
            (5, 'B2_Dynkin', [[0, 1]], 'none', 8),
            (5, 'B2_Dynkin', [[0, 1]], 'majorana', 4),
            (6, 'D3_Dynkin', [[1, 0, 0]], 'real', 6),
            (6, 'D3_Dynkin', [[0, 1, 0]], 'none', 8),
            (6, 'D3_Dynkin', [[0, 1, 0], [0, 0, 1]], 'complex', 16),
        ]:
            with self.subTest(dimension=dimension, irreps=irreps, reality=reality):
                spec = single(reality=reality, lorentz={'dimension': dimension, 'scheme': scheme, 'irreps': irreps})
                self.assertEqual(matter_dimension(canonical(spec)), expected)

    def test_tensor_product_gauge_dimensions_and_restriction(self):
        spec = single(weight=(1, 0), charge='1', copies=3)
        spec['gauge_factors'].append({'id': 'h', 'family': 'A', 'rank': 1})
        spec['matter'][0]['gauge_representations']['h'] = {'dynkin': [1]}
        self.assertEqual(matter_dimension(canonical(spec)), 3 * 2 * 3 * 2)
        for weight in [(0,), (1,), (2,), (1, 0)]:
            for reality, lorentz in [('complex', None), ('complex', {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['1/2', '1/2']]})]:
                charged = single(weight=weight, charge='1', reality=reality, lorentz=lorentz, copies=3)
                with self.subTest(weight=weight, lorentz=lorentz):
                    self.assertEqual(matter_dimension(canonical(charged)),
                                     matter_dimension(restrict_nonabelian(charged)['canonical']))

    def test_symbolic_scalar_dimension_is_independent_of_charge_locus(self):
        family = single(charge='n', copies=3)
        family.update(schema_version='field-content-3', parameters={'n': {'domain': 'integer'}}, constraints=[])
        symbolic = canonical(family)
        self.assertEqual(matter_dimension(symbolic), 6)
        self.assertEqual(matter_dimension(restrict_nonabelian(family)['canonical']), 6)
        for value in [0, 1, 17]:
            with self.subTest(value=value):
                self.assertEqual(matter_dimension(canonical(specialize(family, {'n': value}))), 6)
        self.assertEqual(symbolic, canonical(family))

    def test_unresolved_representations_fail_instead_of_approximating(self):
        valid = canonical(single())
        bad_family = deepcopy(valid); bad_family['gauge_factors'][0]['family'] = '?'
        bad_weight = deepcopy(valid); bad_weight['matter'][0]['gauge'][0]['dynkin'] = [1, 0]
        bad_lorentz = deepcopy(valid); bad_lorentz['matter'][0]['lorentz']['scheme'] = 'unknown'
        bad_reality = deepcopy(valid); bad_reality['matter'][0]['reality'] = 'unknown'
        for bad in [bad_family, bad_weight, bad_lorentz, bad_reality]:
            with self.subTest(canonical=bad), self.assertRaises((ValueError, KeyError)):
                matter_dimension(bad)


class MatterOrdering(unittest.TestCase):
    def test_total_dimension_precedes_representation_tie_breaks(self):
        spectra = [canonical(single(reality='real', copies=n)) for n in [2, 10, 100]]
        self.assertEqual(sorted(reversed(spectra), key=matter_sort_key), spectra)

    def test_equal_dimensions_use_numeric_dynkin_labels(self):
        lower = canonical(single(weight=(2,), reality='real', copies=11))
        upper = canonical(single(weight=(10,), reality='real', copies=3))
        self.assertEqual(matter_dimension(lower), 33)
        self.assertEqual(matter_dimension(upper), 33)
        self.assertLess(matter_sort_key(lower), matter_sort_key(upper))

    def test_equal_dimensions_use_numeric_lorentz_spins(self):
        spectra = [canonical(single(reality='none', copies=copies,
                    lorentz={'dimension': 4, 'scheme': 'jL_jR', 'irreps': [[spin, '0']]}))
                   for spin, copies in [('2', 21), ('10', 5)]]
        self.assertEqual([matter_dimension(c) for c in spectra], [210, 210])
        self.assertLess(matter_sort_key(spectra[0]), matter_sort_key(spectra[1]))

    def test_equal_dimensions_use_exact_numeric_charges(self):
        base = canonical(single(reality='none', lorentz={'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['1/2', '0']]}))
        # Feed fixed canonical charge coordinates directly; normalization must
        # not rescale a charge as part of a presentation-only sorting key.
        spectra = []
        for charge in ['-10', '-2', '1/3', '1/2', '2', '10']:
            payload = deepcopy(base)
            payload['matter'][0]['gauge'][-1]['charge'] = charge
            spectra.append(payload)
        self.assertEqual(sorted(reversed(spectra), key=matter_sort_key), spectra)

    def test_canonical_splitting_permutations_and_names_preserve_order_key(self):
        spec = deepcopy(ENTRIES['lr-triplet-matter']['specification'])
        equivalent = deepcopy(spec)
        equivalent['gauge_factors'].reverse()
        equivalent['matter'].reverse()
        row = next(row for row in equivalent['matter'] if row['copies'] == 3)
        duplicate = deepcopy(row); duplicate['copies'] = 1
        row['copies'] = 2
        equivalent['matter'].append(duplicate)
        ids = {factor['id']: 'renamed-' + str(i) for i, factor in enumerate(equivalent['gauge_factors'])}
        for factor in equivalent['gauge_factors']:
            factor['id'] = ids[factor['id']]
        for row in equivalent['matter']:
            row['gauge_representations'] = {ids[name]: rep for name, rep in row['gauge_representations'].items()}
        self.assertEqual(matter_sort_key(canonical(spec)), matter_sort_key(canonical(equivalent)))
        self.assertEqual(matter_sort_key(restrict_nonabelian(spec)['canonical']),
                         matter_sort_key(restrict_nonabelian(equivalent)['canonical']))

    def test_symbolic_domain_metadata_breaks_remaining_ties(self):
        family = single(charge='n')
        family.update(schema_version='field-content-3', parameters={'n': {'domain': 'integer'}}, constraints=['n > 0'])
        different_domain = deepcopy(family); different_domain['constraints'] = ['n > 1']
        a, b = canonical(family), canonical(different_domain)
        self.assertEqual(matter_dimension(a), matter_dimension(b))
        self.assertNotEqual(matter_sort_key(a), matter_sort_key(b))
        self.assertEqual(sorted([a, b], key=matter_sort_key), sorted([b, a], key=matter_sort_key))

    def test_core_projection_uses_matter_dimension_within_the_algebra(self):
        ids = ['real-singlet-z2', 'complex-singlet-portal', 'two-higgs-doublets']
        entries = [deepcopy(ENTRIES[entry_id]) for entry_id in reversed(ids)]
        cores, _, _ = attach_layers(entries)
        self.assertEqual([group['entryIds'] for group in cores], [[entry_id] for entry_id in ids])
        self.assertEqual([matter_dimension(group['canonical']) for group in cores], [185, 186, 188])
        for entry in entries:
            self.assertEqual(entry['identity'], ENTRIES[entry['id']]['identity'])
            self.assertEqual(entry['specification'], ENTRIES[entry['id']]['specification'])

    def test_build_orders_full_entries_without_reordering_source(self):
        source = json.loads((ROOT / 'atlas/catalogue.json').read_text())
        ids = ['real-singlet-z2', 'complex-singlet-portal', 'two-higgs-doublets']
        by_id = {entry['id']: entry for entry in source['entries']}
        source['entries'] = [by_id[entry_id] for entry_id in reversed(ids)]
        before = deepcopy(source)
        built = main_data(source)
        self.assertEqual([entry['id'] for entry in built['entries']], ids)
        self.assertEqual(source, before)

    def test_generated_matter_layers_follow_the_same_precise_ranking(self):
        for name in ['entries', 'cores']:
            groups = DATA[name]
            key = lambda group: spectrum_sort_key(group['identity']['canonical'] if name == 'entries' else group['canonical']) + (group['id'],)
            with self.subTest(layer=name):
                for earlier, later in zip(groups, groups[1:]):
                    self.assertTrue(key(earlier) <= key(later),
                                    name + ': ' + earlier['id'] + ' precedes ' + later['id'])


if __name__ == '__main__':
    unittest.main()
