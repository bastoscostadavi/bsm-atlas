"""Crash-safe removal of temporary extraction payloads, never catalogue data."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from .catalogue import exclusive_lock, load, write_json

VERSION = 'bsm-compact-job-1'
PAYLOADS = ('paper.txt', 'prompt.txt', 'source.raw.txt', 'result.json', 'events.jsonl', 'stderr.txt',
            'paper.json', 'source.json', 'progress.json')


def seal(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def compact_record(job):
    path = Path(job) / 'compacted.json'
    if not path.exists():
        return None
    wrapper = json.loads(path.read_text())
    value = wrapper['record']
    if wrapper['sha256'] != seal(value) or value['schema_version'] != VERSION:
        raise ValueError('Invalid compact receipt: ' + str(path))
    receipt = Path(job) / 'ingestion.json'
    if value['ingestion'] is not None and (not receipt.exists() or json.loads(receipt.read_text()) != value['ingestion']):
        raise ValueError('Ingestion receipt changed after compaction: ' + str(job))
    return value


def payloads(job):
    job = Path(job)
    if job.is_symlink():
        raise ValueError('Refusing a symlink job directory')
    paths = [job / name for name in PAYLOADS]
    for attempt in job.glob('attempt-*'):
        if not re.fullmatch(r'attempt-[0-9]+', attempt.name) or attempt.is_symlink():
            raise ValueError('Unexpected attempt path: ' + str(attempt))
        paths.extend(attempt / name for name in PAYLOADS)
    for path in paths:
        if path.is_symlink():
            raise ValueError('Refusing symlink payload: ' + str(path))
    return [path for path in paths if path.is_file()]


def compact_job(job, *, known=None, entry_papers=None, discard_uningested=False, write=True):
    """Caller owns run.lock. Seal completion BEFORE unlinking; safe to repeat."""
    job = Path(job)
    value = compact_record(job)
    if value is None:
        state_path = job / 'status.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {'state': 'pending'}
        if state['state'] == 'running':
            return {'kept': 'running', 'bytes_removed': 0}
        paper_path, progress_path = job / 'paper.json', job / 'progress.json'
        meta = json.loads(paper_path.read_text()) if paper_path.exists() else {}
        progress = json.loads(progress_path.read_text()) if progress_path.exists() else None
        paper = meta.get('paper', (progress or {}).get('paper'))
        if paper is None and known is not None:
            from .papers import job_id
            paper = next((p for p in known.values() if job_id(p['arxiv']) == job.name), None)
        recorded = (known or {}).get(paper['arxiv']) if paper else None
        receipt_path = job / 'ingestion.json'
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
        if receipt:
            if known is not None and not recorded:
                raise ValueError('Ingested paper is missing from the selected catalogue: ' + str(job))
            if entry_papers is not None and any(paper['arxiv'] not in entry_papers.get(target, set())
                                              for target in receipt['entry_ids']):
                raise ValueError('Ingested model/reference is missing from the catalogue: ' + str(job))
            # Do not seal a changed result as successfully ingested.
            result = job / 'result.json'
            if not result.exists() or sha256(result.read_bytes()).hexdigest() != receipt['result_sha256']:
                raise ValueError('Result changed before cleanup: ' + str(job))
            terminal = 'ingested'
        elif recorded or progress:
            terminal = state['state'] if state['state'] in {'retry', 'invalid'} else 'already_recorded'
        elif discard_uningested and state['state'] in {'extracted', 'review', 'skipped', 'retry', 'invalid'}:
            terminal = 'discarded'
        else:
            return {'kept': 'uncommitted_or_unprocessed', 'bytes_removed': 0}
        paths = payloads(job)
        diagnostic = None
        for path in paths:
            if path.name != 'events.jsonl':
                continue
            with path.open() as stream:
                for line in stream:
                    if len(line) > 8192:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get('type') in {'error', 'turn.failed'}:
                        message = event.get('message') or event.get('error', {}).get('message')
                        if isinstance(message, str):
                            diagnostic = message[:1000]
        value = {'schema_version': VERSION, 'paper': paper, 'state': terminal,
                 'category': state.get('category'),
                 'diagnostic': diagnostic,
                 'reason': state.get('reason', '')[:1000], 'ingestion': receipt,
                 'progress': progress, 'text_sha256': meta.get('text_sha256'),
                 'prompt_sha256': meta.get('prompt_sha256'),
                 'removed_sha256': {str(p.relative_to(job)): sha256(p.read_bytes()).hexdigest() for p in paths},
                 'compacted_utc': datetime.now(timezone.utc).isoformat()}
    paths = payloads(job)
    for path in paths:
        name = str(path.relative_to(job))
        actual = sha256(path.read_bytes()).hexdigest()
        previous = value['removed_sha256'].get(name)
        if previous is not None and actual != previous:
            raise ValueError('Payload changed during interrupted cleanup: ' + str(path))
        value['removed_sha256'][name] = actual
    size = sum(p.stat().st_size for p in paths)
    if write:
        # Atomic durable marker makes partial deletion recoverable after a crash.
        write_json(job / 'compacted.json', {'record': value, 'sha256': seal(value)})
        state = {'state': value['state'], 'reason': value['reason'], 'compacted': True}
        if value.get('category'):
            state['category'] = value['category']
        write_json(job / 'status.json', state)
        for path in paths:
            path.unlink()
    return {'state': value['state'], 'bytes_removed': size, 'files_removed': len(paths)}


def cleanup_run(directory, *, source=None, write=False, discard_uningested=False):
    from .harvest import run_info
    from .extraction_tracking import catalogue_source
    directory, info = run_info(directory)
    source = Path(source) if source else catalogue_source(directory, info)
    data = load(source)
    known = {p['arxiv']: p for p in data['papers']}
    by_id = {p['id']: p['arxiv'] for p in data['papers']}
    entry_papers = {e['id']: {by_id[r['paper_id']] for r in e['references']} for e in data['entries']}
    with exclusive_lock(directory / 'run.lock'):
        reports = [compact_job(directory / 'jobs' / name, known=known,
                               entry_papers=entry_papers,
                               discard_uningested=discard_uningested, write=write)
                   for name in info['jobs']]
        if write:
            write_json(directory / 'retention.json', {'delete_payloads': True, 'schema_version': VERSION})
    return {'dry_run': not write, 'jobs': len(reports),
            'bytes_removed': sum(r['bytes_removed'] for r in reports),
            'files_removed': sum(r.get('files_removed', 0) for r in reports),
            'kept_jobs': sum('kept' in r for r in reports)}


def compact_if_enabled(directory, names):
    if (Path(directory) / 'retention.json').exists():
        for name in names:
            compact_job(Path(directory) / 'jobs' / name)
