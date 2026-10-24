"""Offline paper-to-catalogue tests; fake workers never call a model service."""
from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from bsm_atlas import harvest, papers
from bsm_atlas.catalogue import load, source_lock, write_json

ROOT = Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / 'atlas/examples/two-higgs-doublets.json').read_text())
BODY = 'Full paper fixture: gauge algebra, complete fermion and scalar tables. ' * 5


def result(spec=None, identifier='fixture-two-higgs', outcome='entries'):
    return {'outcome': outcome, 'reason': 'Source field table establishes this inventory.',
            'entries': [{'id': identifier, 'name': 'Fixture two-Higgs model',
                         'specification_json': json.dumps(SPEC if spec is None else spec),
                         'locators': ['Table 1; Sec. 2']}]
            if outcome == 'entries' else []}


def feed(identifier='2501.00001v1'):
    return ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            '<id>http://arxiv.org/abs/' + identifier + '</id><title>Fixture title</title>'
            '<author><name>Test Author</name></author><summary>Only an abstract</summary>'
            '</entry></feed>').encode()


class HarvestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'catalogue.json'
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
        self.manifest = self.base / 'papers.json'
        self.directory = self.base / 'run'
        (self.base / 'paper.txt').write_text(BODY)
        self.requests = [{'arxiv': '2501.00001v1', 'title': 'Fixture paper one',
                          'authors': 'Test Author', 'text': 'paper.txt'}]

    def prepare(self, requests=None):
        write_json(self.manifest, {'papers': self.requests if requests is None else requests})
        client = Mock()
        client.get.side_effect = AssertionError('Offline test attempted network access')
        report = harvest.prepare_batch(self.manifest, self.directory, source=self.source, client=client)
        client.get.assert_not_called()
        return report

    def job(self, identifier='2501.00001v1'):
        return self.directory / 'jobs' / papers.job_id(identifier)

    def set_result(self, value=None, identifier='2501.00001v1'):
        value = result() if value is None else value
        job = self.job(identifier)
        write_json(job / 'result.json', value)
        write_json(job / 'status.json', {'state': {'entries': 'review', 'skip': 'skipped', 'retry': 'retry'}[value['outcome']]})

    def fake_worker(self, value=None, delay=0, exit_code=0, modern=True):
        path = self.base / 'fake-codex'
        help_text = '--output-schema --output-last-message --json --ignore-user-config --ephemeral' if modern else '--json'
        payload = json.dumps(result() if value is None else value)
        path.write_text(
            '#!' + sys.executable + '\n'
            'import json, pathlib, sys, time\n'
            'if "--help" in sys.argv:\n'
            '    print(' + repr(help_text) + '); sys.exit(0)\n'
            'assert sys.argv[sys.argv.index("--sandbox")+1] == "read-only"\n'
            'assert "--ignore-user-config" in sys.argv\n'
            'message=sys.stdin.read()\n'
            'assert "BEGIN PAPER CONTENT" in message\n'
            'time.sleep(' + repr(delay) + ')\n'
            'if ' + repr(exit_code) + ': sys.exit(' + repr(exit_code) + ')\n'
            'pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(' + repr(payload) + ')\n'
            'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20,"cached_input_tokens":30}}))\n')
        path.chmod(0o700)
        return path

    def test_prepare_pins_one_paper_and_does_not_change_catalogue(self):
        before = self.source.read_bytes()
        self.assertEqual(self.prepare()['counts'], {'ready': 1})
        job = self.job()
        cached = harvest.checked_job(job)
        self.assertEqual(cached['paper']['arxiv'], self.requests[0]['arxiv'])
        message = (job / 'prompt.txt').read_text()
        self.assertIn(BODY, message)
        self.assertIn('untrusted source data', message)
        self.assertIn('field-content-3', message)
        self.assertEqual(self.source.read_bytes(), before)

    def test_unversioned_or_duplicate_manifest_is_rejected_before_preparation(self):
        for requests in ([{**self.requests[0], 'arxiv': '2501.00001'}], self.requests * 2):
            write_json(self.manifest, {'papers': requests})
            with self.subTest(requests=requests), self.assertRaises(ValueError):
                harvest.prepare_batch(self.manifest, self.directory, source=self.source)
        self.assertFalse(self.directory.exists())

    def test_prompt_limits_scope_without_excluding_unified_models_or_complete_efts(self):
        self.prepare()
        message = (self.job() / 'prompt.txt').read_text()
        for rule in ('Include only complete Standard Model extensions',
                     'unified models with the SM embedded in a larger algebra',
                     'not appear as separate direct-sum factors',
                     'an SM mention alone is not an inherited baseline',
                     'Exclude the unextended SM, standalone toy theories',
                     'calculation-only sectors that omit part of the SM',
                     'Never append missing SM fields',
                     'SM-extension EFT remains eligible in its stated regime',
                     'even if a different UV or cosmological setup is incomplete',
                     'Always supply a nonempty reason'):
            with self.subTest(rule=rule):
                self.assertIn(rule, message)

    def test_empty_worker_reason_is_invalid_for_every_outcome(self):
        self.prepare()
        paper = harvest.checked_job(self.job())['paper']
        for outcome in ('entries', 'skip', 'retry'):
            value = result(outcome=outcome)
            value['reason'] = ''
            with self.subTest(outcome=outcome), self.assertRaisesRegex(ValueError, 'nonempty string'):
                harvest.extracted_entries(paper, value)

    def test_source_inputs_must_stay_outside_published_directory(self):
        write_json(self.manifest, {'papers': self.requests})
        with self.assertRaisesRegex(ValueError, 'published website'):
            harvest.prepare_batch(self.manifest, ROOT / 'website/private-run', source=self.source)

    def test_resume_reuses_unchanged_inputs_and_rejects_changed_manifest(self):
        self.prepare()
        client = Mock()
        report = harvest.prepare_batch(self.manifest, self.directory, True, self.source, client)
        self.assertEqual(report['counts'], {'ready': 1})
        client.get.assert_not_called()
        write_json(self.manifest, {'papers': [{**self.requests[0], 'title': 'Changed context'}]})
        with self.assertRaises(ValueError):
            harvest.prepare_batch(self.manifest, self.directory, True, self.source, client)

    def test_retrieval_failure_is_retry_not_skip_and_can_resume(self):
        request = {'arxiv': '2501.00001v1'}
        write_json(self.manifest, {'papers': [request]})
        client = Mock()
        client.get.side_effect = OSError('Network unavailable')
        report = harvest.prepare_batch(self.manifest, self.directory, source=self.source, client=client)
        self.assertEqual(report['counts'], {'retry': 1})
        self.assertFalse((self.job() / 'prompt.txt').exists())
        with patch('bsm_atlas.harvest.fetch_paper', return_value=(
                {'id': 'p1', 'arxiv': request['arxiv'], 'title': 'Recovered', 'authors': 'Test Author'}, BODY, 'fixture')):
            self.assertEqual(harvest.prepare_batch(self.manifest, self.directory, True, self.source, client)['counts'], {'ready': 1})

    def test_legacy_arxiv_identifiers_are_safe_job_paths(self):
        self.prepare([{**self.requests[0], 'arxiv': 'hep-ph/0503065v1'}])
        self.assertEqual(harvest.status(self.directory)['jobs'][0]['job'], 'hep-ph-0503065v1')

    def test_run_dry_run_never_resolves_or_launches_a_worker(self):
        self.prepare()
        with patch('bsm_atlas.harvest.subprocess.Popen') as launch:
            report = harvest.run_batch(self.directory, executable='/does/not/exist')
        launch.assert_not_called()
        self.assertTrue(report['dry_run'])
        self.assertEqual(report['model'], 'gpt-6.1-sol')
        self.assertFalse(list(self.job().glob('attempt-*')))

    def test_cli_and_python_defaults_select_sol61(self):
        self.prepare()
        command = [sys.executable, '-B', '-m', 'bsm_atlas', 'harvest', 'run', str(self.directory)]
        response = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(response.stdout)['model'], harvest.DEFAULT_MODEL)
        self.assertEqual(harvest.DEFAULT_MODEL, 'gpt-6.1-sol')

    def test_sol61_unsupported_reasoning_fails_before_launch(self):
        self.prepare()
        for reasoning in ('none', 'minimal', 'unknown'):
            with self.subTest(reasoning=reasoning), patch('bsm_atlas.harvest.check_worker') as check:
                with self.assertRaisesRegex(ValueError, 'no workers launched'):
                    harvest.run_batch(self.directory, True, reasoning=reasoning)
                check.assert_not_called()
        self.assertFalse(list(self.job().glob('attempt-*')))

    def test_old_cli_fails_preflight_before_any_model_job(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'No workers launched'):
            harvest.run_batch(self.directory, True, executable=self.fake_worker(modern=False))
        self.assertFalse(list(self.job().glob('attempt-*')))

    def test_parallel_workers_have_separate_paper_context_and_report_usage(self):
        (self.base / 'second.txt').write_text('SECOND ARTICLE CONTENT ' * 15)
        self.prepare([self.requests[0], {**self.requests[0], 'arxiv': '2501.00002v1', 'text': 'second.txt'}])
        executable = self.fake_worker()
        report = harvest.run_batch(self.directory, True, workers=2, executable=executable)
        self.assertEqual(report['counts'], {'ingested': 2})
        self.assertEqual(report['usage']['input_tokens'], 200)
        self.assertEqual(report['usage']['output_tokens'], 40)
        self.assertNotIn('SECOND ARTICLE CONTENT', (self.job() / 'prompt.txt').read_text())
        self.assertNotIn(BODY, (self.job('2501.00002v1') / 'prompt.txt').read_text())
        self.assertEqual(len(load(self.source)['entries']), 1)
        self.assertEqual(len(load(self.source)['entries'][0]['references']), 2)
        with patch('bsm_atlas.harvest.check_worker') as preflight:
            harvest.run_batch(self.directory, True, executable=executable)
        preflight.assert_not_called()  # Completed jobs are not silently billed again.

    def test_worker_timeout_and_nonzero_exit_are_retry_not_skip(self):
        self.prepare()
        report = harvest.run_batch(self.directory, True, executable=self.fake_worker(delay=1), timeout=0.05)
        self.assertEqual(report['counts'], {'retry': 1})
        self.assertIsNone(report['usage'])
        self.assertEqual(report['unreported_attempts'], 1)
        report = harvest.run_batch(self.directory, True, executable=self.fake_worker(exit_code=7), retry=True)
        self.assertEqual(report['counts'], {'retry': 1})
        self.assertEqual(report['jobs'][0]['attempts'], 2)

    def test_invalid_worker_entry_never_reaches_source(self):
        self.prepare()
        bad = deepcopy(SPEC)
        bad['matter'][0]['copies'] = 0
        report = harvest.run_batch(self.directory, True, executable=self.fake_worker(result(bad)))
        self.assertEqual(report['counts'], {'invalid': 1})
        self.assertEqual(harvest.ingest_batch(self.directory, self.source, True)['accepted_jobs'], [])
        self.assertEqual(load(self.source)['entries'], [])

    def test_source_tampering_prevents_ingestion_and_result_changes_are_visible(self):
        self.prepare()
        self.set_result()
        original = (self.job() / 'paper.txt').read_text()
        (self.job() / 'paper.txt').write_text('Changed source')
        with self.assertRaisesRegex(ValueError, 'changed'):
            harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(load(self.source)['papers'], [])
        (self.job() / 'paper.txt').write_text(original)
        harvest.ingest_batch(self.directory, self.source, True)
        altered = result()
        altered['reason'] = 'Changed after ingestion'
        write_json(self.job() / 'result.json', altered)
        self.assertEqual(harvest.status(self.directory)['counts'], {'changed_after_ingestion': 1})

    def test_new_calls_require_frozen_instructions_but_saved_entries_use_current_validation(self):
        self.prepare()
        self.set_result()
        with patch('bsm_atlas.harvest.context', return_value='Changed conventions'):
            with self.assertRaisesRegex(ValueError, 'conventions changed'):
                harvest.run_batch(self.directory)
            report = harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(report['new_entries'], 1)

    def test_valid_results_ingest_without_approval_and_dry_run_is_read_only(self):
        self.prepare()
        self.set_result()
        before = self.source.read_bytes()
        report = harvest.ingest_batch(self.directory, self.source)
        self.assertEqual(report['accepted_jobs'], ['2501.00001v1'])
        self.assertEqual(report['new_entries'], 1)
        self.assertEqual(report['new_papers'], 1)
        self.assertEqual(self.source.read_bytes(), before)
        harvest.ingest_batch(self.directory, self.source, True)
        data = load(self.source)
        self.assertEqual(len(data['entries']), 1)
        self.assertEqual(len(data['papers']), 1)
        after = self.source.read_bytes()
        harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(self.source.read_bytes(), after)

    def test_optional_inspection_is_read_only_and_has_no_approval_api(self):
        self.prepare()
        self.set_result()
        before = self.source.read_bytes()
        report = harvest.inspect_result(self.directory, '2501.00001v1')
        self.assertEqual(report['paper']['arxiv'], '2501.00001v1')
        self.assertEqual(report['entries'][0]['specification']['matter'][-1]['reality'], 'real_module')
        self.assertFalse((self.job() / 'review.json').exists())
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(hasattr(harvest, 'review'))

    def test_two_papers_normalize_to_one_entry_and_gain_references(self):
        self.prepare([self.requests[0], {**self.requests[0], 'arxiv': '2501.00002v1'}])
        self.set_result()
        other = deepcopy(SPEC)
        other['matter'].reverse()
        other['gauge_factors'].reverse()
        for row in other['matter']:
            for factor in other['gauge_factors']:
                if factor['family'] == 'U1':
                    from fractions import Fraction
                    representation = row['gauge_representations'][factor['id']]
                    representation['charge'] = str(7 * Fraction(representation['charge']))
        self.set_result(result(other, 'another-model-name'), '2501.00002v1')
        report = harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(report['new_entries'], 1)
        data = load(self.source)
        self.assertEqual(len(data['papers']), 2)
        self.assertEqual(len(data['entries'][0]['references']), 2)

    def test_existing_paper_id_is_reused_not_duplicated(self):
        self.prepare([{**self.requests[0], 'id': 'worker-paper-id'}])
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'entries': [], 'papers': [
            {'id': 'original-paper', 'arxiv': '2501.00001v1', 'title': 'Existing title', 'authors': 'Existing authors'}]})
        self.set_result()
        harvest.ingest_batch(self.directory, self.source, True)
        data = load(self.source)
        self.assertEqual(len(data['papers']), 1)
        self.assertEqual(data['entries'][0]['references'][0]['paper_id'], 'original-paper')

    def test_skip_adds_bibliography_only_and_retry_is_not_ingested(self):
        self.prepare()
        self.set_result(result(outcome='retry'))
        self.assertEqual(harvest.ingest_batch(self.directory, self.source, True)['accepted_jobs'], [])
        self.set_result(result(outcome='skip'))
        harvest.ingest_batch(self.directory, self.source, True)
        data = load(self.source)
        self.assertEqual(len(data['papers']), 1)
        self.assertEqual(data['entries'], [])

    def test_symbolic_parameter_names_are_mapped_by_code(self):
        spec = json.loads((ROOT / 'atlas/examples/parameterized-charges.json').read_text())
        self.prepare()
        self.set_result(result(spec))
        harvest.ingest_batch(self.directory, self.source, True)
        entry = load(self.source)['entries'][0]
        self.assertEqual(set(entry['specification']['parameters']), {'z1', 'z2'})
        self.assertEqual(set(entry['references'][0]['parameter_names']), set(spec['parameters']))

    def test_model_name_collisions_are_disambiguated_without_changing_identity(self):
        self.prepare([self.requests[0], {**self.requests[0], 'arxiv': '2501.00002v1'}])
        self.set_result()
        other = deepcopy(SPEC)
        other['matter'][0]['copies'] += 123
        self.set_result(result(other), '2501.00002v1')  # Same entry ID, genuinely different spectrum.
        report = harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(report['new_entries'], 2)
        entries = load(self.source)['entries']
        self.assertEqual(len({e['id'] for e in entries}), 2)
        self.assertTrue(entries[1]['id'].startswith('fixture-two-higgs-'))
        self.assertEqual(harvest.ingest_batch(self.directory, self.source, True)['new_entries'], 0)

    def test_indexed_batch_reconciliation_matches_the_strict_single_entry_writer(self):
        self.prepare()
        paper = harvest.checked_job(self.job())['paper']
        entries = harvest.extracted_entries(paper, result())
        reference = {'schema_version': 'bsm-atlas-1', 'papers': [paper], 'entries': []}
        indexed = deepcopy(reference)
        fingerprints = {}
        additions = []
        for number, copies in enumerate((0, 1, 0, 2, 1)):
            entry = deepcopy(entries[0])
            entry['id'] = f'fixture-entry-{number}'
            entry['specification']['matter'][-1]['copies'] += copies
            additions.append(entry)
        for entry in additions:
            reference, expected = harvest.ingest(reference, entry)
            indexed, actual = harvest.ingest(indexed, entry, _fingerprints=fingerprints)
            self.assertEqual(expected, actual)
        harvest.validate(indexed)
        self.assertEqual(reference, indexed)
        self.assertEqual(len(fingerprints), 3)

    def test_schema_valid_majorana_higher_spin_field_roundtrips_to_sqlite(self):
        from contextlib import closing
        import sqlite3
        from bsm_atlas.build import database, main_data
        self.prepare()
        spec = deepcopy(SPEC)
        representations = {factor['id']: ({'charge': '0'} if factor['family'] == 'U1'
                           else {'dynkin': [0] * factor['rank']}) for factor in spec['gauge_factors']}
        spec['matter'].append({'lorentz': {'dimension': 4, 'scheme': 'jL_jR',
                              'irreps': [['1', '1/2'], ['1/2', '1']]},
                              'reality': 'majorana', 'copies': 1, 'gauge_representations': representations})
        self.set_result(result(spec))
        harvest.ingest_batch(self.directory, self.source, True)
        path = self.base / 'catalogue.sqlite'
        database(path, main_data(load(self.source)))
        with closing(sqlite3.connect(path)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM matter WHERE reality='majorana'").fetchone()[0], 1)

    def test_invalid_saved_entry_rolls_back_a_batch_without_a_partial_receipt(self):
        self.prepare([self.requests[0], {**self.requests[0], 'arxiv': '2501.00002v1'}])
        self.set_result()
        bad = deepcopy(SPEC)
        bad['matter'][0]['copies'] = 0
        self.set_result(result(bad), '2501.00002v1')
        before = self.source.read_bytes()
        with self.assertRaises(ValueError):
            harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(before, self.source.read_bytes())
        self.assertFalse(list(self.directory.glob('jobs/*/ingestion.json')))

    def test_writers_share_lock_and_atomic_write_failure_keeps_source(self):
        self.prepare()
        self.set_result()
        before = self.source.read_bytes()
        with source_lock(self.source), self.assertRaisesRegex(ValueError, 'lock'):
            harvest.ingest_batch(self.directory, self.source, True)
        with patch.object(Path, 'replace', side_effect=OSError('Disk failure')):
            with self.assertRaises(OSError):
                write_json(self.source, {'changed': True})
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(list(self.base.glob('.catalogue.json-*')))

    def test_single_entry_cli_respects_the_same_lock(self):
        candidate = self.base / 'candidate.json'
        candidate.write_text('{}')
        with source_lock(self.source):
            run = subprocess.run([sys.executable, '-B', '-m', 'bsm_atlas', 'add', str(candidate),
                                  '--source', str(self.source), '--write'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('lock', run.stderr)

    def test_cli_prepare_status_and_dry_run_do_not_need_codex(self):
        write_json(self.manifest, {'papers': self.requests})
        commands = [
            ['prepare', str(self.manifest), '--run-dir', str(self.directory), '--source', str(self.source)],
            ['status', str(self.directory)],
            ['run', str(self.directory), '--codex', '/nonexistent'],
            ['ingest', str(self.directory), '--source', str(self.source)]]
        for command in commands:
            with self.subTest(command=command):
                run = subprocess.run([sys.executable, '-B', '-m', 'bsm_atlas', 'harvest', *command],
                                     cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIsInstance(json.loads(run.stdout), dict)
        self.assertEqual(load(self.source)['entries'], [])

    def test_dangerous_job_paths_and_skip_with_entries_are_rejected(self):
        self.prepare()
        info = harvest.read_json(self.directory / 'run.json')
        info['jobs'] = ['../escape']
        write_json(self.directory / 'run.json', info)
        with self.assertRaises(ValueError):
            harvest.status(self.directory)
        bad = result()
        bad['outcome'] = 'skip'
        with self.assertRaises(ValueError):
            harvest.extracted_entries({'id': 'p1', 'arxiv': '2501.00001v1', 'title': 'T', 'authors': 'A'}, bad)

    def test_rebuild_requires_real_source_and_explicit_write(self):
        self.prepare()
        for write in (False, True):
            with self.subTest(write=write), self.assertRaises(ValueError):
                harvest.ingest_batch(self.directory, self.source, write, rebuild=True)

    def test_projection_failure_prevents_source_commit(self):
        self.prepare()
        self.set_result()
        before = self.source.read_bytes()
        with patch('bsm_atlas.build.main_data', side_effect=ValueError('Unprojectable specification')):
            with self.assertRaisesRegex(ValueError, 'Unprojectable'):
                harvest.ingest_batch(self.directory, self.source, True)
        self.assertEqual(self.source.read_bytes(), before)

    def test_rebuild_failure_reports_that_source_was_saved(self):
        self.prepare()
        self.set_result()
        with patch('bsm_atlas.harvest.SOURCE', self.source), patch(
                'bsm_atlas.build.write_outputs', side_effect=OSError('Export directory unavailable')):
            with self.assertRaisesRegex(ValueError, 'Catalogue saved, but exports failed'):
                harvest.ingest_batch(self.directory, self.source, True, rebuild=True)
        self.assertEqual(len(load(self.source)['entries']), 1)

    def test_invalid_limits_cannot_launch_workers(self):
        self.prepare()
        for options in ({'workers': 0}, {'workers': 9}, {'limit': 0}, {'timeout': float('nan')}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                harvest.run_batch(self.directory, True, **options)


class PaperRetrievalTests(unittest.TestCase):
    def test_metadata_requires_exact_requested_version(self):
        self.assertEqual(papers.metadata(feed(), '2501.00001v1')['title'], 'Fixture title')
        with self.assertRaisesRegex(ValueError, 'different paper/version'):
            papers.metadata(feed('2501.00001v2'), '2501.00001v1')

    def test_tex_archive_members_are_never_extracted(self):
        content = ('\\documentclass{article}\n\\begin{document}\n' + BODY + '\\end{document}').encode()
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz') as output:
            member = tarfile.TarInfo('../../never-extract.tex')
            member.size = len(content)
            output.addfile(member, io.BytesIO(content))
        self.assertIn(BODY, papers.tex_text(archive.getvalue()))
        self.assertIn(BODY, papers.tex_text(gzip.compress(content)))
        with self.assertRaises(ValueError):
            papers.tex_text(b'<html>A login page or error, not a paper</html>')

    def test_html_keeps_math_and_table_column_separators(self):
        parser = papers.PaperHTML()
        parser.feed('<script>not paper</script><article><p>' + BODY + '</p><table><tr>'
                    '<td>fermion</td><td><math alttext="(3,2;1)"><mi>rendered</mi></math>'
                    '</td></tr></table></article><footer>not paper</footer>')
        body = ''.join(parser.parts)
        self.assertIn('\tfermion\t (3,2;1)', body)
        self.assertNotIn('rendered', body)
        self.assertNotIn('not paper', body)

    def test_full_text_failure_does_not_fall_back_to_abstract(self):
        client = Mock()
        client.get.side_effect = [feed(), OSError('source missing'), OSError('HTML missing')]
        with self.assertRaisesRegex(ValueError, 'Full text unavailable'):
            papers.fetch_paper({'arxiv': '2501.00001v1'}, Path('/tmp'), client)

    def test_large_source_is_rejected_without_truncating(self):
        with self.assertRaisesRegex(ValueError, 'bound'):
            papers.full_text('x' * (papers.MAX_TEXT + 1))

    def test_network_client_throttles_even_the_first_request(self):
        client = papers.ArxivClient()
        response = io.BytesIO(b'fixture response')
        response.geturl = lambda: 'https://arxiv.org/example'
        with patch('bsm_atlas.papers.time.sleep') as sleep, patch(
                'bsm_atlas.papers.urlopen', return_value=response):
            self.assertEqual(client.get('https://arxiv.org/example'), b'fixture response')
        self.assertGreater(sleep.call_args.args[0], 3)

    def test_full_text_redirect_cannot_silently_change_versions(self):
        response = io.BytesIO(b'wrong version')
        response.geturl = lambda: 'https://arxiv.org/html/2501.00001v2'
        with patch('bsm_atlas.papers.time.sleep'), patch('bsm_atlas.papers.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'changed the requested paper/version'):
                papers.ArxivClient().get('https://arxiv.org/html/2501.00001v1')


if __name__ == '__main__':
    unittest.main()
