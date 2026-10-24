"""Version-specific cross-batch deduplication; fixtures make no external calls."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from bsm_atlas import expansion, harvest
from bsm_atlas.build import database, main_data
from bsm_atlas.catalogue import exclusive_lock, load, source_lock, validate, write_json
from bsm_atlas.extraction_tracking import recorded_papers, record_extractions

ROOT = Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / 'atlas/examples/two-higgs-doublets.json').read_text())


class ExtractionTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'catalogue.json'
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
        self.path = self.base / 'papers.json'
        self.run = self.base / 'run'
        (self.base / 'source.txt').write_text('Complete version-matched article fixture. ' * 10)
        self.requests = [{'arxiv': '2501.00001v1', 'title': 'First fixture', 'authors': 'Fixture author', 'text': 'source.txt'},
                         {'arxiv': 'hep-ph/0503065v1', 'title': 'Second fixture', 'authors': 'Fixture author', 'text': 'source.txt'}]
        write_json(self.path, {'papers': self.requests})

    def prepare(self):
        harvest.prepare_batch(self.path, self.run, source=self.source)

    def job(self, name='2501.00001v1'):
        return self.run / 'jobs' / name

    def finish(self, name='2501.00001v1', *, outcome='skip'):
        entries = [] if outcome != 'entries' else [{'id': 'two-higgs-fixture', 'name': 'Two Higgs fixture',
            'specification_json': json.dumps(SPEC), 'locators': ['Table 1']}]
        write_json(self.job(name) / 'result.json', {'outcome': outcome, 'reason': 'Fixture source assessment.', 'entries': entries})
        write_json(self.job(name) / 'status.json', {'state': {'entries': 'review', 'skip': 'skipped', 'retry': 'retry'}[outcome]})

    def sync(self, write=True):
        return record_extractions(self.run, self.source, write, manifest_path=self.path)

    def test_valid_entries_and_no_model_outcomes_are_complete_but_not_ingested(self):
        self.prepare()
        self.finish(outcome='entries')
        self.finish('hep-ph-0503065v1')
        before = self.source.read_bytes()
        report = self.sync(False)
        self.assertTrue(report['dry_run'])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(report['counts'], {'complete': 2})
        self.sync()
        data = load(self.source)
        self.assertEqual(data['entries'], [])
        self.assertTrue(all(p['extraction_status'] == 'complete' for p in data['papers']))
        self.assertFalse(list(self.run.glob('jobs/*/review.json')))
        saved = self.source.read_bytes()
        self.assertFalse(self.sync()['source_changed'])
        self.assertEqual(self.source.read_bytes(), saved)

    def test_reordered_new_batch_skips_before_fetching_with_no_cache_dependency(self):
        self.prepare()
        self.finish()
        self.finish('hep-ph-0503065v1', outcome='entries')
        self.sync()
        other_path = self.base / 'different-ranking.json'
        write_json(other_path, {'papers': list(reversed(self.requests))})
        other_run = self.base / 'other-run'
        client = Mock()
        with patch('bsm_atlas.harvest.fetch_paper') as fetch:
            report = harvest.prepare_batch(other_path, other_run, source=self.source, client=client)
        fetch.assert_not_called()
        client.get.assert_not_called()
        self.assertEqual(report['counts'], {'already_recorded': 2})
        self.assertFalse(list(other_run.glob('jobs/*/paper.txt')))
        self.assertFalse(list(other_run.glob('jobs/*/attempt-*')))
        with patch('bsm_atlas.harvest.check_worker') as preflight:
            harvest.run_batch(other_run, True, executable='/does/not/exist')
        preflight.assert_not_called()
        self.assertEqual(harvest.ingest_batch(other_run, self.source)['ignored_jobs'], [])

    def test_prepared_jobs_are_rechecked_before_worker_dispatch_without_source_text(self):
        self.prepare()
        other_run = self.base / 'other-run'
        harvest.prepare_batch(self.path, other_run, source=self.source)
        self.finish()
        self.finish('hep-ph-0503065v1')
        self.sync()
        for path in other_run.glob('jobs/*/paper.txt'):
            path.unlink()
        before = {str(p): p.read_bytes() for p in other_run.glob('jobs/*/status.json')}
        with patch('bsm_atlas.harvest.check_worker') as preflight:
            preview = harvest.run_batch(other_run)
            self.assertEqual(preview['jobs'], [])
            self.assertEqual(before, {str(p): p.read_bytes() for p in other_run.glob('jobs/*/status.json')})
            report = harvest.run_batch(other_run, True, executable='/does/not/exist')
        preflight.assert_not_called()
        self.assertEqual(report['counts'], {'already_recorded': 2})

    def test_every_recorded_version_is_skipped_regardless_of_extraction_status(self):
        self.prepare()
        paper = harvest.checked_job(self.job())['paper']
        for alterations in ({}, {'extraction_status': 'unresolved'},
                            {'extraction_status': 'complete'}, {'extraction_status': 'not_started'}):
            with self.subTest(alterations=alterations):
                stored = {**paper, **alterations}
                write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [stored], 'entries': []})
                self.assertIn('2501.00001v1', recorded_papers(self.source))
                destination = self.base / ('retry-' + str(len(list(self.base.glob('retry-*')))))
                with patch('bsm_atlas.harvest.fetch_paper', wraps=harvest.fetch_paper) as fetch:
                    report = harvest.prepare_batch(self.path, destination, source=self.source)
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(report['counts'], {'already_recorded': 1, 'ready': 1})

    def test_a_different_exact_version_is_new_but_changed_conventions_do_not_reopen_old_papers(self):
        self.prepare()
        paper = harvest.checked_job(self.job())['paper']
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [
            {**paper, 'id': 'version-two', 'arxiv': '2501.00001v2', 'extraction_status': 'complete'}], 'entries': []})
        report = harvest.prepare_batch(self.path, self.base / 'version-check', source=self.source)
        self.assertEqual(report['counts'], {'ready': 2})
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [paper], 'entries': []})
        with patch('bsm_atlas.harvest.context', return_value=harvest.context() + '\nChanged instructions.'):
            report = harvest.prepare_batch(self.path, self.base / 'convention-check', source=self.source)
        self.assertEqual(report['counts'], {'already_recorded': 1, 'ready': 1})

    def test_retry_invalid_and_retrieval_failures_are_unresolved_not_complete(self):
        self.prepare()
        self.finish(outcome='retry')
        write_json(self.job('hep-ph-0503065v1') / 'status.json', {'state': 'invalid'})
        report = self.sync()
        self.assertEqual(report['counts'], {'unresolved': 2})
        self.assertTrue(all(p['extraction_status'] == 'unresolved' for p in recorded_papers(self.source).values()))
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
        other = self.base / 'failed-run'
        with patch('bsm_atlas.harvest.fetch_paper', side_effect=ValueError('Unreadable source')):
            harvest.prepare_batch(self.path, other, source=self.source)
        report = record_extractions(other, self.source, True, manifest_path=self.path)
        self.assertEqual(report['counts'], {'unresolved': 2})

    def test_pending_and_running_jobs_are_not_marked_complete(self):
        self.prepare()
        write_json(self.job() / 'status.json', {'state': 'running'})
        report = self.sync()
        self.assertEqual(len(report['ignored']), 2)
        self.assertEqual(load(self.source)['papers'], [])

    def test_old_failures_require_explicit_retry_flags(self):
        with patch('bsm_atlas.harvest.fetch_paper', side_effect=ValueError('Unreadable source')):
            self.prepare()
        self.sync()
        with patch('bsm_atlas.harvest.fetch_paper', wraps=harvest.fetch_paper) as fetch:
            report = harvest.prepare_batch(self.path, self.run, resume=True, source=self.source, retry=True)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(report['counts'], {'ready': 2})

        def worker(job, *_):
            self.finish(Path(job).name)

        with patch('bsm_atlas.harvest.check_worker'), patch('bsm_atlas.harvest.run_job', side_effect=worker) as launch:
            report = harvest.run_batch(self.run, True, retry=True)
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(report['counts'], {'ingested': 2})
        self.assertTrue(all(p['extraction_status'] == 'complete' for p in load(self.source)['papers']))

    def test_new_only_expansion_records_retrieval_failures_after_skipping_old_papers(self):
        self.prepare()
        self.finish()
        self.finish('hep-ph-0503065v1')
        self.sync()
        new = {**self.requests[0], 'arxiv': '2501.00003v1'}
        write_json(self.path, {'papers': [*self.requests, new]})
        with (patch('bsm_atlas.expansion.check_worker'),
              patch('bsm_atlas.harvest.fetch_paper', side_effect=ValueError('Unsupported source')) as fetch,
              patch('bsm_atlas.expansion.run_job') as worker, redirect_stdout(io.StringIO())):
            report = expansion.expand_batch(self.path, self.base / 'new-only-expansion', execute=True,
                                             source=self.source, fetch_size=1)
        self.assertEqual(fetch.call_count, 1)
        worker.assert_not_called()
        self.assertEqual(report['counts'], {'already_recorded': 2, 'retry': 1})
        self.assertEqual(recorded_papers(self.source)[new['arxiv']]['extraction_status'], 'unresolved')

    def test_older_failure_cannot_overwrite_a_completed_result(self):
        self.prepare()
        old_run = self.base / 'older-run'
        harvest.prepare_batch(self.path, old_run, source=self.source)
        write_json(old_run / 'jobs/2501.00001v1/status.json', {'state': 'retry'})
        self.finish()
        self.sync()
        record_extractions(old_run, self.source, True)
        self.assertEqual(load(self.source)['papers'][0]['extraction_status'], 'complete')

    def test_legacy_review_records_are_not_an_approval_gate(self):
        self.prepare()
        self.finish(outcome='entries')
        self.sync()
        write_json(self.job() / 'review.json', {'decision': 'rejected', 'artifact_sha256': 'legacy-gate'})
        self.sync()
        report = harvest.ingest_batch(self.run, self.source, True)
        self.assertEqual(report['new_entries'], 1)
        self.assertEqual(load(self.source)['papers'][0]['extraction_status'], 'complete')

    def test_mismatched_results_tampered_sources_and_wrong_manifests_fail_atomically(self):
        self.prepare()
        self.finish()
        self.finish('hep-ph-0503065v1')
        before = self.source.read_bytes()
        write_json(self.job('hep-ph-0503065v1') / 'status.json', {'state': 'review'})
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.sync()
        self.assertEqual(before, self.source.read_bytes())
        self.finish('hep-ph-0503065v1')
        (self.job() / 'paper.txt').write_text('Tampered source')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.sync()
        self.assertEqual(before, self.source.read_bytes())
        other = self.base / 'another-manifest.json'
        write_json(other, {'papers': self.requests})
        with self.assertRaisesRegex(ValueError, 'original frozen manifest'):
            record_extractions(self.run, self.source, True, manifest_path=other)

    def test_paper_ids_are_reused_and_completion_does_not_require_model_links(self):
        self.prepare()
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [
            {'id': 'original-id', 'arxiv': '2501.00001v1', 'title': 'Existing title', 'authors': 'Author'}], 'entries': []})
        self.finish()
        self.sync()
        papers = load(self.source)['papers']
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]['id'], 'original-id')
        self.assertEqual(papers[0]['extraction_status'], 'complete')

    def test_backfill_obeys_catalogue_and_run_locks(self):
        self.prepare()
        self.finish()
        before = self.source.read_bytes()
        for lock in (lambda: source_lock(self.source), lambda: exclusive_lock(self.run / 'run.lock')):
            with lock(), self.assertRaisesRegex(ValueError, 'lock'):
                self.sync()
            self.assertEqual(self.source.read_bytes(), before)

    def test_completed_markers_are_validated_and_exported_in_existing_sqlite_table(self):
        self.prepare()
        self.finish()
        self.sync()
        data = load(self.source)
        destination = self.base / 'export.sqlite'
        database(destination, main_data(data))
        with closing(sqlite3.connect(destination)) as con:
            self.assertEqual(con.execute('SELECT extraction_status FROM papers').fetchone(), ('complete',))
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE papers SET extraction_status='pending'")
        for updates in ({'extraction_status': 'arbitrary'}, {'extraction_status': None},
                        {'extraction_status': False}):
            altered = deepcopy(data)
            altered['papers'][0].update(updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                validate(altered)

    def test_status_cli_defaults_to_preview_and_never_calls_a_model(self):
        self.prepare()
        self.finish()
        before = self.source.read_bytes()
        result = subprocess.run([sys.executable, '-B', '-m', 'bsm_atlas', 'harvest', 'sync-status',
            str(self.run), '--source', str(self.source), '--manifest', str(self.path)],
            cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(result.stdout)['dry_run'])
        self.assertEqual(before, self.source.read_bytes())

    def test_rolling_expansion_reuses_completed_papers_in_a_new_run(self):
        self.prepare()
        self.finish()
        self.finish('hep-ph-0503065v1')
        self.sync()
        with (patch('bsm_atlas.expansion.check_worker'), patch('bsm_atlas.expansion.run_job') as worker,
              redirect_stdout(io.StringIO())):
            report = expansion.expand_batch(self.path, self.base / 'new-expansion', execute=True,
                                             source=self.source, fetch_size=1)
        worker.assert_not_called()
        self.assertEqual(report['phase'], 'extraction_complete')
        self.assertEqual(report['counts'], {'already_recorded': 2})
        self.assertEqual(report['model_writes'], 0)


if __name__ == '__main__':
    unittest.main()
