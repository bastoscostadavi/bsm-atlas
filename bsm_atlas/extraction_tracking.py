"""Paper-version completion markers in the existing catalogue, never model intake.

Only structurally valid extraction responses count as complete. A completed skip
is included. Normal expansions skip every recorded version, including failures;
retries are a separate explicit operation. No full-text cache is needed to skip.
"""
from collections import Counter
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path

from .catalogue import SOURCE, exclusive_lock, load, source_lock, validate, write_json
from .papers import job_id


def catalogue_source(directory, info):
    """Legacy runs have no source path; expansions already froze one separately."""
    if 'catalogue_source' in info:
        return Path(info['catalogue_source'])
    from .harvest import read_json
    path = Path(directory) / 'expansion.json'
    return Path(read_json(path)['config']['source']) if path.exists() else SOURCE


def recorded_papers(source):
    """Existence, not extraction success, controls normal expansion admission."""
    return {p['arxiv']: p for p in load(source)['papers']}


def already_recorded(job, identifier, known, *, write=True):
    paper = known.get(identifier)
    if paper is None:
        return False
    if write:
        write_json(Path(job) / 'status.json', {
            'state': 'already_recorded', 'paper_id': paper['id'],
            'reason': 'This exact arXiv version is already in papers; normal expansions take new versions only.'})
    return True


def record_extractions(directory, source=SOURCE, write=False, *, jobs=None,
                       manifest_path=None, _run_locked=False):
    """Backfill/update paper progress only; no calls, approvals or model writes.

    An optional original manifest supplies bibliography for retrieval failures.
    All decisions are validated before the one atomic catalogue replacement.
    Older failures cannot overwrite an already complete result. Mathematical
    validation failures remain unresolved for a separate explicit follow-up.
    """
    from .harvest import (extracted_entries, checked_job, digest, manifest,
                          read_json, run_info)
    from .retention import compact_record
    directory, info = run_info(directory)
    source = Path(source).resolve()
    names = info['jobs'] if jobs is None else list(jobs)
    if len(set(names)) != len(names) or not set(names) <= set(info['jobs']):
        raise ValueError('Unknown or repeated paper job in extraction-status update')
    requests = {}
    if manifest_path is not None:
        path = Path(manifest_path).resolve()
        if digest(str(path).encode() + path.read_bytes()) != info['manifest_sha256']:
            raise ValueError('Status backfill requires the original frozen manifest')
        requests = {job_id(p['arxiv']): p for p in manifest(path)['papers']}
    report = {'dry_run': not write, 'recorded': [], 'ignored': [], 'missing_metadata': [],
              'new_papers': 0, 'updated_papers': 0, 'model_writes': 0}
    with nullcontext() if _run_locked else exclusive_lock(directory / 'run.lock'):
        with source_lock(source) if write else nullcontext():
            data = load(source)
            before = deepcopy(data)
            known = {p['arxiv']: p for p in data['papers']}
            for paper in data['papers']:
                paper.setdefault('extraction_status', 'not_started')
            for name in names:
                job = directory / 'jobs' / name
                if compact_record(job):
                    report['ignored'].append(name)
                    continue
                state_path = job / 'status.json'
                state = read_json(state_path)['state'] if state_path.exists() else 'pending'
                if state not in {'extracted', 'review', 'skipped', 'retry', 'invalid'}:
                    report['ignored'].append(name)
                    continue
                if (job / 'paper.json').exists():
                    paper = checked_job(job)['paper']
                else:
                    request = requests.get(name, {})
                    if not all(request.get(k) for k in ('arxiv', 'title', 'authors')):
                        report['missing_metadata'].append(name)
                        continue
                    paper = {k: request[k] for k in ('arxiv', 'title', 'authors')}
                    paper['id'] = request.get('id', 'arxiv-' + name.replace('.', '-'))
                outcome = 'unresolved'
                if state in {'extracted', 'review', 'skipped'}:
                    result = read_json(job / 'result.json')
                    if result['outcome'] != {'extracted': 'entries', 'review': 'entries', 'skipped': 'skip'}[state]:
                        raise ValueError('Worker state/result mismatch: ' + name)
                    extracted_entries(paper, result)
                    outcome = 'complete'
                existing = known.get(paper['arxiv'])
                if existing is None:
                    if any(p['id'] == paper['id'] for p in data['papers']):
                        raise ValueError('Paper ID collision during extraction-status update')
                    existing = {k: paper[k] for k in ('id', 'arxiv', 'title', 'authors')}
                    data['papers'].append(existing)
                    known[paper['arxiv']] = existing
                    report['new_papers'] += 1
                old = deepcopy(existing)
                if not (outcome == 'unresolved'
                        and existing.get('extraction_status') == 'complete'):
                    existing['extraction_status'] = outcome
                if existing != old:
                    report['updated_papers'] += 1
                report['recorded'].append({'job': name, 'arxiv': paper['arxiv'],
                                           'extraction_status': existing['extraction_status']})
            validate(data)
            report['counts'] = dict(Counter(p.get('extraction_status', 'not_started') for p in data['papers']))
            report['source_changed'] = data != before
            if write and data != before:
                write_json(source, data)
            if write:
                for row in report['recorded']:
                    paper = known[row['arxiv']]
                    write_json(directory / 'jobs' / row['job'] / 'progress.json',
                               {'source': str(source), 'paper': paper,
                                'extraction_status': row['extraction_status']})
    return report
