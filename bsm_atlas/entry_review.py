"""Blinded Terra checks of Luna entries; disagreements retain Terra for later Sol review.

One paper per worker preserves source context and checks the complete inventory.
Review metadata is separate from mathematical identity. No Sol calls are made.
"""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from hashlib import sha256
from functools import lru_cache
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
from threading import Event, Lock
import time

from .catalogue import SOURCE, ROOT, identity, validate, write_json, source_lock, exclusive_lock
from .corpus import CORPUS
from .corpus_queue import AwaitingSource
from .harvest import reconcile_entry
from .joint_harvest import DEFAULT_EXECUTABLE, now, check_worker, compact
from .inventory_worker import (SCOPE, context, response_schema, run_worker,
                               validate_response, inventory_quality)
from .literature import path_for, bind_luna_receipt, VERSION as LINKS_VERSION
from .papers import job_id

VERSION = 'luna-terra-entry-review-1'
MODEL = 'gpt-6.1-terra'
LUNA = 'gpt-6-luna'
RETRY_VERSION = 'terra-entry-retry-pass-1'
CONFIDENCE_VERSION = 'terra-luna-no-entry-confidence-pass-1'


def read_source(identifier, directory=CORPUS, *, timeout=10):
    """Verify retained bytes and assemble profile-three TeX outside the scheduler."""
    code = '''import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from bsm_atlas.corpus_queue import read_source,AwaitingSource
from bsm_atlas.tex_source_v3 import _prepare
from bsm_atlas.corpus import paper_dir
from bsm_atlas.citations import base_id
try:
    identifier=sys.argv[2];directory=Path(sys.argv[3]);local=Path(sys.argv[4])
    base=base_id(identifier);original=paper_dir(directory,base,identifier[len(base):])
    if not (original/'meta.json').exists():
        raise AwaitingSource(identifier)
    if original.is_symlink() or (original/'meta.json').is_symlink():
        raise ValueError('Symlink corpus source refused')
    if sys.platform=='darwin':
        target=paper_dir(local,base,identifier[len(base):]);target.parent.mkdir(parents=True,exist_ok=True)
        try:
            cloned=subprocess.run(['/bin/cp','-cRP',str(original),str(target)],capture_output=True,timeout=3)
        except subprocess.TimeoutExpired:
            cloned=None
        if cloned is not None and not cloned.returncode:
            directory=local
    body,provenance=read_source(identifier,directory,preparer=_prepare)
    provenance['corpus_meta']=str((original/'meta.json').resolve())
    result={'body':body,'provenance':provenance}
except (AwaitingSource,ValueError,OSError) as error:
    result={'error':str(error),'kind':'awaiting' if isinstance(error,AwaitingSource) else 'unusable'}
print(json.dumps(result))
'''
    command = [sys.executable, '-I', '-B']
    if sys.pycache_prefix:
        command += ['-X', 'pycache_prefix='+sys.pycache_prefix]
    with tempfile.TemporaryDirectory(prefix='terra-source-',
            dir='/private/tmp' if sys.platform == 'darwin' else None) as temporary:
        command += ['-c', code, str(ROOT), identifier, str(Path(directory).resolve()), temporary]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.communicate()
            raise AwaitingSource('Retained source preparation timed out: '+identifier) from error
        if process.returncode:
            raise RuntimeError('Source preparation failed: '+stderr.decode(errors='replace')[-700:])
        prepared = json.loads(stdout)
    if 'error' in prepared:
        if prepared['kind'] == 'awaiting':
            raise AwaitingSource(prepared['error'])
        raise ValueError(prepared['error'])
    return prepared['body'], prepared['provenance']


