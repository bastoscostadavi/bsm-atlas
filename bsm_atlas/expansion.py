"""Checkpointed extraction and automatic deterministic ingestion of a frozen manifest."""
from datetime import datetime, timezone
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
from math import isfinite
import os
from pathlib import Path
import time

from .catalogue import ROOT, SOURCE, exclusive_lock, write_json
from .harvest import (DEFAULT_MODEL, RESULT_SCHEMA, check_worker, context, digest, manifest,
                      artifact_digest, checked_job, current_context, ingest_batch, prepare_batch,
                      read_json, run_job, run_info, status)
from .papers import ArxivClient, job_id
from .extraction_tracking import already_recorded, recorded_papers, record_extractions
from .retention import compact_record, compact_if_enabled, VERSION as RETENTION_VERSION


def now():
    return datetime.now(timezone.utc).isoformat()


def unfinished_manifest(path, previous_directory):
    """Plan an explicit restart without modifying or rerunning completed papers.

    Returns a harvest-compatible manifest and private provenance. It performs no
    model calls or writes. An empty papers list means there is nothing to run.
    Source hashes remain attached to the original run rather than being edited.
    """
    path = Path(path).resolve()
    requests = manifest(path)
    previous_directory, info = run_info(previous_directory)
    if info['manifest_sha256'] != digest(str(path).encode() + path.read_bytes()):
        raise ValueError('Restart must use the original frozen manifest')
    report = status(previous_directory)
    if any(job['state'] == 'running' for job in report['jobs']):
        raise ValueError('Inspect running workers before planning a restart')
    remaining, preserved = [], []
    completed = {'extracted', 'review', 'skipped', 'ingested', 'already_recorded'}
    states = {job['job']: job for job in report['jobs']}
    for item in requests['papers']:
        name = job_id(item['arxiv'])
        compact = compact_record(previous_directory / 'jobs' / name)
        if compact:
            preserved.append({'job': name, 'state': compact['state'], 'compacted': True})
            continue
        if states[name]['state'] in completed:
            job = previous_directory / 'jobs' / name
            compact = compact_record(job)
            if compact:
                preserved.append({'job': name, 'state': compact['state'], 'compacted': True})
                continue
            if states[name]['state'] == 'already_recorded':
                preserved.append({'job': name, 'state': 'already_recorded',
                                  'paper_id': states[name]['paper_id']})
                continue
            checked_job(job)
            preserved.append({'job': name, 'state': states[name]['state'],
                              'artifact_sha256': artifact_digest(job)})
        else:
            item = dict(item)
            if 'text' in item:
                item['text'] = str((path.parent / item['text']).resolve())
            remaining.append(item)
    return {'papers': remaining}, {
        'previous_run': str(previous_directory), 'original_manifest': str(path),
        'manifest_sha256': info['manifest_sha256'], 'created_utc': now(),
        'original_papers': len(requests['papers']), 'preserved_papers': preserved,
        'remaining_papers': len(remaining), 'previous_counts': report['counts'],
        'previous_usage': report['usage'], 'previous_unreported_attempts': report['unreported_attempts'],
        'policy': 'Keep completed responses unchanged; explicitly retry unfinished/invalid papers using new source preparation. '
                  'Usage in the new run is additional to the previous run; valid extractions ingest automatically.'}


def infrastructure_failure(directory, jobs):
    """Scientific retry responses may continue; failed worker executions may not."""
    for name in jobs:
        job = directory / 'jobs' / name
        state = read_json(job / 'status.json')
        if state['state'] != 'retry' or state.get('category') == 'input_size':
            continue
        metrics = sorted(job.glob('attempt-*/metrics.json'))
        if not metrics:
            return name + ': Worker failed without a completed metrics record'
        latest = metrics[-1]
        if (read_json(latest)['usage'] is None or
                not (job / 'result.json').exists() or
                state.get('reason', '').startswith('Worker exited with status ')):
            return name + ': ' + state.get('reason', 'Worker execution failed')
    return None


