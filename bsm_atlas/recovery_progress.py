"""Incremental operational counters for one exclusively owned recovery run.

Durable job files remain authoritative. Load their counters once on resume,
then refresh only jobs that the coordinator has changed or is still running.
This avoids repeatedly reading cold historical files during each heartbeat.
"""
from collections import Counter
from pathlib import Path


class RecoveryProgress:
    def __init__(self, directory, reader):
        self.reader = reader
        self.states = {}
        self.metrics = {}
        self.counts = Counter()
        self.usage = Counter()
        jobs = Path(directory) / 'jobs'
        existing = {p.parent for pattern in ('*/state.json', '*/metrics.json')
                    for p in jobs.glob(pattern)}
        for job in existing:
            self.refresh(job)

    def refresh(self, job):
        job = Path(job)
        state_path, metrics_path = job / 'state.json', job / 'metrics.json'
        if state_path.exists():
            current = self.reader(state_path)['state']
            previous = self.states.get(job.name)
            if previous != current:
                if previous is not None:
                    self.counts[previous] -= 1
                self.counts[current] += 1
                self.states[job.name] = current
        if metrics_path.exists():
            current = self.reader(metrics_path).get('usage') or {}
            previous = self.metrics.get(job.name, {})
            if current != previous:
                self.usage.subtract(previous)
                self.usage.update(current)
            self.metrics[job.name] = current

    def snapshot(self):
        """Return counters without reading any historical file."""
        return ({key: value for key, value in self.counts.items() if value},
                dict(self.usage))