def read_saved_bytes(path, *, timeout=5):
    """Bound a saved-file read without leaving a stuck reader in the coordinator."""
    path = Path(path).absolute()
    deadline = time.monotonic()+timeout
    with tempfile.TemporaryDirectory(prefix='terra-metadata-',
            dir='/private/tmp' if sys.platform == 'darwin' else None) as temporary:
        target = path
        try:
            if sys.platform == 'darwin' and stat.S_ISREG(path.stat().st_mode):
                # APFS snapshots avoid reopening the original provider-managed
                # file stream. Other filesystems fall back to the bounded reader.
                snapshot = Path(temporary)/'metadata.json'
                try:
                    cloned = subprocess.run(['/bin/cp', '-c', str(path), str(snapshot)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=max(.001, min(1, deadline-time.monotonic())))
                except subprocess.TimeoutExpired:
                    cloned = None
                if cloned is not None and not cloned.returncode:
                    target = snapshot
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired('saved metadata snapshot', timeout)
            command = [sys.executable, '-I', '-B', '-c',
                       'import pathlib,sys;sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())',
                       str(target)]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError('Saved review metadata read timed out: '+str(path)) from error
    if result.returncode:
        raise OSError('Cannot read saved review metadata '+str(path)+': '+
                      result.stderr.decode(errors='replace')[-500:])
    return result.stdout


def read_metadata(path, *, timeout=5):
    return json.loads(read_saved_bytes(path, timeout=timeout))


def read(path):
    """Read a bounded local snapshot of an authoritative JSON store."""
    return read_metadata(path, timeout=30)


def load_links(path):
    """Keep the literature store's existing schema checks with bounded reads."""
    path = Path(path)
    if not path.exists():
        return {'schema_version': LINKS_VERSION, 'papers': {}}
    data = read(path)
    if (set(data) != {'schema_version', 'papers'} or data['schema_version'] != LINKS_VERSION
            or not isinstance(data['papers'], dict)):
        raise ValueError('Invalid literature-link store')
    return data


def source_preparation_policy():
    """Pin the same static source assembler already used by Luna recovery."""
    from . import corpus_queue, tex_source, tex_source_v3
    return {'source_preparation_profile': 'tex-v3',
            'cleaner_version': tex_source_v3.CLEANER_VERSION,
            'source_reader_sha256': sha256(read_saved_bytes(corpus_queue.__file__)).hexdigest(),
            'base_source_preparation_sha256': sha256(read_saved_bytes(tex_source.__file__)).hexdigest(),
            'source_preparation_sha256': sha256(read_saved_bytes(tex_source_v3.__file__)).hexdigest()}


def registered_jobs(store):
    """The registry indexes completed attempts, including superseded retry history."""
    return {str(Path(job).absolute()) for record in store['papers'].values()
            for job in [record['job'], *record.get('previous_jobs', [])]}


class UsageLedger:
    """Count new call usage once; retain cached lifetime totals as a lower bound."""
    def __init__(self, cached=None):
        cached = cached or {}
        self.base = Counter(cached.get('usage') or {})
        self.base_as_of = cached.get('usage_base_as_of', cached.get('updated'))
        self.current, self.seen, self.missing = Counter(), set(), {}
        self.lock = Lock()

    def capture(self, job):
        key = str(job)
        with self.lock:
            if key in self.seen:
                return
            self.seen.add(key)
        try:
            usage = read_metadata(Path(job)/'metrics.json').get('usage')
            if not isinstance(usage, dict) or any(type(v) is not int or v < 0 for v in usage.values()):
                raise ValueError('Usage is unavailable or invalid')
        except (OSError, ValueError, TypeError) as error:
            with self.lock:
                self.missing[key] = str(error)
        else:
            with self.lock:
                self.current.update(usage)

    def snapshot(self):
        with self.lock:
            total = self.base.copy()
            total.update(self.current)
            return {'usage': dict(total), 'usage_since_launch': dict(self.current),
                    'usage_is_lower_bound': True, 'usage_base_as_of': self.base_as_of,
                    'usage_missing_since_launch': len(self.missing)}


def job_directories(directory):
    directory = Path(directory).resolve()
    yield from (directory/'jobs').glob('*')
    yield from (directory/'retry-passes').glob('*/jobs/*')


def record_digest(record):
    return sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def confidence_requests(directory):
    """Read explicitly authorized, frozen first reviews of Luna no-entry decisions."""
    requests = {}
    for path in sorted((Path(directory)/'confidence-passes').glob('*/manifest.json')):
        manifest = read_metadata(path)
        if (manifest['schema_version'] != CONFIDENCE_VERSION or manifest['model'] != MODEL
                or manifest['reasoning'] != 'medium' or manifest['scope'] != SCOPE):
            raise ValueError('Invalid Terra confidence manifest: ' + str(path))
        for request in manifest['papers']:
            receipt = request['luna_receipt']
            confidence = (receipt.get('quality') or {}).get('confidence')
            if (confidence == 'high' or receipt.get('models')
                    or (receipt.get('extractor') or {}).get('model') != LUNA
                    or receipt.get('arxiv') != request['arxiv']
                    or record_digest(receipt) != request['luna_receipt_sha256']):
                raise ValueError('Invalid frozen Luna no-entry receipt: ' + str(path))
            if request['paper_id'] in requests:
                raise ValueError('Duplicate Terra confidence request: ' + request['paper_id'])
            requests[request['paper_id']] = request
    return requests


def queue_confidence(directory, source=SOURCE, *, execute=False):
    """Authorize one first review of current Medium/Low/unreported Luna skips."""
    directory, source = Path(directory).resolve(), Path(source).resolve()
    with exclusive_lock(directory/'confidence-queue.lock', wait=True), source_lock(source, wait=True):
        data, links, store = read(source), load_links(path_for(source)), reviews(source)
        positive = {ref['paper_id'] for entry in data['entries'] for ref in entry['references']}
        queued = confidence_requests(directory)
        selected, counts = [], Counter()
        for paper in data['papers']:
            receipt = links['papers'].get(paper['id'])
            if (paper['id'] in positive or paper['id'] in store['papers'] or paper['id'] in queued
                    or paper.get('extractor', {}).get('model') != LUNA or not receipt
                    or (receipt.get('extractor') or {}).get('model') != LUNA
                    or receipt.get('arxiv') != paper['arxiv'] or receipt.get('models')
                    or (directory/'jobs'/job_id(paper['arxiv'])/'state.json').exists()):
                continue
            confidence = (receipt.get('quality') or {}).get('confidence')
            if confidence == 'high':
                continue
            label = confidence if confidence in ('medium', 'low') else 'not_reported'
            counts[label] += 1
            selected.append({'paper_id': paper['id'], 'arxiv': paper['arxiv'],
                             'luna_confidence': label, 'luna_receipt': deepcopy(receipt),
                             'luna_receipt_sha256': record_digest(receipt)})
        manifest = {'schema_version': CONFIDENCE_VERSION, 'model': MODEL, 'reasoning': 'medium',
                    'scope': SCOPE, 'created': now(), 'confidence_counts': dict(counts), 'papers': selected}
        result = {'eligible_papers': len(selected), 'confidence_counts': dict(counts),
                  'model': MODEL, 'scope': SCOPE, 'workers_shared_with_first_pass': True}
        if execute and selected:
            target = directory/'confidence-passes'/str(time.time_ns())/'manifest.json'
            target.parent.mkdir(parents=True)
            write_json(target, manifest)
            return {**result, 'queued_papers': len(selected), 'manifest': str(target)}
    return {**result, 'dry_run': not execute}


def confidence_candidates(directory, data, links, store):
    positive = {ref['paper_id'] for entry in data['entries'] for ref in entry['references']}
    papers = {paper['id']: paper for paper in data['papers']}
    selected = []
    for paper_id, request in confidence_requests(directory).items():
        paper, receipt = papers.get(paper_id), links['papers'].get(paper_id)
        if (paper is None or paper_id in positive or paper_id in store['papers']
                or paper.get('extractor', {}).get('model') != LUNA
                or paper['arxiv'] != request['arxiv'] or receipt is None
                or record_digest(receipt) != request['luna_receipt_sha256']
                or (Path(directory)/'jobs'/job_id(paper['arxiv'])/'state.json').exists()):
            continue
        selected.append(deepcopy(paper))
    return selected


def queue_retries(directory, source=SOURCE, *, execute=False):
    """Freeze one explicitly requested attempt for each currently unresolved paper."""
    directory, source = Path(directory).resolve(), Path(source).resolve()
    # Review receipts are replaced atomically. A separate queue lock prevents
    # duplicate requests without delaying Luna's catalogue writer; each request
    # is checked again against its exact prior-receipt digest before dispatch.
    with exclusive_lock(directory/'retry-queue.lock', wait=True):
        store = reviews(source)
        selected = []
        already_queued = {(item['paper_id'], item['previous_job'])
                          for manifest in (directory/'retry-passes').glob('*/manifest.json')
                          for item in read(manifest)['papers']}
        for paper_id, record in store['papers'].items():
            if not record['needs_terra_retry'] or record.get('model') != MODEL:
                continue
            previous_job = Path(record['job'])
            if ((paper_id, record['job']) in already_queued or (previous_job/'apply.json').exists()
                    or not (previous_job/'state.json').exists()
                    or read(previous_job/'state.json')['state'] == 'running'):
                continue
            selected.append({'paper_id': paper_id, 'arxiv': record['paper']['arxiv'],
                             'previous_job': record['job'], 'previous_review_sha256': record_digest(record)})
        manifest = {'schema_version': RETRY_VERSION, 'model': MODEL, 'reasoning': 'medium',
                    'scope': SCOPE, 'created': now(), 'papers': selected}
        if execute and selected:
            target = directory/'retry-passes'/str(time.time_ns())
            target.mkdir(parents=True)
            write_json(target/'response.schema.json', response_schema())
            write_json(target/'manifest.json', manifest)
            return {'queued_papers': len(selected), 'manifest': str(target/'manifest.json'),
                    'model': MODEL, 'scope': SCOPE, 'workers_shared_with_first_pass': True}
    return {'dry_run': not execute, 'eligible_papers': len(selected), 'model': MODEL, 'scope': SCOPE}


def retry_candidates(directory, data, store):
    """A frozen request permits one attempt; inconclusive outcomes do not loop."""
    papers = {paper['id']: paper for paper in data['papers']}
    choices = []
    for path in sorted((Path(directory)/'retry-passes').glob('*/manifest.json')):
        manifest = read_metadata(path)
        if (manifest['schema_version'] != RETRY_VERSION or manifest['model'] != MODEL
                or manifest['reasoning'] != 'medium' or manifest['scope'] != SCOPE):
            raise ValueError('Invalid Terra retry manifest: ' + str(path))
        for request in manifest['papers']:
            job = path.parent/'jobs'/job_id(request['arxiv'])
            current = store['papers'].get(request['paper_id'])
            paper = papers.get(request['paper_id'])
            if ((job/'state.json').exists() or current is None or paper is None
                    or not current['needs_terra_retry'] or current['job'] != request['previous_job']
                    or record_digest(current) != request['previous_review_sha256']
                    or paper['arxiv'] != request['arxiv']):
                continue
            choices.append((deepcopy(paper), job, request, deepcopy(current)))
    return choices


def inventory_snapshot(row):
    return {'fingerprints': sorted({fingerprint(e['specification'])
                                     for e in row.get('entries', [])})}


def review_path(source=SOURCE):
    return Path(source).with_name('extraction_reviews.json')


def review_route(record):
    """Only applied Luna/Terra model-inventory disagreements enter the Sol queue."""
    retry = record['state'] in ('unresolved', 'stale_baseline')
    sol = not retry and record.get('applied', False) and record.get('inventory_agrees') is False
    return {'needs_terra_retry': retry, 'needs_sol': sol,
            'next_pass': 'terra' if retry else 'sol' if sol else None}


def reviews(source=SOURCE):
    path = review_path(source)
    result = read(path) if path.exists() else {'schema_version': VERSION, 'papers': {}}
    if set(result) != {'schema_version', 'papers'} or result['schema_version'] != VERSION:
        raise ValueError('Unsupported extraction review store')
    for record in result['papers'].values():
        scope_inventory_record(record)
    return result


def scope_inventory_record(record):
    """Keep historical extraction outcomes while removing annotation certification."""
    record['scope'] = SCOPE
    record['quality'] = inventory_quality(record)
    record.pop('associations_agree', None)
    record.pop('associations_checked', None)
    for key in ('baseline', 'terra'):
        if record.get(key) is not None:
            record[key] = {'fingerprints': record[key]['fingerprints']}
    clean = bool(record.get('applied')) and not record['quality']['needs_followup']
    record['checked'] = clean and bool(record.get('inventory_agrees'))
    before = set((record.get('baseline') or {}).get('fingerprints', []))
    for entry in record.get('entries', []):
        entry['checked'] = clean and entry['fingerprint'] in before
    record.update(review_route(record))
    return record


def capture(data, links, paper):
    """Retain compact scientific records, including superseded inventories/evidence."""
    entries = []
    for stored in data['entries']:
        refs = [r for r in stored['references'] if r['paper_id'] == paper['id']]
        if refs:
            entries.append({**deepcopy(stored), 'references': deepcopy(refs)})
    annotation = deepcopy(links['papers'].get(paper['id']))
    return {'paper': deepcopy(paper), 'entries': entries, 'links': annotation,
            'snapshot': inventory_snapshot({'entries': entries})}


def candidates(data, store, directory=None, links=None):
    positive = {r['paper_id'] for e in data['entries'] for r in e['references']}
    selected = [deepcopy(p) for p in data['papers'] if p['id'] in positive
                and p.get('extractor', {}).get('model') == LUNA
                and p['id'] not in store['papers']]
    if directory is not None:
        selected.extend(confidence_candidates(directory, data, links, store))
    return selected


def specification_key(spec):
    return json.dumps(spec, sort_keys=True, separators=(',', ':'))


@lru_cache(maxsize=8192)
def _fingerprint(serialized):
    return identity(json.loads(serialized))['fingerprint']


def fingerprint(spec):
    return _fingerprint(specification_key(spec))


def _apply_result(job, row, baseline, data, links, store):
    """Apply one receipt to a private batch copy; never touch shared files."""
    job = Path(job)
    changed = False
    quality = inventory_quality(row)
    accepted = (row['state'] == 'ready' and row.get('outcome') in ('entries', 'skip')
                and row.get('coverage') == 'full_text')
    terra = inventory_snapshot(row) if accepted else None
    before = baseline['snapshot']
    inventory_agrees = bool(accepted and terra['fingerprints'] == before['fingerprints'])
    clean = accepted and not quality['needs_followup']
    record = {'paper': baseline['paper'], 'model': MODEL, 'reasoning': 'medium', 'scope': SCOPE,
              'state': ('agreement' if inventory_agrees else 'disagreement') if accepted else 'unresolved',
              'checked': inventory_agrees and clean, 'inventory_agrees': inventory_agrees,
              'applied': accepted, 'quality': quality, 'baseline': before, 'terra': terra,
              'reason': row.get('reason'), 'entries': [], 'finished': now(), 'job': str(job.resolve())}
    record.update(review_route(record))
    paper_id = baseline['paper']['id']
    previous = store['papers'].get(paper_id)
    if previous and previous['job'] != str(job.resolve()):
        if str(job.resolve()) in previous.get('previous_jobs', []):
            # Replaying an old journal must never replace a later retry receipt.
            return scope_inventory_record(read(job/'comparison.json')), False
        authorization = read(job/'retry.json') if (job/'retry.json').exists() else None
        if (authorization is None or not previous['needs_terra_retry']
                or authorization['paper_id'] != paper_id
                or authorization['previous_job'] != previous['job']
                or authorization['previous_review_sha256'] != record_digest(previous)):
            raise ValueError('Paper already reviewed by another job; explicit retry required')
        archived = read(job/'previous-review.json')
        if record_digest(archived) != record_digest(previous):
            raise ValueError('Prior Terra receipt changed since retry dispatch')
        record['previous_jobs'] = [*previous.get('previous_jobs', []), previous['job']]
        previous = None
    if previous:
        record = previous
    else:
        paper = next(p for p in data['papers'] if p['id'] == paper_id)
        current = capture(data, links, paper)['snapshot']
        # A prior crash may already have written Terra's inventory while
        # leaving the annotation file or review receipt to be recovered.
        recovered = (accepted and paper.get('extractor', {}).get('model') == MODEL
                     and current['fingerprints'] == terra['fingerprints'])
        selection = baseline.get('confidence_selection')
        receipt_changed = (selection is not None and
            record_digest(links['papers'].get(paper_id)) != selection['luna_receipt_sha256'])
        if (current['fingerprints'] != before['fingerprints'] or receipt_changed) and not recovered:
            record.update(state='stale_baseline', checked=False,
                          applied=False, reason='Paper changed while Terra was running')
            record.update(review_route(record))
        elif accepted:
            wanted = set(terra['fingerprints'])
            reserved = {name: fingerprint(e['specification'])
                        for e in data['entries']
                        for name in [e['id'], *[a['id'] for a in e.get('aliases', [])]]}
            retained = []
            for entry in data['entries']:
                if any(r['paper_id'] == paper_id for r in entry['references']):
                    entry['references'] = [r for r in entry['references'] if r['paper_id'] != paper_id]
                # Keep an orphan temporarily if Terra returns the same
                # specification, to preserve its established ID and aliases.
                if entry['references'] or fingerprint(entry['specification']) in wanted:
                    retained.append(entry)
            data['entries'] = retained
            fingerprints = {fingerprint(e['specification']): e for e in retained}
            for candidate in row['entries']:
                candidate = deepcopy(candidate)
                candidate_fingerprint = fingerprint(candidate['specification'])
                if candidate['id'] in reserved and reserved[candidate['id']] != candidate_fingerprint:
                    candidate['id'] += '-' + candidate_fingerprint[:12]
                for ref in candidate['references']:
                    ref['paper_id'] = paper_id
                data, _ = reconcile_entry(data, candidate, fingerprints=fingerprints)
            paper['extractor'] = {'provider': 'openai', 'model': MODEL, 'reasoning': 'medium'}
            paper['extraction_status'] = 'complete'
            links['papers'][paper_id] = bind_luna_receipt(links['papers'].get(paper_id),
                baseline['entries'], data['entries'], paper, fingerprints=fingerprints)
            for fp in terra['fingerprints']:
                entry = fingerprints[fp]
                record['entries'].append({'entry_id': entry['id'], 'fingerprint': fp,
                    'checked': clean and fp in before['fingerprints']})
            changed = True
    store['papers'][paper_id] = record
    return record, changed


def _validate_export_changes(data, changed_papers, cache):
    # The full catalogue's structural constraints are checked separately. The
    # expensive derived export checks only need repeating for changed spectra.
    entries, keys = [], set()
    for entry in data['entries']:
        key = specification_key(entry['specification'])
        if key not in cache and key not in keys and any(
                ref['paper_id'] in changed_papers for ref in entry['references']):
            entries.append(entry)
            keys.add(key)
    if entries:
        from .build import main_data
        main_data({**data, 'entries': entries})
        if len(cache) + len(keys) > 8192:
            cache.clear()
        cache.update(keys)


def finish_batch(items, source=SOURCE, *, specification_cache=None, export_cache=None):
    """Journal all receipts, validate once, then publish one recoverable batch.

    An interruption between shared-file writes replays the original journals,
    recognizing already-applied Terra fingerprints without another model call.
    """
    items = [(Path(job), row, baseline) for job, row, baseline in items]
    if not items:
        return []
    source = Path(source)
    specification_cache = {} if specification_cache is None else specification_cache
    export_cache = set() if export_cache is None else export_cache
    for job, row, baseline in items:
        write_json(job/'apply.json', {'row': row, 'baseline': baseline})
    with source_lock(source, wait=True):
        data, links, store = read(source), load_links(path_for(source)), reviews(source)
        records, changed_papers = [], set()
        for job, row, baseline in items:
            record, changed = _apply_result(job, row, baseline, data, links, store)
            records.append(record)
            if changed:
                changed_papers.add(baseline['paper']['id'])
        if changed_papers:
            validate(data, _specification_cache=specification_cache)
            _validate_export_changes(data, changed_papers, export_cache)
            write_json(source, data)
            write_json(path_for(source), links)
        write_json(review_path(source), store)
    for (job, _, _), record in zip(items, records):
        write_json(job/'comparison.json', record)
        write_json(job/'state.json', record)
        compact(job)
        (job/'apply.json').unlink(missing_ok=True)
    return records


def finish(job, row, baseline, source=SOURCE):
    return finish_batch([(job, row, baseline)], source)[0]


def restore_review_receipts(directory, source=SOURCE):
    """Restore missing metadata from completed jobs without reapplying spectra."""
    indexed = registered_jobs(reviews(source))
    saved = []
    for job in sorted(job_directories(directory)):
        if str(job.absolute()) in indexed:
            continue
        state = job/'state.json'
        if not state.exists() or (job/'apply.json').exists():
            continue
        record = read_metadata(state)
        if record['state'] == 'running':
            continue
        if record.get('model') != MODEL or Path(record['job']).resolve() != job.resolve():
            raise ValueError('Invalid saved review receipt: ' + str(job))
        saved.append(record)
    if not saved:
        return 0
    restored = 0
    with source_lock(source, wait=True):
        store = reviews(source)
        for record in saved:
            paper_id = record['paper']['id']
            previous = store['papers'].get(paper_id)
            if previous is not None:
                if previous['job'] != record['job']:
                    if record['job'] in previous.get('previous_jobs', []):
                        continue
                    if previous['job'] not in record.get('previous_jobs', []):
                        raise ValueError('Conflicting saved review jobs: ' + paper_id)
                    store['papers'][paper_id] = scope_inventory_record(record)
                    restored += 1
                continue
            store['papers'][paper_id] = scope_inventory_record(record)
            restored += 1
        if restored:
            write_json(review_path(source), store)
    return restored


def dispatch_snapshot(source, *, wait=False):
    """Read a consistent baseline without waiting on another writer by default."""
    try:
        with source_lock(source, wait=wait):
            return read(source), load_links(path_for(source)), reviews(source)
    except ValueError as error:
        if isinstance(error.__cause__, BlockingIOError):
            return None
        raise


def durable_worker(job, paper, body, provenance, instructions, config, baseline, *, accounting=None):
    row = run_worker(job, paper, body, provenance, instructions, config)
    write_json(job/'apply.json', {'row': row, 'baseline': baseline})
    if accounting is not None:
        accounting.capture(job)
    return row


def live_status(snapshot, *, queues, active, waiting, accounting, cached=None):
    """Publish scheduling progress without reopening historical state/metrics files."""
    _, _, store = snapshot
    cached = cached or {}
    records = list(store['papers'].values())
    result = {'model': MODEL, 'counts': dict(Counter(r['state'] for r in records)),
              'counts_scope': 'latest_review_receipts',
              'reviewed_papers': len(records), 'checked_papers': sum(r['checked'] for r in records),
              'checked_entry_references': sum(e['checked'] for r in records for e in r['entries']),
              'terra_retry_papers': sum(r['needs_terra_retry'] for r in records),
              'sol_queue_papers': sum(r['needs_sol'] for r in records),
              'model_calls_running': active, 'results_waiting_apply': waiting,
              'attempt_counts': deepcopy(cached.get('attempt_counts', {})),
              'attempt_counts_as_of': cached.get('attempt_counts_as_of', cached.get('updated')),
              'attempt_counts_cached': True, 'updated': now(), **queues}
    result.update(accounting.snapshot())
    return result


def status(directory, source=SOURCE, *, queue=False):
    directory = Path(directory)
    states, usage = Counter(), Counter()
    waiting = 0
    attempted = set()
    for job in job_directories(directory):
        path = job/'state.json'
        if not path.exists():
            continue
        state = read(path)['state']
        states[state] += 1
        attempted.add(path.parent.name)
        if state == 'running' and ((path.parent/'apply.json').exists() or
                ((path.parent/'result.json').exists() and (path.parent/'metrics.json').exists())):
            waiting += 1
    for job in job_directories(directory):
        if (job/'metrics.json').exists():
            usage.update(read(job/'metrics.json').get('usage') or {})
    store = reviews(source)
    records = list(store['papers'].values())
    data = read(source)
    links = load_links(path_for(source))
    result = {'model': MODEL, 'counts': dict(states), 'usage': dict(usage),
              'reviewed_papers': len(records), 'checked_papers': sum(r['checked'] for r in records),
              'checked_entry_references': sum(e['checked'] for r in records for e in r['entries']),
              'terra_retry_papers': sum(r['needs_terra_retry'] for r in records),
              'sol_queue_papers': sum(r['needs_sol'] for r in records),
              'model_calls_running': states['running'] - waiting,
              'results_waiting_apply': waiting,
              'awaiting_first_review': sum(job_id(p['arxiv']) not in attempted
                                          for p in candidates(data, store, directory, links)),
              'updated': now()}
    result['awaiting_confidence_review'] = len(confidence_candidates(directory, data, links, store))
    result['awaiting_requested_terra_retry'] = len(retry_candidates(directory, data, store))
    result['attempt_counts'] = dict(states)
    if queue:
        result['terra_retry_queue'] = [{'arxiv': r['paper']['arxiv'], 'state': r['state'],
                                       'job': r['job'], 'reason': r.get('reason')}
                                      for r in records if r['needs_terra_retry']]
        result['sol_queue'] = [{'arxiv': r['paper']['arxiv'], 'state': r['state'], 'job': r['job']}
                               for r in records if r['needs_sol']]
    return result


def run(directory, *, execute=False, workers=16, follow=False, source=SOURCE,
        corpus=CORPUS, executable=DEFAULT_EXECUTABLE):
    directory, source, corpus = map(lambda p: Path(p).resolve(), (directory, source, corpus))
    if not 1 <= workers <= 16:
        raise ValueError('Workers must be between one and sixteen')
    instructions = context()
    config = {'schema_version': VERSION, 'model': MODEL, 'reasoning': 'medium', 'review_scope': SCOPE,
              'workers': workers, 'follow': follow, 'source': str(source), 'corpus': str(corpus),
              'executable': str(executable), 'timeout': 900,
              'context_sha256': sha256(instructions.encode()).hexdigest(),
              'response_schema_sha256': sha256(json.dumps(response_schema(), sort_keys=True).encode()).hexdigest(),
              'worker_sha256': sha256(read_saved_bytes(Path(__file__).with_name('inventory_worker.py'))).hexdigest(),
              'runner_sha256': sha256(read_saved_bytes(Path(__file__))).hexdigest(),
              **source_preparation_policy()}
    if not execute:
        return {'dry_run': True, **config, 'eligible_papers': len(candidates(
            read(source), reviews(source), directory, load_links(path_for(source))))}
    check_worker(executable)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'jobs').mkdir(exist_ok=True)
    with exclusive_lock(directory/'run.lock'), exclusive_lock(source.with_suffix('.review.json.lock')):
        if (directory/'config.json').exists() and read(directory/'config.json') != config:
            raise ValueError('Frozen review configuration changed')
        write_json(directory/'config.json', config)
        write_json(directory/'response.schema.json', response_schema())
        try:
            cached_status = read_metadata(directory/'status.json')
        except (OSError, ValueError):
            cached_status = {}
        accounting = UsageLedger(cached_status)
        specification_cache, export_cache = {}, set()
        restored = restore_review_receipts(directory, source)
        indexed = registered_jobs(reviews(source))
        recoveries = []
        for job in sorted(job_directories(directory)):
            if (job/'apply.json').exists():
                saved = read_metadata(job/'apply.json')
                recoveries.append((job, saved['row'], saved['baseline']))
            elif str(job.absolute()) in indexed:
                continue
            elif (job/'state.json').exists() and read_metadata(job/'state.json')['state'] == 'running':
                baseline = read_metadata(job/'baseline.json')
                row = {'state': 'interrupted', 'paper': baseline['paper'],
                       'reason': 'Interrupted attempt preserved; no automatic paid retry'}
                if (job/'result.json').exists():
                    try:
                        body, provenance = read_source(baseline['paper']['arxiv'], corpus)
                        if provenance != read_metadata(job/'source.json'):
                            raise ValueError('Source changed since interrupted call')
                        result = read_metadata(job/'result.json')
                        entries = validate_response(baseline['paper'], result, legacy=True)
                        row = {key: result[key] for key in ('outcome', 'coverage', 'reason', 'confidence', 'uncertainty_reason')}
                        row.update(state='ready' if result['outcome'] != 'retry' else 'retry',
                                   paper=baseline['paper'], entries=entries, scope=SCOPE)
                        row['quality'] = inventory_quality(row)
                    except (ValueError, OSError, AwaitingSource) as error:
                        row['reason'] = str(error)
                recoveries.append((job, row, baseline))
        for offset in range(0, len(recoveries), workers):
            finish_batch(recoveries[offset:offset+workers], source,
                         specification_cache=specification_cache, export_cache=export_cache)
        terminating = Event()
        previous = {sig: signal.signal(sig, lambda *_: terminating.set()) for sig in (signal.SIGTERM, signal.SIGINT)}
        active, stop, last_scan, last_status = {}, None, 0, 0
        attempted = {job.name for job in (directory/'jobs').iterdir() if (job/'state.json').exists()}
        dispatch_data, dispatch_links, dispatch_store = dispatch_snapshot(source, wait=True)
        choices, retry_choices, source_waits = [], [], {}
        confidence_ids = set()
        queues = {'awaiting_first_review': 0, 'awaiting_confidence_review': 0,
                  'awaiting_requested_terra_retry': 0, 'queue_counts_as_of': now()}
        pending, writing, writer, writer_started = [], [], None, None
        pipeline = {'restored_review_receipts': restored, 'recovered_results': len(recoveries),
                    'batches_applied': 0, 'results_applied': 0,
                    'max_buffered_results': workers * 4}
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool, ThreadPoolExecutor(max_workers=1) as writer_pool:
                while True:
                    if terminating.is_set() or (directory/'STOP').exists() or (directory.parent/'STOP').exists():
                        stop = 'Stop requested; active workers draining'
                    if writer is not None and writer.done():
                        applied = writer.result()
                        for record in applied:
                            dispatch_store['papers'][record['paper']['id']] = record
                        pipeline.update(last_batch_size=len(writing),
                                        last_batch_seconds=round(time.monotonic()-writer_started, 3))
                        pipeline['batches_applied'] += 1
                        pipeline['results_applied'] += len(writing)
                        writer, writing = None, []
                    for future, (job, baseline) in list(active.items()):
                        if not future.done():
                            continue
                        row = future.result()
                        pending.append((job, row, baseline))
                        if row.get('infrastructure'):
                            stop = row['reason']
                        del active[future]
                    if not stop and time.monotonic()-last_scan > 15:
                        # Keep feeding known work while Luna writes, but give an
                        # idle reader a turn at the lock so an empty old snapshot
                        # cannot indefinitely hide newly ingested inventories.
                        # Application still rechecks the live fingerprints.
                        idle = not (active or pending or writer is not None or choices or retry_choices)
                        snapshot = dispatch_snapshot(source, wait=idle)
                        if snapshot is not None:
                            dispatch_data, dispatch_links, dispatch_store = snapshot
                            queues['queue_counts_as_of'] = now()
                        eligible = [paper for paper in candidates(dispatch_data, dispatch_store, directory, dispatch_links)
                                    if job_id(paper['arxiv']) not in attempted]
                        eligible_retries = retry_candidates(directory, dispatch_data, dispatch_store)
                        ready_at = time.monotonic()
                        choices = [paper for paper in eligible
                                   if source_waits.get(paper['arxiv'], 0) <= ready_at]
                        retry_choices = [item for item in eligible_retries
                                         if source_waits.get(item[0]['arxiv'], 0) <= ready_at]
                        # A rescan must not put expired source failures ahead of
                        # papers whose retained text has not yet been tried.
                        choices.sort(key=lambda p: (p['arxiv'] in source_waits,
                                                   source_waits.get(p['arxiv'], 0)))
                        retry_choices.sort(key=lambda item: (item[0]['arxiv'] in source_waits,
                                                source_waits.get(item[0]['arxiv'], 0)))
                        confidence_ids = {p['id'] for p in confidence_candidates(
                            directory, dispatch_data, dispatch_links, dispatch_store)}
                        queues.update(awaiting_first_review=len(eligible),
                                      awaiting_confidence_review=len(confidence_ids),
                                      awaiting_requested_terra_retry=len(eligible_retries),
                                      source_waiting_papers=sum(t > ready_at for t in source_waits.values()))
                        last_scan = time.monotonic()
                    source_scan_started = time.monotonic()
                    while (not stop and (choices or retry_choices) and len(active) < workers
                           and len(pending)+len(writing)+len(active) < workers * 4):
                        if terminating.is_set() or (directory/'STOP').exists() or (directory.parent/'STOP').exists():
                            stop = 'Stop requested; active workers draining'
                            break
                        retry_request, previous_review = None, None
                        if choices:
                            paper = choices.pop(0)
                            job = directory/'jobs'/job_id(paper['arxiv'])
                            if job.name in attempted:
                                continue
                        else:
                            paper, job, retry_request, previous_review = retry_choices.pop(0)
                            if (job/'state.json').exists():
                                continue
                        try:
                            body, provenance = read_source(paper['arxiv'], corpus)
                        except (AwaitingSource, ValueError, OSError):
                            source_waits[paper['arxiv']] = time.monotonic()+60
                            queues['source_waiting_papers'] = sum(t > time.monotonic() for t in source_waits.values())
                            if time.monotonic()-source_scan_started > 2:
                                break
                            continue
                        source_waits.pop(paper['arxiv'], None)
                        baseline = capture(dispatch_data, dispatch_links, paper)
                        if not baseline['entries'] and retry_request is None:
                            selection = confidence_requests(directory).get(paper['id'])
                            if selection is not None:
                                baseline['confidence_selection'] = deepcopy(selection)
                        job.mkdir(parents=True, exist_ok=True)
                        if retry_request is not None:
                            write_json(job/'previous-review.json', previous_review)
                            write_json(job/'retry.json', retry_request)
                        write_json(job/'baseline.json', baseline)
                        write_json(job/'state.json', {'state': 'running', 'paper': paper})
                        if retry_request is None:
                            attempted.add(job.name)
                            queues['awaiting_first_review'] -= 1
                            if paper['id'] in confidence_ids:
                                queues['awaiting_confidence_review'] -= 1
                        else:
                            queues['awaiting_requested_terra_retry'] -= 1
                        active[pool.submit(durable_worker, job, paper, body, provenance,
                                           instructions, config, baseline,
                                           accounting=accounting)] = (job, baseline)
                        if time.monotonic()-source_scan_started > 2:
                            break
                    if pending and writer is None:
                        writing, pending = pending[:workers*2], pending[workers*2:]
                        writer_started = time.monotonic()
                        writer = writer_pool.submit(finish_batch, writing, source,
                            specification_cache=specification_cache, export_cache=export_cache)
                    if time.monotonic()-last_status > 15:
                        pipeline.update(batch_in_progress=len(writing), buffered_results=len(pending))
                        value = live_status((dispatch_data, dispatch_links, dispatch_store),
                            queues=queues, active=len(active), waiting=len(pending)+len(writing),
                            accounting=accounting, cached=cached_status)
                        value.update(phase='draining' if stop else 'running', pid=os.getpid(),
                                     workers=workers, reason=stop, pipeline=pipeline)
                        write_json(directory/'status.json', value)
                        last_status = time.monotonic()
                    if not active and not pending and writer is None and (stop or (not follow and not choices and not retry_choices)):
                        break
                    futures = [*active, *([writer] if writer is not None else [])]
                    if futures:
                        wait(futures, timeout=2, return_when=FIRST_COMPLETED)
                    else:
                        terminating.wait(5)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        snapshot = dispatch_snapshot(source, wait=True)
        data, links, store = snapshot
        queues.update(awaiting_first_review=sum(job_id(p['arxiv']) not in attempted
                      for p in candidates(data, store, directory, links)),
                      awaiting_confidence_review=len(confidence_candidates(directory, data, links, store)),
                      awaiting_requested_terra_retry=len(retry_candidates(directory, data, store)),
                      queue_counts_as_of=now())
        value = live_status(snapshot, queues=queues, active=0, waiting=0,
                            accounting=accounting, cached=cached_status)
        value.update(phase='stopped' if stop else 'completed', pid=os.getpid(), workers=workers, reason=stop, pipeline=pipeline)
        write_json(directory/'status.json', value)
        return value


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'launch', 'status', 'queue-retries', 'queue-confidence'))
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--follow', action='store_true')
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--corpus', type=Path, default=CORPUS)
    parser.add_argument('--codex', default=DEFAULT_EXECUTABLE)
    parser.add_argument('--queue', action='store_true')
    args = parser.parse_args()
    if args.action == 'status':
        value = status(args.run_dir, args.source, queue=args.queue)
    elif args.action == 'queue-retries':
        value = queue_retries(args.run_dir, args.source, execute=args.execute)
    elif args.action == 'queue-confidence':
        value = queue_confidence(args.run_dir, args.source, execute=args.execute)
    elif args.action == 'launch' and args.execute:
        directory = args.run_dir.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        with exclusive_lock(directory/'launch.lock'):
            # The actual coordinator also owns this lock for its entire life.
            with exclusive_lock(directory/'run.lock'):
                pass
            if (directory/'process.json').exists():
                pid = read(directory/'process.json')['pid']
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError('Review coordinator already alive')
            if (directory/'STOP').exists() or (directory.parent/'STOP').exists():
                raise ValueError('STOP marker present')
            check_worker(args.codex)
            command = [sys.executable, '-B', '-u', '-m', 'bsm_atlas.entry_review', 'run',
                       '--run-dir', str(directory), '--execute', '--workers', str(args.workers),
                       '--source', str(args.source.resolve()), '--corpus', str(args.corpus.resolve()), '--codex', args.codex]
            if args.follow:
                command.append('--follow')
            log = directory/f'coordinator-{time.time_ns()}.log'
            with log.open('w') as stream:
                process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                           stdout=stream, stderr=stream, start_new_session=True)
            value = {'pid': process.pid, 'command': command, 'log': str(log), 'launched': now()}
            write_json(directory/'process.json', value)
    else:
        value = run(args.run_dir, execute=args.execute, workers=args.workers, follow=args.follow,
                    source=args.source, corpus=args.corpus, executable=args.codex)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
