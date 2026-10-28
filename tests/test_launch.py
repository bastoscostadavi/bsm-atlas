"""A handoff can preview launch without calling either model provider."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bsm_atlas.catalogue import write_json
from bsm_atlas.launch import launch_expansion


class LaunchTests(unittest.TestCase):
    def test_preview_is_read_only_and_requires_explicit_claude_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'papers.json';run=root/'run'
            write_json(manifest,{'papers':[{'arxiv':'2501.00001v1'}]})
            with patch('bsm_atlas.launch.subprocess.Popen',side_effect=AssertionError('Unexpected process')):
                report=launch_expansion(manifest,run,model='claude-fixture')
                self.assertTrue(report['dry_run'])
                self.assertFalse(run.exists())
                with self.assertRaisesRegex(ValueError,'explicit claude'):
                    launch_expansion(manifest,run,model='gpt-6.1-sol')

    def test_cli_dry_run_does_not_require_claude_authentication(self):
        from bsm_atlas.__main__ import main
        from contextlib import redirect_stdout
        import io
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'papers.json'
            write_json(manifest,{'papers':[{'arxiv':'2501.00001v1'}]})
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['harvest','launch',str(manifest),'--run-dir',str(root/'run'),
                    '--model','claude-fixture','--claude','/not-installed']),0)
