"""The unified command is read-only unless an addition explicitly uses --write."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'atlas/catalogue.json'
DATABASE = ROOT / 'website/downloads/field-catalogue.sqlite'
ENTRY = next(entry for entry in json.loads(SOURCE.read_text())['entries']
             if entry['id'] == 'two-higgs-doublets')


class CatalogueCLI(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, '-B', '-m', 'bsm_atlas', *map(str, arguments)],
                              cwd=ROOT, capture_output=True, text=True)

    def test_help_exposes_one_command_with_documented_operations(self):
        overview = self.run_cli('--help')
        self.assertEqual(overview.returncode, 0, overview.stderr)
        for command in ('validate', 'add', 'prepare', 'lookup', 'build'):
            self.assertIn(command, overview.stdout)
            result = self.run_cli(command, '--help')
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_is_read_only_and_accepts_an_explicit_source(self):
        before = SOURCE.read_bytes()
        result = self.run_cli('validate')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Valid catalogue:', result.stdout)
        self.assertEqual(SOURCE.read_bytes(), before)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.json'
            source.write_bytes(before)
            result = self.run_cli('validate', '--source', source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_bytes(), before)

    def test_prepare_normalized_entry_and_duplicate_lookup_are_read_only(self):
        before = SOURCE.read_bytes(), DATABASE.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'specification.json'
            candidate.write_text(json.dumps(ENTRY['specification']))
            unchanged = candidate.read_bytes()
            result = self.run_cli('prepare', candidate, '--require-normalized', '--database', DATABASE)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['normalized_entry'], ENTRY['specification'])
            self.assertEqual(report['duplicate_check']['status'], 'exact_field_content_match')
            self.assertEqual(candidate.read_bytes(), unchanged)
        self.assertEqual((SOURCE.read_bytes(), DATABASE.read_bytes()), before)

    def test_prepare_require_normalized_rejects_rescaled_source_charges(self):
        spec = deepcopy(ENTRY['specification'])
        for row in spec['matter']:
            for factor in spec['gauge_factors']:
                if factor['family'] == 'U1':
                    rep = row['gauge_representations'][factor['id']]
                    rep['charge'] = str(2 * int(rep['charge']))
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'specification.json'
            candidate.write_text(json.dumps(spec))
            unchanged = candidate.read_bytes()
            result = self.run_cli('prepare', candidate, '--require-normalized')
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'blocked_before_ingestion')
            self.assertEqual(candidate.read_bytes(), unchanged)
            result = self.run_cli('prepare', candidate)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['normalized_entry'], ENTRY['specification'])

    def test_lookup_matches_the_default_and_an_explicit_export(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'specification.json'
            candidate.write_text(json.dumps(ENTRY['specification']))
            export = Path(directory) / 'export.sqlite'
            export.write_bytes(DATABASE.read_bytes())
            for arguments in ((), ('--database', export)):
                with self.subTest(arguments=arguments):
                    result = self.run_cli('lookup', candidate, *arguments)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report['status'], 'exact_field_content_match')
                    self.assertIn(ENTRY['id'], [match['entry_id'] for match in report['matches']])

    def test_lookup_never_creates_a_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'specification.json'
            candidate.write_text(json.dumps(ENTRY['specification']))
            missing = Path(directory) / 'missing.sqlite'
            result = self.run_cli('lookup', candidate, '--database', missing)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'unresolved_or_invalid_input')
            self.assertFalse(missing.exists())

    def test_invalid_json_has_a_controlled_error(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'invalid.json'
            candidate.write_text('{')
            for command in ('prepare', 'lookup', 'add'):
                with self.subTest(command=command):
                    result = self.run_cli(command, candidate)
                    self.assertEqual(result.returncode, 2)
                    self.assertNotIn('Traceback', result.stdout + result.stderr)

    def test_write_flag_is_only_available_for_add(self):
        before = SOURCE.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'specification.json'
            candidate.write_text(json.dumps(ENTRY['specification']))
            for command in ('validate', 'prepare', 'lookup', 'build'):
                with self.subTest(command=command):
                    arguments = [candidate] if command in {'prepare', 'lookup'} else []
                    result = self.run_cli(command, *arguments, '--write')
                    self.assertEqual(result.returncode, 2)
        self.assertEqual(SOURCE.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
