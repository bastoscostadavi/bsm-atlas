"""Offline regression tests for recovery bookkeeping; no model calls."""
import json
from pathlib import Path
import tempfile
import unittest

from bsm_atlas.recovery_progress import RecoveryProgress


class RecoveryProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reads = []

    def write(self, name, state, usage=None):
        job = self.root / 'jobs' / name
        job.mkdir(parents=True, exist_ok=True)
        (job / 'state.json').write_text(json.dumps({'state': state}))
        if usage is not None:
            (job / 'metrics.json').write_text(json.dumps({'usage': usage}))
        return job

    def read(self, path):
        self.reads.append(path)
        return json.loads(path.read_text())

    def test_checkpoint_survives_unreadable_historical_files_after_startup(self):
        old = self.write('old', 'ingested', {'input_tokens': 100})
        progress = RecoveryProgress(self.root, self.read)
        # Simulate a cloud provider making an old receipt inaccessible after
        # startup. Producing a checkpoint must not touch that file again.
        (old / 'state.json').write_text('unreadable historical file')
        (old / 'metrics.json').write_text('unreadable historical file')
        self.reads.clear()
        self.assertEqual(progress.snapshot(),
                         ({'ingested': 1}, {'input_tokens': 100}))
        self.assertEqual(self.reads, [])

    def test_intake_refresh_uses_persisted_outcome_without_double_counting(self):
        old = self.write('old', 'ingested', {'input_tokens': 100})
        job = self.write('active', 'running')
        progress = RecoveryProgress(self.root, self.read)
        self.write('active', 'invalid', {'input_tokens': 20, 'output_tokens': 3})
        self.reads.clear()
        progress.refresh(job)
        progress.refresh(job)
        self.assertEqual(progress.snapshot(),
                         ({'ingested': 1, 'invalid': 1},
                          {'input_tokens': 120, 'output_tokens': 3}))
        self.assertNotIn(old / 'state.json', self.reads)
        self.assertNotIn(old / 'metrics.json', self.reads)

    def test_completed_metrics_and_new_job_states_are_visible(self):
        job = self.write('active', 'running')
        progress = RecoveryProgress(self.root, self.read)
        self.write('active', 'running', {'input_tokens': 11})
        progress.refresh(job)
        deferred = self.write('deferred', 'source_deferred')
        progress.refresh(deferred)
        self.assertEqual(progress.snapshot(),
                         ({'running': 1, 'source_deferred': 1},
                          {'input_tokens': 11}))
        self.write('active', 'retry', {'input_tokens': 11})
        progress.refresh(job)
        restored = RecoveryProgress(self.root, self.read)
        self.assertEqual(progress.snapshot(), restored.snapshot())
