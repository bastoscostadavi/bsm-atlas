"""Offline expansion tests. Fixture workers make no service calls."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from bsm_atlas import expansion, harvest, papers
from bsm_atlas.catalogue import write_json


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'catalogue.json'
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
        self.path = self.base / 'papers.json'
        self.directory = self.base / 'run'
        (self.base / 'paper.txt').write_text('Full source article fixture. ' * 20)
        self.requests = [{'arxiv': f'2501.{i:05d}v1', 'title': f'Fixture {i}',
                          'authors': 'Fixture author', 'text': 'paper.txt'} for i in range(1, 6)]
        write_json(self.path, {'papers': self.requests})
        self.executable = self.base / 'fixture-worker'
        self.executable.write_text(
            '#!' + sys.executable + '\n'
            'import json,pathlib,sys\n'
            'if "--help" in sys.argv:\n'
            ' print("--output-schema --output-last-message --json --ignore-user-config --ephemeral");sys.exit(0)\n'
            'sys.stdin.read()\n'
            'out=pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1])\n'
            'out.write_text(json.dumps({"outcome":"skip","reason":"Fixture establishes no BSM extension.","entries":[]}))\n'
            'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":10}}))\n')
        self.executable.chmod(0o700)

    def run_expansion(self, **kwargs):
        with redirect_stdout(io.StringIO()):
            return expansion.expand_batch(self.path, self.directory, executable=self.executable,
                                          source=self.source, **kwargs)

    def test_dry_run_makes_no_files_or_calls(self):
        with patch('bsm_atlas.expansion.check_worker') as check:
            report = self.run_expansion()
        self.assertTrue(report['dry_run'])
        self.assertEqual(report['papers'], 5)
        self.assertFalse(self.directory.exists())
        check.assert_not_called()

    def test_incremental_prepare_initializes_all_jobs_and_preserves_order(self):
        first = harvest.prepare_batch(self.path, self.directory, source=self.source, limit=2)
        self.assertEqual(first['counts'], {'ready': 2, 'pending': 3})
        second = harvest.prepare_batch(self.path, self.directory, resume=True, source=self.source,
                                       limit=2, pending_only=True)
        self.assertEqual(second['counts'], {'ready': 4, 'pending': 1})
        self.assertEqual(second['jobs'][0]['job'], '2501.00001v1')

    def test_full_run_checkpoints_usage_and_ingests_without_approval(self):
        before = self.source.read_bytes()
        report = self.run_expansion(execute=True, fetch_size=2)
        self.assertEqual(report['phase'], 'extraction_complete')
        self.assertEqual(report['counts'], {'ingested': 5})
        self.assertEqual(report['usage']['input_tokens'], 500)
        self.assertEqual(report['model_writes'], 0)
        registered = json.loads(self.source.read_text())
        self.assertEqual(registered['entries'], json.loads(before)['entries'])
        self.assertEqual(len(registered['papers']), 5)
        self.assertTrue(all(p['extraction_status'] == 'complete' for p in registered['papers']))
        self.assertFalse(list(self.directory.glob('jobs/*/review.json')))
        final = self.run_expansion(execute=True, fetch_size=2, resume=True)
        self.assertEqual(final['usage'], report['usage'])
        self.assertEqual(sum(job['attempts'] for job in harvest.status(self.directory)['jobs']), 5)

    def test_completed_workers_are_ingested_in_one_validated_batch(self):
        def all_complete(futures, **kwargs):
            for future in futures:
                future.result()
            return set(futures), set()

        with patch('bsm_atlas.expansion.wait', side_effect=all_complete), patch(
                'bsm_atlas.expansion.ingest_batch', wraps=harvest.ingest_batch) as intake, patch(
                'bsm_atlas.expansion.record_extractions', wraps=expansion.record_extractions) as tracking:
            report = self.run_expansion(execute=True, workers=5, fetch_size=5)
        self.assertEqual(report['counts'], {'ingested': 5})
        self.assertEqual(intake.call_count, 1)
        self.assertEqual(len(intake.call_args.kwargs['jobs']), 5)
        tracking.assert_not_called()
        registered = json.loads(self.source.read_text())
        self.assertTrue(all(p['extraction_status'] == 'complete' for p in registered['papers']))

    def test_failed_worker_stops_before_launching_entire_manifest(self):
        self.executable.write_text(self.executable.read_text().replace(
            'sys.stdin.read()\n', 'sys.stdin.read()\nsys.exit(7)\n'))
        report = self.run_expansion(execute=True, fetch_size=5)
        self.assertEqual(report['phase'], 'stopped')
        self.assertIn('auth/quota', report['reason'])
        self.assertEqual(report['counts'], {'retry': 2, 'ready': 3})
        self.assertEqual(sum(job['attempts'] for job in harvest.status(self.directory)['jobs']), 2)

    def test_stop_file_preserves_ready_jobs_and_resumes_without_duplicate_calls(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source, limit=2)
        # Adopt only directories created by the expansion itself, not arbitrary runs.
        with self.assertRaisesRegex(ValueError, 'not an expansion'):
            self.run_expansion(execute=True, resume=True)

    def test_stop_file_is_checked_between_worker_windows(self):
        original = expansion.run_job

        def stop_after_window(*args, **kwargs):
            report = original(*args, **kwargs)
            (self.directory / 'STOP').touch()
            return report

        with patch('bsm_atlas.expansion.run_job', side_effect=stop_after_window):
            report = self.run_expansion(execute=True)
        self.assertEqual(report['phase'], 'stopped')
        snapshot = harvest.status(self.directory)
        self.assertLessEqual(sum(job['attempts'] for job in snapshot['jobs']), 2)
        self.assertGreaterEqual(report['counts'].get('ingested', 0), 1)
        (self.directory / 'STOP').unlink()
        final = self.run_expansion(execute=True, resume=True)
        self.assertEqual(final['counts'], {'ingested': 5})
        self.assertTrue(all(job['attempts'] == 1 for job in harvest.status(self.directory)['jobs']))

    def test_settings_changes_are_not_silently_resumed(self):
        self.run_expansion(execute=True)
        with self.assertRaisesRegex(ValueError, 'settings or inputs changed'):
            self.run_expansion(execute=True, resume=True, workers=1)

    def test_bad_options_fail_before_calls(self):
        for options in ({'fetch_size': 0}, {'fetch_size': 101}, {'workers': 0},
                        {'timeout': float('nan')}, {'reasoning': 'none'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_expansion(execute=True, **options)
        self.assertFalse(self.directory.exists())

    def test_registry_initializes_before_background_fetch_and_checkpoint_writes(self):
        original = expansion.prepare_batch
        observed = []

        def prepare(*args, **kwargs):
            if not kwargs.get('_initialize_only'):
                self.assertTrue((self.directory / 'run.json').exists())
                self.assertTrue(all((self.directory / 'jobs' / f'2501.{i:05d}v1/status.json').exists()
                                    for i in range(1, 6)))
                observed.append('background')
            return original(*args, **kwargs)

        with patch('bsm_atlas.expansion.prepare_batch', side_effect=prepare):
            report = self.run_expansion(execute=True)
        self.assertTrue(observed)
        self.assertEqual(report['phase'], 'extraction_complete')

    def test_preparation_access_block_stops_instead_of_trying_remaining_papers(self):
        client = Mock()
        client.get.side_effect = papers.RetrievalBlocked('arXiv returned HTTP 429')
        requests = [{k: v for k, v in row.items() if k != 'text'} for row in self.requests]
        write_json(self.path, {'papers': requests})
        with self.assertRaises(papers.RetrievalBlocked):
            harvest.prepare_batch(self.path, self.directory, source=self.source, client=client)
        self.assertEqual(client.get.call_count, 1)
        self.assertEqual(harvest.status(self.directory)['counts'], {'retry': 1, 'pending': 4})

    def test_access_or_rate_limit_does_not_try_another_endpoint(self):
        for code in (401, 403, 429):
            error = HTTPError('https://arxiv.org/example', code, 'Blocked', {}, None)
            with self.subTest(code=code), patch('bsm_atlas.papers.time.sleep'), patch(
                    'bsm_atlas.papers.urlopen', side_effect=error) as get:
                with self.assertRaises(papers.RetrievalBlocked):
                    papers.ArxivClient().get('https://arxiv.org/example')
                self.assertEqual(get.call_count, 1)

    def test_size_guard_counts_the_complete_prompt_and_utf8_bytes(self):
        with patch.object(harvest, 'MAX_PROMPT_CHARS', 100):
            harvest.check_prompt_size('x' * 100)
            for message in ('x' * 101, '\u03c8' * 51):
                with self.subTest(message=message), self.assertRaises(harvest.InputTooLarge):
                    harvest.check_prompt_size(message)

    def test_legacy_oversized_cached_prompt_never_launches_or_reports_a_fake_attempt(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source)
        with patch.object(harvest, 'MAX_PROMPT_CHARS', 10), patch(
                'bsm_atlas.harvest.check_worker'), patch('bsm_atlas.harvest.subprocess.Popen') as launch:
            report = harvest.run_batch(self.directory, True, executable=self.executable)
        launch.assert_not_called()
        self.assertEqual(report['counts'], {'retry': 5})
        self.assertEqual(report['unreported_attempts'], 0)
        self.assertTrue(all(job['category'] == 'input_size' and job['attempts'] == 0 for job in report['jobs']))
        self.assertIsNone(expansion.infrastructure_failure(self.directory, [job['job'] for job in report['jobs']]))

    def test_an_oversized_retrieval_window_does_not_stop_other_papers(self):
        (self.base / 'large.txt').write_text('BIG BODY ' * 10000)
        rows = [{**self.requests[0], 'text': 'large.txt'}, *self.requests[1:]]
        write_json(self.path, {'papers': rows})
        example = {'id': 'arxiv-2501-00005v1', 'arxiv': '2501.00005v1',
                   'title': 'Fixture 5', 'authors': 'Fixture author'}
        threshold = len(harvest.prompt(example, (self.base / 'paper.txt').read_text(), harvest.context()).encode()) + 1000
        with patch.object(harvest, 'MAX_PROMPT_CHARS', threshold):
            report = self.run_expansion(execute=True, fetch_size=1)
        self.assertEqual(report['phase'], 'extraction_complete')
        self.assertEqual(report['counts'], {'retry': 1, 'ingested': 4})
        self.assertEqual(report['usage']['input_tokens'], 400)
        first = harvest.status(self.directory)['jobs'][0]
        self.assertEqual(first['category'], 'input_size')
        self.assertEqual(first['attempts'], 0)

    def test_restart_plan_keeps_completed_source_artifacts_unchanged(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source)
        harvest.run_batch(self.directory, True, executable=self.executable, limit=2)
        before = {str(p): p.read_bytes() for p in self.directory.rglob('*') if p.is_file()}
        remaining, provenance = expansion.unfinished_manifest(self.path, self.directory)
        self.assertEqual([row['arxiv'] for row in remaining['papers']], [row['arxiv'] for row in self.requests[2:]])
        self.assertEqual(provenance['remaining_papers'], 3)
        self.assertEqual(len(provenance['preserved_papers']), 2)
        self.assertEqual(provenance['previous_usage']['input_tokens'], 200)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.directory.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(ValueError, 'frozen manifest'):
            write_json(self.path, {'papers': self.requests[:3]})
            expansion.unfinished_manifest(self.path, self.directory)

    def test_restart_does_not_duplicate_potentially_running_workers(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source)
        write_json(self.directory / 'jobs/2501.00001v1/status.json', {'state': 'running'})
        with self.assertRaisesRegex(ValueError, 'running workers'):
            expansion.unfinished_manifest(self.path, self.directory)

    def test_source_errors_continue_but_network_only_window_stops(self):
        for network in (False, True):
            with self.subTest(network=network):
                write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
                self.directory = self.base / ('network-run' if network else 'source-run')
                error = papers.SourceUnavailable('Fixture unavailable', network_failure=network)
                with patch('bsm_atlas.harvest.fetch_paper', side_effect=error):
                    report = self.run_expansion(execute=True, fetch_size=1)
                if network:
                    self.assertEqual(report['phase'], 'stopped')
                    self.assertEqual(report['counts'], {'retry': 1, 'pending': 4})
                else:
                    self.assertEqual(report['phase'], 'extraction_complete')
                    self.assertEqual(report['counts'], {'retry': 5})

    def test_html_bibliography_is_removed_without_removing_tables_or_captions(self):
        parser = papers.PaperHTML()
        parser.feed('<article><p>Definitions.</p><table><tr><td>(3,2;1)</td></tr></table>'
                    '<figure><figcaption>A real scalar.</figcaption><img src="x.png"></figure>'
                    '<section class="ltx_bibliography"><h2>References</h2><ul><li>LONG BIB</li></ul></section>'
                    '<section>Appendix: more field definitions.</section></article>')
        body = ''.join(parser.parts)
        self.assertIn('(3,2;1)', body)
        self.assertIn('A real scalar', body)
        self.assertIn('Appendix', body)
        self.assertNotIn('LONG BIB', body)

    def test_raw_source_cache_keeps_provenance_separate_from_the_math_database(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source, limit=1)
        job = self.directory / 'jobs/2501.00001v1'
        record = json.loads((job / 'source.json').read_text())
        self.assertEqual(record['raw_sha256'], harvest.digest((job / 'source.raw.txt').read_bytes()))
        self.assertEqual(record['cleaned_sha256'], harvest.digest((job / 'paper.txt').read_bytes()))
        self.assertEqual(json.loads(self.source.read_text())['entries'], [])

    def test_raw_source_tampering_is_detected_before_review(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source, limit=1)
        job = self.directory / 'jobs/2501.00001v1'
        raw = job / 'source.raw.txt'
        raw.write_text(raw.read_text() + 'Altered field definition')
        with self.assertRaisesRegex(ValueError, 'provenance changed'):
            harvest.checked_job(job)

    def test_progress_callback_sees_completed_token_usage(self):
        harvest.prepare_batch(self.path, self.directory, source=self.source, limit=1)
        observed = []
        harvest.run_batch(self.directory, True, executable=self.executable,
                          progress=lambda: observed.append(harvest.status(self.directory)))
        self.assertTrue(observed)
        self.assertEqual(observed[-1]['usage']['input_tokens'], 100)
        self.assertEqual(observed[-1]['counts'], {'ingested': 1, 'pending': 4})


if __name__ == '__main__':
    unittest.main()
