"""Offline rolling-coordinator regressions; no model or network service calls."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from bsm_atlas import expansion, harvest
from bsm_atlas.catalogue import exclusive_lock, write_json


class RollingExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'catalogue.json'
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
        self.path = self.base / 'papers.json'
        self.directory = self.base / 'run'
        (self.base / 'paper.txt').write_text('Complete local source fixture. ' * 20)
        self.requests = [{'arxiv': f'2502.{i:05d}v1', 'title': f'Fixture {i}',
                          'authors': 'Fixture author', 'text': 'paper.txt'} for i in range(1, 11)]
        write_json(self.path, {'papers': self.requests})

    def expand(self, **kwargs):
        options = {'execute': True, 'source': self.source, 'executable': 'offline-fixture',
                   'fetch_size': 10}
        options.update(kwargs)
        with redirect_stdout(io.StringIO()), patch('bsm_atlas.expansion.check_worker'):
            return expansion.expand_batch(self.path, self.directory, **options)

    @staticmethod
    def finish(job, *, failure=False):
        """Produce the same terminal files the coordinator reads from a real worker."""
        job = Path(job)
        attempt = job / 'attempt-0001'
        attempt.mkdir()
        usage = None if failure else {'input_tokens': 100, 'output_tokens': 10}
        write_json(attempt / 'metrics.json', {'model': 'gpt-6.1-sol', 'reasoning': 'medium',
                                             'elapsed_seconds': 0.01, 'usage': usage})
        if failure:
            outcome = {'state': 'retry', 'reason': 'Worker exited with status 7; quota fixture'}
        else:
            write_json(job / 'result.json', {'outcome': 'skip',
                                            'reason': 'Fixture has no eligible model.', 'entries': []})
            outcome = {'state': 'skipped', 'reason': 'Fixture has no eligible model.'}
        write_json(job / 'status.json', outcome)
        return outcome

    def quick_worker(self, job, *_):
        write_json(Path(job) / 'status.json', {'state': 'running', 'model': 'gpt-6.1-sol'})
        return self.finish(job)

    def job_snapshots(self):
        return {str(path.relative_to(self.directory)): path.read_bytes()
                for path in (self.directory / 'jobs').rglob('*') if path.is_file()}

    def completed_run(self):
        with patch('bsm_atlas.expansion.run_job', side_effect=self.quick_worker):
            result = self.expand(workers=2)
        self.assertEqual(result['counts'], {'ingested': 10})
        return self.job_snapshots()

    def test_six_workers_are_busy_concurrently_and_never_exceed_the_limit(self):
        guard = threading.Lock()
        first_six = threading.Barrier(6, timeout=4)
        active = peak = calls = 0

        def worker(job, *_):
            nonlocal active, peak, calls
            with guard:
                calls += 1
                number = calls
                active += 1
                peak = max(peak, active)
            write_json(Path(job) / 'status.json', {'state': 'running'})
            try:
                if number <= 6:
                    first_six.wait()
                return self.finish(job)
            finally:
                with guard:
                    active -= 1

        with patch('bsm_atlas.expansion.run_job', side_effect=worker):
            report = self.expand(workers=6)
        self.assertEqual(report['phase'], 'extraction_complete')
        self.assertEqual(report['counts'], {'ingested': 10})
        self.assertEqual((peak, active, calls), (6, 0, 10))
        self.assertEqual(report['usage']['input_tokens'], 1000)
        self.assertTrue(all(job['attempts'] == 1 for job in harvest.status(self.directory)['jobs']))

    def test_freed_worker_is_replaced_before_the_slow_first_paper_finishes(self):
        replacement_started = threading.Event()
        first_finished = threading.Event()
        observations = []

        def worker(job, *_):
            write_json(Path(job) / 'status.json', {'state': 'running'})
            if Path(job).name == '2502.00001v1':
                observations.append(replacement_started.wait(4))
                first_finished.set()
            elif Path(job).name == '2502.00003v1':
                observations.append(not first_finished.is_set())
                replacement_started.set()
            return self.finish(job)

        with patch('bsm_atlas.expansion.run_job', side_effect=worker):
            report = self.expand(workers=2)
        self.assertEqual(report['phase'], 'extraction_complete')
        self.assertEqual(observations, [True, True])

    def test_second_source_download_overlaps_first_paper_inference(self):
        worker_started = threading.Event()
        second_downloaded = threading.Event()
        observed = []
        original_fetch = harvest.fetch_paper
        fetched = 0

        def fetch(*args, **kwargs):
            nonlocal fetched
            fetched += 1
            if fetched == 2:
                observed.append(worker_started.wait(4))
                second_downloaded.set()
            return original_fetch(*args, **kwargs)

        def worker(job, *_):
            write_json(Path(job) / 'status.json', {'state': 'running'})
            if Path(job).name == '2502.00001v1':
                worker_started.set()
                observed.append(second_downloaded.wait(4))
            return self.finish(job)

        with patch('bsm_atlas.harvest.fetch_paper', side_effect=fetch), patch(
                'bsm_atlas.expansion.run_job', side_effect=worker):
            report = self.expand(workers=2, fetch_size=1)
        self.assertEqual(report['phase'], 'extraction_complete')
        self.assertEqual(observed, [True, True])
        self.assertEqual(fetched, 10)

    def test_stop_drains_existing_workers_without_submitting_more(self):
        first_three = threading.Barrier(3, timeout=4)
        stop_present = threading.Event()
        calls = []
        guard = threading.Lock()

        def worker(job, *_):
            with guard:
                calls.append(Path(job).name)
            write_json(Path(job) / 'status.json', {'state': 'running'})
            first_three.wait()
            if Path(job).name == '2502.00001v1':
                (self.directory / 'STOP').touch()
                stop_present.set()
            else:
                self.assertTrue(stop_present.wait(4))
            return self.finish(job)

        with patch('bsm_atlas.expansion.run_job', side_effect=worker):
            report = self.expand(workers=3)
        self.assertEqual(report['phase'], 'stopped')
        self.assertIn('STOP', report['reason'])
        self.assertEqual(set(calls), {'2502.00001v1', '2502.00002v1', '2502.00003v1'})
        self.assertEqual(report['counts'].get('ingested'), 3)
        self.assertNotIn('running', report['counts'])
        (self.directory / 'STOP').unlink()
        with patch('bsm_atlas.expansion.run_job', side_effect=self.quick_worker):
            final = self.expand(workers=3, resume=True)
        self.assertEqual(final['counts'], {'ingested': 10})
        self.assertTrue(all(job['attempts'] == 1 for job in harvest.status(self.directory)['jobs']))

    def test_quota_or_process_failure_drains_but_does_not_launch_replacements(self):
        first_three = threading.Barrier(3, timeout=4)
        failure_written = threading.Event()
        calls = []
        guard = threading.Lock()

        def worker(job, *_):
            with guard:
                calls.append(Path(job).name)
            write_json(Path(job) / 'status.json', {'state': 'running'})
            first_three.wait()
            if Path(job).name == '2502.00001v1':
                result = self.finish(job, failure=True)
                failure_written.set()
                return result
            self.assertTrue(failure_written.wait(4))
            return self.finish(job)

        with patch('bsm_atlas.expansion.run_job', side_effect=worker):
            report = self.expand(workers=3)
        self.assertEqual(report['phase'], 'stopped')
        self.assertIn('auth/quota', report['reason'])
        self.assertEqual(len(calls), 3)
        self.assertEqual(report['counts'].get('retry'), 1)
        self.assertEqual(report['counts'].get('ingested'), 2)
        self.assertNotIn('running', report['counts'])
        self.assertEqual(report['unreported_attempts'], 1)

    def test_explicit_concurrency_reconfigure_preserves_completed_attempts(self):
        before = self.completed_run()
        with patch('bsm_atlas.expansion.run_job') as launch:
            with self.assertRaisesRegex(ValueError, 'settings or inputs changed'):
                self.expand(workers=6, fetch_size=7, resume=True)
            report = self.expand(workers=6, fetch_size=7, resume=True, reconfigure=True)
        launch.assert_not_called()
        self.assertEqual(before, self.job_snapshots())
        self.assertEqual(report['counts'], {'ingested': 10})
        configuration = harvest.read_json(self.directory / 'expansion.json')['config']
        self.assertEqual(configuration['workers'], 6)
        self.assertEqual(configuration['fetch_size'], 7)

    def test_reconfigure_requires_explicit_resume(self):
        with self.assertRaisesRegex(ValueError, 'resume'):
            self.expand(workers=6, reconfigure=True)
        self.assertFalse(self.directory.exists())

    def test_reconfigure_cannot_change_model_or_scientific_worker_settings(self):
        self.completed_run()
        before = (self.directory / 'expansion.json').read_bytes()
        for changes in ({'model': 'gpt-6-sol'}, {'reasoning': 'high'}, {'timeout': 901},
                        {'executable': 'different-fixture'}, {'source': self.base / 'other.json'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.expand(workers=6, resume=True, reconfigure=True, **changes)
            self.assertEqual((self.directory / 'expansion.json').read_bytes(), before)

    def test_reconfigure_cannot_change_manifest_or_prompt_context(self):
        self.completed_run()
        before = (self.directory / 'expansion.json').read_bytes()
        with patch('bsm_atlas.expansion.context', return_value=harvest.context() + '\nChanged convention.'):
            with self.assertRaises(ValueError):
                self.expand(workers=6, resume=True, reconfigure=True)
        write_json(self.path, {'papers': list(reversed(self.requests))})
        with self.assertRaises(ValueError):
            self.expand(workers=6, resume=True, reconfigure=True)
        self.assertEqual((self.directory / 'expansion.json').read_bytes(), before)

    def test_reconfigure_refuses_active_expansion_or_run_lock(self):
        self.completed_run()
        before = (self.directory / 'expansion.json').read_bytes()
        for name in ('expansion.lock', 'run.lock'):
            with self.subTest(lock=name), exclusive_lock(self.directory / name):
                with self.assertRaisesRegex(ValueError, 'lock'):
                    self.expand(workers=6, resume=True, reconfigure=True)
            self.assertEqual((self.directory / 'expansion.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
