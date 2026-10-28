"""Exact-result caches must not weaken input validation or share mutable data."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bsm_atlas.json_memo import memoized_specification
from bsm_atlas.catalogue_identity import canonicalize, normalize_spec
from bsm_atlas.nonabelian_core import restrict_nonabelian
from bsm_atlas.presentation import matrix


class JsonMemoTests(unittest.TestCase):
    def test_content_changes_miss_and_callers_cannot_poison_results(self):
        calls = []

        @memoized_specification(maxsize=2)
        def calculate(spec):
            calls.append(deepcopy(spec))
            return {'nested': [spec]}

        value = {'a': [1], 'b': True}
        first = calculate(value)
        first['nested'][0]['a'].append(999)
        self.assertEqual(calculate({'b': True, 'a': [1]}), {'nested': [value]})
        self.assertEqual(len(calls), 1)
        value['a'].append(2)
        self.assertEqual(calculate(value)['nested'][0]['a'], [1, 2])
        self.assertEqual(len(calls), 2)
        calculate({'other': 1})
        self.assertEqual(calculate.cache_info().currsize, 2)

    def test_python_types_are_not_coerced_into_previously_valid_json(self):
        calls = []

        @memoized_specification()
        def calculate(spec):
            calls.append(spec)
            if type(spec['values']) is not list:
                raise ValueError('Expected a list')
            return type(spec['values'][0]).__name__

        self.assertEqual(calculate({'values': [1]}), 'int')
        self.assertEqual(calculate({'values': [True]}), 'bool')
        self.assertEqual(calculate({'values': [1.0]}), 'float')
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'Expected a list'):
                calculate({'values': (1,)})
        self.assertEqual(len(calls), 5)

    def test_exceptions_are_never_cached(self):
        calls = []

        @memoized_specification()
        def reject(spec):
            calls.append(spec)
            raise ValueError('Invalid specification')

        for _ in range(2):
            with self.assertRaises(ValueError):
                reject({'invalid': True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(reject.cache_info().currsize, 0)

    def test_real_calculations_match_uncached_results_and_return_owned_copies(self):
        root = Path(__file__).resolve().parent.parent
        spec = json.loads((root/'atlas/examples/two-higgs-doublets.json').read_text())
        original = deepcopy(spec)
        for function in (normalize_spec, canonicalize, restrict_nonabelian, matrix):
            with self.subTest(function=function.__name__):
                expected = function.__wrapped__(deepcopy(spec))
                result = function(spec)
                self.assertEqual(result, expected)
                result.clear()
                self.assertEqual(function(spec), expected)
        self.assertEqual(spec, original)
        # A warm cache must not turn a tuple into an accepted Dynkin-label list.
        invalid = deepcopy(spec)
        factor = next(a['id'] for a in spec['gauge_factors'] if a['family'] != 'U1')
        rep = invalid['matter'][0]['gauge_representations'][factor]
        rep['dynkin'] = tuple(rep['dynkin'])
        with self.assertRaises(ValueError):
            normalize_spec(invalid)


if __name__ == '__main__':
    unittest.main()
