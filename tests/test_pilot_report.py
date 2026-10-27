"""Offline consistency checks for the frozen pilot and manuscript tables."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = importlib.util.spec_from_file_location('pilot_summary', ROOT / 'experiments/extraction-pilot/summarize.py')
pilot = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(pilot)


class PilotReportTests(unittest.TestCase):
    def setUp(self):
        self.data = pilot.read(pilot.HERE / 'results.json')

    def test_snapshot_records_reconcile_without_private_runs(self):
        pilot.verify(self.data)
        self.assertEqual(sum(len(run['records']) for run in self.data['runs']), 20 * len(pilot.RUNS))
        original = [r for r in self.data['runs'] if r['id'] != 'sol61-revised']
        self.assertEqual(sum(r['usage']['input_tokens'] for r in original), 5274826)
        self.assertEqual(sum(r['usage']['output_tokens'] for r in original), 48906)

    def test_faulty_response_cannot_be_dropped_from_counts(self):
        altered = deepcopy(self.data)
        next(r for r in altered['runs'] if r['id'] == 'luna-revised')['counts']['faulty_response'] = 0
        with self.assertRaises(AssertionError):
            pilot.verify(altered)

    def test_worker_payload_change_is_detected(self):
        altered = deepcopy(self.data)
        record = altered['runs'][0]['records'][0]
        if 'worker_response_summary' in record:
            record['worker_response_summary']['outcome'] = 'Changed outcome'
        else:
            record['worker_response']['reason'] = 'Changed response'
        with self.assertRaises(AssertionError):
            pilot.verify(altered)

    def test_report_and_manuscript_rows_agree(self):
        for path in (pilot.HERE / 'README.md', ROOT / 'paper/main.tex'):
            for usage, key in ((False, 'PILOT RESULTS'), (True, 'PILOT USAGE')):
                pilot.marked(path, key, pilot.rows(self.data, latex=path.suffix == '.tex', usage=usage), False)
            pilot.marked(path, 'PILOT TOTALS', pilot.totals(self.data, latex=path.suffix == '.tex'), False)

    def test_multiple_spectra_and_deferred_review_are_not_worker_retries(self):
        run = next(r for r in self.data['runs'] if r['id'] == 'sol61-revised')
        self.assertEqual(run['counts']['matched'], 4)
        self.assertEqual(run['matched_spectra'], 5)
        self.assertEqual(run['worker_retries'], 0)
        self.assertEqual(run['review_deferred'], 1)


if __name__ == '__main__':
    unittest.main()
