"""Durable opt-in launcher for a reserved batch; never purchases or retries."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from .catalogue import ROOT, SOURCE, exclusive_lock
from .citations import private_json
from .allocations import register_manifest
from .harvest import check_worker
from .expansion import expand_batch


def launch_expansion(manifest, directory, *, model, provider='claude', executable='claude',
                     reasoning='medium', workers=1, fetch_size=1, timeout=900, resume=False,
                     execute=False):
    manifest, directory = Path(manifest).resolve(), Path(directory).resolve()
    plan = expand_batch(manifest, directory, model=model, provider=provider,
                        workers=workers, fetch_size=fetch_size, timeout=timeout)
    if not execute:
        return plan
    check_worker(executable) if provider == 'codex' else check_worker(executable, provider)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(directory.parent / ('.' + directory.name + '-launch.lock')):
        record_path = directory.parent / (directory.name + '-process.json')
        if directory.exists():
            with exclusive_lock(directory / 'expansion.lock'):
                pass
            if not resume:
                raise ValueError('Run already exists; use --resume rather than launching twice')
        if record_path.exists():
            previous = json.loads(record_path.read_text())
            try:
                os.kill(previous['pid'], 0)
            except ProcessLookupError:
                pass
            else:
                raise ValueError('The saved batch coordinator is still alive; no duplicate launch')
        register_manifest(manifest, provider, SOURCE)
        command = [sys.executable, '-B', '-m', 'bsm_atlas', 'harvest', 'expand', str(manifest),
                   '--run-dir', str(directory), '--execute', '--provider', provider, '--model', model,
                   '--reasoning', reasoning, '--workers', str(workers), '--fetch-size', str(fetch_size),
                   '--timeout', str(timeout), '--claude' if provider == 'claude' else '--codex', str(executable)]
        if resume:
            command.append('--resume')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        error_path = directory.parent / (directory.name + '-coordinator-' + stamp + '.txt')
        descriptor = os.open(error_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'wb') as errors:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
        guard = None
        if sys.platform == 'darwin':
            guard = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(process.pid)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True).pid
        value = {'launched_utc': datetime.now(timezone.utc).isoformat(), 'pid': process.pid,
                 'idle_sleep_guard_pid': guard, 'command': command, 'provider': provider,
                 'model': model, 'reasoning': reasoning, 'status': str(directory/'expansion-status.json'),
                 'error_log': str(error_path)}
        private_json(record_path, value)
        return value
