"""Syntactic family identity; deliberately no parameter-domain solver."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'atlas'))
from charge_expressions import parse_charge, parse_constraints
from symbolic_identity import canonicalize_family
from catalogue_identity import IncompleteContent
from prepare_entry import prepare
from check_entry import check


def family():
    return {'schema_version': 'field-content-3', 'inventory_complete': True,
            'parameters': {'n': {'domain': 'integer'}, 'm': {'domain': 'integer'}},
            'constraints': ['n > 0', 'm < 4'],
            'gauge_factors': [{'id': 'colour', 'family': 'A', 'rank': 2},
                              {'id': 'left', 'family': 'A', 'rank': 1},
                              {'id': 'right', 'family': 'A', 'rank': 1},
                              {'id': 'X', 'family': 'U1', 'rank': 1}],
            'matter': [{'label': 'psi', 'copies': 3, 'reality': 'none',
                        'lorentz': {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['1/2', '0']]},
                        'gauge_representations': {'colour': {'dynkin': [1, 0]},
                                                 'left': {'dynkin': [1]},
                                                 'right': {'dynkin': [0]},
                                                 'X': {'charge': '(n+m)**2'}}},
                       {'label': 'chi', 'copies': 1, 'reality': 'none',
                        'lorentz': {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['1/2', '0']]},
                        'gauge_representations': {'colour': {'dynkin': [0, 0]},
                                                 'left': {'dynkin': [0]},
                                                 'right': {'dynkin': [1]},
                                                 'X': {'charge': 'n-m'}}}]}


def renamed(spec, mapping):
    result = deepcopy(spec)
    names = tuple(sorted(spec['parameters']))
    result['parameters'] = {mapping[name]: declaration for name, declaration in spec['parameters'].items()}
    from symbolic_identity import _rename
    target_names = tuple(sorted(mapping.values()))
    for row in result['matter']:
        for factor in result['gauge_factors']:
            if factor['family'] == 'U1':
                rep = row['gauge_representations'][factor['id']]
                rep['charge'] = _rename(parse_charge(rep['charge'], names), mapping, target_names)
    result['constraints'] = [_rename(a, mapping, target_names) + ' ' + op + ' ' + _rename(b, mapping, target_names)
                             for a, op, b, _ in parse_constraints(spec['constraints'], names)]
    return result


class SymbolicIdentity(unittest.TestCase):
    def test_expansion_names_and_idempotence(self):
        source = family()
        unchanged = deepcopy(source)
        result = canonicalize_family(source)
        self.assertEqual(source, unchanged)
        self.assertEqual(list(result['normalized_entry']['parameters']), ['z1', 'z2'])
        self.assertEqual(result['normalized_entry']['matter'][0]['gauge_representations']['X']['charge'], 'z1**2 + 2*z1*z2 + z2**2')
        again = canonicalize_family(result['normalized_entry'])
        self.assertEqual(again['normalized_entry'], result['normalized_entry'])
        self.assertEqual(again['fingerprint'], result['fingerprint'])
        result['normalized_entry']['parameters'].clear()
        self.assertEqual(len(canonicalize_family(source)['normalized_entry']['parameters']), 2)

    def test_consistent_parameter_renaming_and_expansion(self):
        a = family()
        b = renamed(a, {'m': 'a', 'n': 'zz'})
        b['matter'][0]['gauge_representations']['X']['charge'] = 'zz**2 + 2*a*zz + a**2'
        self.assertEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])
        c = renamed(a, {'n': 'z2', 'm': 'z1'})
        self.assertEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(c)['fingerprint'])

    def test_factor_ids_rows_and_identical_factor_permutations(self):
        a = family()
        b = deepcopy(a)
        b['gauge_factors'].reverse()
        b['matter'].reverse()
        b['matter'][0]['label'] = 'another paper name'
        for row in b['matter']:
            reps = row['gauge_representations']
            reps['left'], reps['right'] = reps['right'], reps['left']
        id_map = {factor['id']: 'factor-' + str(i) for i, factor in enumerate(b['gauge_factors'])}
        for row in b['matter']:
            row['gauge_representations'] = {id_map[key]: value for key, value in row['gauge_representations'].items()}
        for factor in b['gauge_factors']:
            factor['id'] = id_map[factor['id']]
        self.assertEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])

    def test_row_splitting_not_multiplicity_change(self):
        a = family()
        b = deepcopy(a)
        b['matter'][0]['copies'] = 2
        row = deepcopy(b['matter'][0]); row['copies'] = 1
        b['matter'].append(row)
        self.assertEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])
        b['matter'][-1]['copies'] = 2
        self.assertNotEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])

    def test_domains_are_preserved_not_solved_or_ignored(self):
        a = family()
        b = deepcopy(a); b['constraints'][0] = 'n >= 1'
        self.assertNotEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])
        b = deepcopy(a); b['constraints'] = []
        self.assertNotEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])
        b = deepcopy(a); b['constraints'].reverse(); b['constraints'].append('n > 0')
        self.assertEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])

    def test_general_parameter_substitution_not_claimed_equivalent(self):
        a = family()
        b = deepcopy(a)
        b['matter'][0]['gauge_representations']['X']['charge'] = '(n+m+1)**2'
        b['matter'][1]['gauge_representations']['X']['charge'] = 'n+1-m'
        b['constraints'][0] = 'n+1 > 0'
        self.assertNotEqual(canonicalize_family(a)['fingerprint'], canonicalize_family(b)['fingerprint'])

    def test_source_parameter_assignments_still_use_source_names(self):
        source = family()
        result = prepare(source, values={'n': 1, 'm': 2})
        standardized = prepare(source)
        values = {standardized['parameter_renaming'][key]: value for key, value in {'n': 1, 'm': 2}.items()}
        self.assertEqual(result['fingerprint'], prepare(standardized['normalized_entry'], values=values)['fingerprint'])
        self.assertEqual(result['parameter_assignment'], {'n': 1, 'm': 2})

    def test_resource_bound_is_explicit_not_a_nonmatch(self):
        source = family()
        source['parameters'] = {'p' + str(i): {'domain': 'integer'} for i in range(7)}
        source['constraints'] = []
        source['matter'][0]['gauge_representations']['X']['charge'] = '+'.join(source['parameters'])
        source['matter'][1]['gauge_representations']['X']['charge'] = 'p0'
        with self.assertRaisesRegex(IncompleteContent, 'safe search bound'):
            prepare(source)
        self.assertTrue(prepare(source, values={name: 1 for name in source['parameters']})['fingerprint'])

    def test_published_family_lookup_names_order_and_references(self):
        data = json.loads((ROOT / 'website/field-catalogue.json').read_text())
        for entry in data['entries']:
            source = entry['specification']
            if source['schema_version'] != 'field-content-3':
                continue
            with self.subTest(entry=entry['id']):
                result = canonicalize_family(source)
                self.assertEqual(result['normalized_entry'], source)
                self.assertEqual(result['fingerprint'], entry['identity']['fingerprint'])
                candidate = renamed(source, {name: 'parameter' + str(i) for i, name in enumerate(source['parameters'])})
                candidate['gauge_factors'].reverse()
                candidate['matter'].reverse()
                report = check(candidate, ROOT / 'website/downloads/field-catalogue.sqlite')
                self.assertEqual(report['status'], 'exact_symbolic_template_match')
                self.assertIn(entry['id'], [match['entry_id'] for match in report['matches']])
                for ref in entry['references']:
                    self.assertLessEqual(set(ref.get('parameter_names',{}).values()),set(source['parameters']))


if __name__ == '__main__':
    unittest.main()