def expand_batch(path, directory, execute=False, resume=False, model=DEFAULT_MODEL,
                 workers=2, executable='codex', reasoning='medium', timeout=900,
                 fetch_size=5, source=SOURCE, reconfigure=False, provider='codex'):
    """One serial fetcher feeds a bounded rolling inference pool.

    Resume never reruns completed, invalid or failed jobs automatically. A STOP
    file drains active calls. Only explicit --reconfigure can change worker and
    fetch-buffer controls on an existing run; scientific inputs stay immutable.
    """
    path, directory = Path(path).resolve(), Path(directory).resolve()
    requests = manifest(path)
    if provider not in {'codex', 'claude'}:
        raise ValueError('Choose codex or claude as the worker provider')
    if provider == 'claude' and (not model.startswith('claude-') or reasoning not in {'low','medium','high','xhigh','max'}):
        raise ValueError('Claude requires an explicit claude-* model identifier and a supported effort setting')
    if reconfigure and not resume:
        raise ValueError('Operational reconfiguration requires --resume')
    if directory.is_relative_to(ROOT / 'website'):
        raise ValueError('Expansion files must stay outside the published website')
    if type(fetch_size) is not int or not 1 <= fetch_size <= 100:
        raise ValueError('Use a fetch window of 1–100 papers')
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('Use 1–16 workers')
    if not isfinite(timeout) or timeout <= 0:
        raise ValueError('Use a positive worker timeout')
    if model == 'gpt-6.1-sol' and reasoning not in {'low', 'medium', 'high', 'xhigh', 'max'}:
        raise ValueError('GPT-6.1 Sol requires low through max reasoning')
    if not execute:
        return {'dry_run': True, 'papers': len(requests['papers']), 'model': model,
                'workers': workers, 'fetch_size': fetch_size,
                'message': 'Add --execute to retrieve sources and launch extraction. No calls or writes made.'}
    # Fail before retrieval if the worker cannot support isolation/structured output.
    check_worker(executable) if provider == 'codex' else check_worker(executable, provider)
    from .allocations import register_manifest
    register_manifest(path, provider, source)
    config = {'manifest_sha256': digest(str(path).encode() + path.read_bytes()),
              'context_sha256': digest(context().encode()), 'model': model,
              'workers': workers, 'reasoning': reasoning, 'timeout': timeout,
              'fetch_size': fetch_size, 'executable': str(executable),
              'source': str(Path(source).resolve())}
    if provider != 'codex':
        config['provider'] = provider
    if directory.exists() and not resume:
        raise ValueError('Expansion directory exists; explicitly use --resume')
    directory.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(directory / 'expansion.lock'), exclusive_lock(directory / 'run.lock'):
        config_path = directory / 'expansion.json'
        if config_path.exists():
            record = read_json(config_path)
            if record['config'] != config:
                operational = {'workers', 'fetch_size'}
                old_fixed = {key: value for key, value in record['config'].items() if key not in operational}
                new_fixed = {key: value for key, value in config.items() if key not in operational}
                if not (resume and reconfigure and old_fixed == new_fixed):
                    raise ValueError('Expansion settings or inputs changed; use a new directory or explicitly reconfigure only worker/fetch controls')
                record.setdefault('configuration_history', []).append({
                    'changed_utc': now(), 'previous': record['config'], 'updated': config,
                    'reason': 'Explicit operational reconfiguration; frozen inputs and results retained'})
                record['config'] = config
                write_json(config_path, record)
        else:
            if (directory / 'run.json').exists():
                raise ValueError('Existing run is not an expansion; use a new directory')
            record = {'config': config, 'created_utc': now(),
                      'catalogue_sha256_at_start': digest(Path(source).read_bytes()),
                      'model_writes': 0}
            write_json(config_path, record)
        started = time.monotonic()
        model_writes = 0

        def checkpoint(phase, reason=None, scheduled=0):
            report = status(directory) if (directory / 'run.json').exists() else None
            value = {'phase': phase, 'updated_utc': now(), 'pid': os.getpid(),
                     'invocation_elapsed_seconds': round(time.monotonic() - started, 3),
                     'papers': len(requests['papers']), 'model': model,
                     'workers': workers, 'scheduler': 'rolling', 'scheduled_workers': scheduled,
                     'model_writes': model_writes, 'paper_progress_recorded': True, 'reason': reason,
                     'counts': report['counts'] if report else {},
                     'usage': report['usage'] if report else None,
                     'unreported_attempts': report['unreported_attempts'] if report else 0,
                     'running_jobs': [job['job'] for job in report['jobs'] if job['state'] == 'running'] if report else []}
            write_json(directory / 'expansion-status.json', value)
            print(json.dumps(value), flush=True)
            return value

        client = ArxivClient()
        try:
            # Initialize synchronously: checkpoint atomic-write temporaries must
            # not race the empty-directory safety check in a background fetch.
            if not (directory / 'run.json').exists():
                prepare_batch(path, directory, source=source, client=client,
                              _run_locked=True, _initialize_only=True)
            write_json(directory / 'retention.json', {'delete_payloads': True, 'schema_version': RETENTION_VERSION})
            checkpoint('starting')
            if (directory / 'run.json').exists():
                _, info = run_info(directory)
                current_context(info)
                if read_json(directory / 'result.schema.json') != RESULT_SCHEMA:
                    raise ValueError('Worker schema changed; prepare a new run')
                if status(directory)['counts'].get('running'):
                    return checkpoint('stopped', 'An interrupted worker needs explicit inspection; not automatically rerun')
                cached = [name for name in info['jobs']
                          if read_json(directory / 'jobs' / name / 'status.json')['state'] in {'extracted', 'review', 'skipped'}
                          and not compact_record(directory / 'jobs' / name)
                          and not (directory / 'jobs' / name / 'ingestion.json').exists()]
                if cached:
                    imported = ingest_batch(directory, source, True, jobs=cached, _run_locked=True, _source_wait=True)
                    model_writes += len(imported['entry_ids'])
            names = [job_id(item['arxiv']) for item in requests['papers']]
            active, fetching, fetch_names = {}, None, []
            stop_reason, last_report = None, 0
            with ThreadPoolExecutor(max_workers=workers) as pool, ThreadPoolExecutor(max_workers=1) as fetcher:
                while True:
                    changed = False
                    if (directory / 'STOP').exists() and stop_reason is None:
                        stop_reason = 'STOP file present; active workers drained without further submissions'
                        changed = True
                    completed = []
                    for future, name in list(active.items()):
                        if not future.done():
                            continue
                        try:
                            future.result()
                            completed.append(name)
                        except Exception as error:
                            if stop_reason is None:
                                stop_reason = type(error).__name__ + ': ' + str(error)
                        del active[future]
                        changed = True
                    if completed:
                        try:
                            states = {name: read_json(directory / 'jobs' / name / 'status.json')['state']
                                      for name in completed}
                            failed = [name for name in completed if states[name] in {'retry', 'invalid'}]
                            accepted = [name for name in completed if states[name] in {'extracted', 'review', 'skipped'}]
                            # Intake itself records successful paper status and
                            # provenance. Do not rewrite the whole source twice.
                            if failed:
                                record_extractions(directory, source, True, jobs=failed,
                                                   manifest_path=path, _run_locked=True, _source_wait=True)
                            if accepted:
                                imported = ingest_batch(directory, source, True, jobs=accepted,
                                                        _run_locked=True, _source_wait=True)
                                model_writes += len(imported['entry_ids'])
                            failure = infrastructure_failure(directory, completed)
                            compact_if_enabled(directory, completed)
                            if failure and stop_reason is None:
                                stop_reason = 'Worker infrastructure/auth/quota failure; inspect before resuming. ' + failure
                        except Exception as error:
                            if stop_reason is None:
                                stop_reason = type(error).__name__ + ': ' + str(error)
                    if fetching is not None and fetching.done():
                        try:
                            fetched = fetching.result()
                            window = [row for row in fetched['jobs'] if row['job'] in fetch_names]
                            advanced = [row for row in window if row['state'] != 'pending']
                            failed = [row['job'] for row in advanced if row['state'] in {'retry', 'invalid'}]
                            if failed:
                                record_extractions(directory, source, True, jobs=failed,
                                                   manifest_path=path, _run_locked=True, _source_wait=True)
                            compact_if_enabled(directory, [row['job'] for row in advanced
                                                          if row['state'] in {'retry', 'invalid', 'already_recorded'}])
                            if not advanced:
                                stop_reason = stop_reason or 'Retrieval made no progress; inspect before resuming'
                            elif all(row.get('category') == 'network' for row in advanced):
                                stop_reason = stop_reason or 'Network failures prevented this retrieval window; inspect before resuming'
                        except Exception as error:
                            stop_reason = stop_reason or (type(error).__name__ + ': ' + str(error))
                        fetching = None
                        changed = True
                    if stop_reason is not None:
                        if not active and fetching is None:
                            return checkpoint('stopped', stop_reason)
                        phase = 'stopping'
                    else:
                        states = {}
                        for name in names:
                            file = directory / 'jobs' / name / 'status.json'
                            states[name] = read_json(file) if file.exists() else {'state': 'pending'}
                        reserved = set(active.values())
                        ready = [name for name in names if states[name]['state'] == 'ready' and name not in reserved]
                        pending = [name for name in names if states[name]['state'] == 'pending']
                        if ready and len(active) < workers:
                            _, info = run_info(directory)
                            current_context(info)
                            known = recorded_papers(source)
                            recorded_jobs = {job_id(identifier): paper for identifier, paper in known.items()}
                            for name in ready[:workers-len(active)]:
                                job = directory / 'jobs' / name
                                done = recorded_jobs.get(name)
                                if done and already_recorded(job, done['arxiv'], known):
                                    changed = True
                                    continue
                                checked_job(job)
                                active[pool.submit(run_job, job, executable, directory / 'result.schema.json',
                                                   model, reasoning, timeout,
                                                   **({} if provider == 'codex' else {'provider': provider}))] = name
                                changed = True
                        if pending and fetching is None and len(ready) < 2 * workers:
                            fetch_names = set(pending)
                            fetching = fetcher.submit(prepare_batch, path, directory,
                                resume=(directory / 'run.json').exists(), source=source, client=client,
                                limit=fetch_size, pending_only=True, _run_locked=True)
                            changed = True
                        if not active and fetching is None and not ready and not pending:
                            return checkpoint('extraction_complete', 'All selected papers handled; valid extractions ingested automatically')
                        phase = 'extracting' if active else 'retrieving'
                    if changed or time.monotonic() - last_report >= 30:
                        checkpoint(phase, stop_reason, scheduled=len(active))
                        last_report = time.monotonic()
                    futures = set(active)
                    if fetching is not None:
                        futures.add(fetching)
                    if futures:
                        wait(futures, timeout=1, return_when=FIRST_COMPLETED)
        except BaseException as error:
            checkpoint('stopped', type(error).__name__ + ': ' + str(error))
            raise
