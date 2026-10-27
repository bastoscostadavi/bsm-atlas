"""Portable checks for the matched Terra follow-up; no private runs or calls."""
from collections import Counter
import json
from pathlib import Path
import unittest

from bsm_atlas.catalogue import identity, normalize

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'experiments/extraction-pilot'


def read(path):
    return json.loads(path.read_text())


class Terra61PilotTests(unittest.TestCase):
    def test_all_twenty_responses_and_usage_reconcile(self):
        data = read(HERE / 'terra61-results.json')
        baseline = next(r for r in read(HERE / 'results.json')['runs'] if r['id'] == 'sol61-revised')
        old = {row['paper']: row for row in baseline['records']}
        self.assertEqual(len(data['records']), 20)
        self.assertEqual({r['paper'] for r in data['records']}, set(old))
        usage = Counter()
        for row in data['records']:
            self.assertEqual(row['prompt_sha256'], old[row['paper']]['prompt_sha256'])
            usage.update(row['usage'])
        self.assertEqual(dict(usage), data['usage'])
        self.assertEqual(dict(Counter(row['audit_category'] for row in data['records'])), data['categories'])
        self.assertEqual(data['categories'], {'matched': 4, 'correct_skip': 14, 'false_skip': 1, 'unresolved': 1})
        cost = ((usage['input_tokens'] - usage['cached_input_tokens']) + .05 * usage['cached_input_tokens'] + 5 * usage['output_tokens']) / 1e6
        self.assertAlmostEqual(cost, data['api_equivalent_usd'])

    def test_inventory_matches_and_missing_extra_eft(self):
        data = read(HERE / 'terra61-results.json')
        for row in data['records']:
            if 'worker_response_summary' in row:
                from bsm_atlas.retention import seal
                self.assertEqual(row['bookkeeping_sha256'],seal({k:v for k,v in row.items() if k!='bookkeeping_sha256'}))
                actual = set(row['extracted_fingerprints'])
            else:
                raw = row['worker_response']
                actual = {identity(normalize(json.loads(item['specification_json'])))['fingerprint'] for item in raw['entries']}
            self.assertEqual(actual, set(row['extracted_fingerprints']))
            self.assertEqual(actual & set(row['reference_fingerprints']), set(row['recovered_reference_fingerprints']))
        modular = next(row for row in data['records'] if row['paper'] == '2610.29754v1')
        self.assertEqual(len(modular['extracted_fingerprints']), 1)
        self.assertEqual(len(modular['missing_reference_fingerprints']), 1)
        self.assertEqual(data['matched_spectra'], 4)
        self.assertEqual(data['sol_baseline']['matched_spectra'], 5)
        higher_spin = next(row for row in data['records'] if row['paper'] == '2610.29598v1')
        self.assertEqual(higher_spin.get('worker_response_summary',higher_spin.get('worker_response'))['outcome'], 'retry')


if __name__ == '__main__':
    unittest.main()
