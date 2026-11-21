"""One user-authorized Luna recovery attempt per unresolved, locally readable paper.

No downloads, model substitution, baseline rewrites or automatic paid retries.
Uses the original extraction, mathematical validation, canonical intake and cleanup.
"""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import signal
import time
from threading import Event

from . import joint_harvest as joint
from .catalogue import ROOT, SOURCE, exclusive_lock, write_json
from .citations import base_id
from .corpus import CORPUS, read_index
from .corpus_queue import read_source, AwaitingSource
from .luna_slots import take, release
from .papers import job_id

FIRST = ROOT / '.harvest/luna-tex-first-primary-20261109'
DEFAULT = ROOT / '.harvest/luna-recovery-20261110'
VERSION = 'luna-recovery-1'


def read(path):
    return json.loads(Path(path).read_text())


def reasons(message):
    value = str(message)
    for prefix in ('Missing TeX dependency', 'Unsupported macro-mediated TeX dependency',
                   'Dynamic or unsupported TeX dependency', 'Missing literal TeX',
                   'Bibliography entry outside', 'Unsupported TeX macro definition',
                   'Response is not usable full TeX', 'Ambiguous independent main TeX'):
        if value.startswith(prefix):
            return prefix
    return value.split(':')[0][:120]


def prepare(directory=DEFAULT, source=SOURCE, corpus=CORPUS, harvest=None, *, source_only=False, workers=2, preparation_profile='tex-v2', candidates_from=None, exclude_manifests=()):
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('Workers must be between 1 and 16')
    directory, source, corpus = map(Path, (directory, source, corpus))
    if source_only:
        return prepare_source_only(directory, source, corpus, harvest, workers=workers, preparation_profile=preparation_profile, candidates_from=candidates_from, exclude_manifests=exclude_manifests)
    directory.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(directory / 'prepare.lock'):
        manifest = directory / 'manifest.json'
        if manifest.exists():
            return read(directory / 'selection.json')
        papers = {p['arxiv']: p for p in read(source)['papers']
                  if p.get('extraction_status') == 'unresolved'}
        # The mirror's complete index supplies the primary-category scope.
        primary = {r['arxiv'] for r in read_index(corpus) if r['categories'][0] == 'hep-ph'}
        wanted = {job_id(i): i for i in papers}
        baselines = {}
        for folder, dirs, _ in os.walk(harvest or ROOT / '.harvest'):
            if Path(folder).name != 'jobs':
                continue
            for name in dirs:
                if name not in wanted:
                    continue
                path = Path(folder) / name / 'state.json'
                if not path.exists():
                    continue
                row = read(path)
                identifier = row.get('paper', {}).get('arxiv')
                if identifier not in papers:
                    continue
                stamp = path.stat().st_mtime_ns
                if identifier not in baselines or stamp > baselines[identifier]['stamp']:
                    baselines[identifier] = {'path': str(path.resolve()), 'stamp': stamp,
                        'state': row.get('state'), 'reason': row.get('reason', '')}
            dirs[:] = []
        selected, deferred, counts = [], [], Counter()
        for identifier, paper in papers.items():
            if base_id(identifier) not in primary:
                deferred.append({'arxiv': identifier, 'reason': 'not_primary_hep_ph'})
                counts['not_primary_hep_ph'] += 1
                continue
            try:
                body, provenance = read_source(identifier, corpus)
            except (AwaitingSource, ValueError, OSError) as error:
                reason = 'not_downloaded' if isinstance(error, AwaitingSource) else reasons(error)
                deferred.append({'arxiv': identifier, 'reason': reason})
                counts[reason] += 1
                continue
            previous = baselines.get(identifier)
            # A failure without a surviving detailed receipt can still be retried;
            # catalogue extraction_status is the authoritative paper selection.
            selected.append({'paper': {k: paper[k] for k in ('id', 'arxiv', 'title', 'authors')},
                             'baseline': previous, 'source': provenance})
        # Source preparation/infrastructure failures first, then scientific failures.
        selected.sort(key=lambda row: (
            (row['baseline'] or {}).get('state') not in ('source_unavailable', 'retry', 'interrupted'),
            row['paper']['arxiv']))
        write_json(manifest, {'schema_version': VERSION, 'papers': selected})
        write_json(directory / 'source-deferred.json', {'papers': deferred})
        summary = {'schema_version': VERSION, 'created': joint.now(),
            'unresolved': len(papers), 'ready_for_one_retry': len(selected),
            'deferred': dict(counts), 'model': 'gpt-6-luna', 'reasoning': 'medium',
            'workers': 2, 'shared_paid_call_limit': 16, 'first_pass_priority': True,
            'manifest_sha256': sha256(manifest.read_bytes()).hexdigest()}
        write_json(directory / 'selection.json', summary)
        return summary


def preparation_reader(profile='tex-v2'):
    if profile == 'tex-v2':
        return read_source
    if profile == 'tex-v3':
        from functools import partial
        from . import tex_source_v3
        return partial(read_source, preparer=tex_source_v3._prepare)
    raise ValueError('Unknown source preparation profile: '+str(profile))


def prior_model_attempt(job, row):
    return (any((job/f).exists() for f in ('metrics.json','result.json','events.jsonl','source.json')) or
            any(job.glob('attempt-*/metrics.json')) or
            row.get('state') in {'running','ready','ingested','invalid','retry','interrupted',
                                 'complete','completed','extracted','proposed','accepted','failed'} or
            row.get('outcome') in {'entries','skip','retry'})


def prepare_source_only(directory, source, corpus, harvest=None, *, workers=16, preparation_profile='tex-v2', candidates_from=None, exclude_manifests=()):
    """Freeze only source-blocked papers with no evidence of any prior paid call.

    Inspect all surviving historical receipts, by arXiv base ID across versions.
    A model result, metrics receipt or attempted-worker state excludes a paper,
    even if a later source failure would otherwise make it look eligible.
    """
    directory, source, corpus = map(Path, (directory, source, corpus))
    directory.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(directory/'prepare.lock'):
        manifest = directory/'manifest.json'
        if manifest.exists():
            return read(directory/'selection.json')
        reader = preparation_reader(preparation_profile)
        catalogue = read(source)
        allowed = None if candidates_from is None else {base_id(row['arxiv']) for row in read(candidates_from)['papers']}
        reserved = set()
        reservations = []
        for path in exclude_manifests:
            path = Path(path)
            reserved.update(base_id(row['paper']['arxiv'] if 'paper' in row else row['arxiv']) for row in read(path)['papers'])
            reservations.append({'path':str(path.resolve()), 'sha256':sha256(path.read_bytes()).hexdigest()})
        linked_papers = {ref['paper_id'] for entry in catalogue.get('entries', []) for ref in entry.get('references', [])}
        papers = {base_id(p['arxiv']): p for p in catalogue['papers']
                  if p.get('extraction_status') == 'unresolved' and
                  (allowed is None or base_id(p['arxiv']) in allowed) and base_id(p['arxiv']) not in reserved}
        primary = {r['arxiv'] for r in read_index(corpus) if r['categories'][0] == 'hep-ph'}
        names = {re.sub(r'v\d+$', '', job_id(p['arxiv'])) for p in papers.values()}
        baselines, paid, receipt_count = {}, set(), 0
        for folder, dirs, _ in os.walk(harvest or ROOT/'.harvest'):
            if Path(folder).name != 'jobs':
                continue
            for name in dirs:
                if re.sub(r'v\d+$', '', name) not in names:
                    continue
                job = Path(folder)/name
                state = job/'state.json'
                if not state.exists():
                    state = job/'status.json'
                if not state.exists():
                    # A metrics/result-only job is still a prior attempt.
                    if prior_model_attempt(job, {}):
                        for bid, paper in papers.items():
                            if re.sub(r'v\d+$','',job_id(paper['arxiv'])) == re.sub(r'v\d+$','',name):
                                paid.add(bid)
                    continue
                row = read(state);identifier = (row.get('paper') or {}).get('arxiv')
                if identifier is None:
                    # Older workers name jobs by pinned ID but omit the paper.
                    matching = [p['arxiv'] for p in papers.values() if job_id(p['arxiv']) == name]
                    if len(matching) != 1:
                        continue
                    identifier = matching[0]
                bid = base_id(identifier)
                if bid not in papers:
                    continue
                receipt_count += 1
                if (papers[bid].get('extractor') or papers[bid]['id'] in linked_papers or
                        prior_model_attempt(job, row)):
                    paid.add(bid)
                if row.get('state') == 'source_unavailable':
                    candidate = {'path':str(state.resolve()),'state':'source_unavailable',
                                 'arxiv':identifier,'reason':row.get('reason',''),
                                 'sha256':sha256(state.read_bytes()).hexdigest()}
                    baselines.setdefault(bid, candidate)
            dirs[:] = []
        selected, deferred, counts = [], [], Counter()
        candidates=[]
        for bid, paper in papers.items():
            if bid not in primary: reason='not_primary_hep_ph'
            elif bid in paid or paper.get('extractor') or paper['id'] in linked_papers: reason='prior_model_attempt'
            elif bid not in baselines: reason='no_pre_extraction_block_receipt'
            else:
                candidates.append((bid,paper));continue
            counts[reason]+=1
        def preflight(item):
            bid,paper=item
            try:
                _, provenance = reader(paper['arxiv'],corpus)
            except (AwaitingSource,ValueError,OSError) as error:
                return None, {'arxiv':paper['arxiv'],'reason':reasons(error),'detail':str(error)}
            return {'paper':{k:paper[k] for k in ('id','arxiv','title','authors')},
                    'baseline':baselines[bid],'source':provenance}, None
        with ThreadPoolExecutor(max_workers=8) as pool:
            for n,(item,error) in enumerate(pool.map(preflight,candidates),1):
                if error:
                    deferred.append(error);counts[error['reason']]+=1
                else:
                    selected.append(item)
                if n%100 == 0:
                    write_json(directory/'preparation-status.json',{'phase':'preparing','checked':n,
                        'candidates':len(candidates),'ready':len(selected),'deferred':len(deferred),'updated':joint.now()})
        selected.sort(key=lambda row:row['paper']['arxiv'])
        write_json(manifest,{'schema_version':VERSION,'selection_scope':'blocked_before_extraction', 'papers':selected})
        write_json(directory/'source-deferred.json',{'papers':deferred})
        summary={'schema_version':VERSION,'created':joint.now(),'selection_scope':'blocked_before_extraction',
                 'unresolved':len(papers),'source_blocked_without_model_attempt':len(candidates),
                 'ready_for_one_retry':len(selected),'deferred':dict(counts),'historical_receipts_checked':receipt_count,
                 'model':'gpt-6-luna','reasoning':'medium','workers':workers,'shared_paid_call_limit':16,
                 'first_pass_priority':True,'manifest_sha256':sha256(manifest.read_bytes()).hexdigest()}
        if preparation_profile != 'tex-v2':
            summary['source_preparation_profile'] = preparation_profile
        if candidates_from is not None:
            path=Path(candidates_from)
            summary['candidate_source']={'path':str(path.resolve()),'sha256':sha256(path.read_bytes()).hexdigest()}
        if reservations:
            summary['excluded_reservations']=reservations
            summary['reserved_base_ids_excluded']=len(reserved)
        write_json(directory/'selection.json',summary)
        write_json(directory/'preparation-status.json',{'phase':'completed','checked':len(candidates),
             'ready':len(selected),'deferred':len(deferred),'updated':joint.now()})
        return summary


def permission(first=FIRST, probe=False, current=None):
    """Fail closed on STOP/access failures; first pass receives dispatch priority."""
    if any(p.exists() for p in (first/'STOP', first/'rolling/run/STOP', first/'supervisor/MAINTENANCE')):
        return False, 'First-pass STOP or maintenance marker'
    try:
        status = read(first/'status.json') if current is None else current
    except FileNotFoundError:
        # Do not dispatch from stale status when an external file replacement
        # temporarily makes the exact operational file unavailable.
        return False, 'First-pass status unavailable; waiting for the exact file'
    reason = str(status.get('reason') or '')
    blocked = any(s in reason.lower() for s in ('429', 'quota', 'usage limit', 'authentication', 'unauthorized', '403', '401'))
    if blocked:
        return (True, 'Single explicitly authorized access probe') if probe else (False, 'Waiting for first-pass provider access to recover')
    if status.get('phase') in ('blocked', 'stopped', 'draining'):
        return False, 'First pass requires attention'
    if status.get('phase') == 'completed':
        return True, 'First pass is complete; stale ready-buffer counters do not reserve slots'
    pipeline = status.get('pipeline', {})
    producer = status.get('producer', {})
    if pipeline.get('active_workers', 0) >= 14 or producer.get('ready_buffer', 0):
        return False, 'New-paper first pass has priority'
    return True, 'Spare call capacity and no queued first-pass dispatch'


def restore(directory, source=SOURCE, corpus=CORPUS, *, reader=None):
    """Recover existing responses/journals without invoking another paid call."""
    reader = reader or read_source
    for job in (directory/'jobs').iterdir():
        if (job/'intake.json').exists():
            joint.intake(directory, [read(job/'intake.json')], source)
        elif (job/'state.json').exists() and read(job/'state.json').get('state') == 'running':
            state = read(job/'state.json')
            if not (job/'metrics.json').exists():
                raise ValueError('Recovery job has no durable completion metrics; inspect possible live paid worker: '+str(job))
            if (job/'result.json').exists():
                result = read(job/'result.json')
                try:
                    body, _ = reader(state['paper']['arxiv'], corpus)
                    entries, annotations = joint.validate_response(state['paper'], result, body, joint.taxonomies())
                    row = {k: result[k] for k in ('outcome', 'coverage', 'reason', 'confidence', 'uncertainty_reason')}
                    row.update(state='retry' if result['outcome']=='retry' else 'ready',
                               paper=state['paper'], entries=entries, annotations=annotations,
                               result_sha256=sha256((job/'result.json').read_bytes()).hexdigest())
                    joint.intake(directory, [row], source)
                    continue
                except (ValueError, OSError, KeyError, TypeError):
                    pass
            write_json(job/'state.json', {'state': 'interrupted', 'paper': state['paper'],
                'reason': 'Interrupted recovery attempt retained; no automatic paid retry', 'finished': joint.now()})
            joint.compact(job)


def run(directory=DEFAULT, *, execute=False, probe=False, source=SOURCE, corpus=CORPUS, first=FIRST):
    directory, source, corpus, first = map(lambda p: Path(p).resolve(), (directory, source, corpus, first))
    selection = read(directory/'selection.json')
    assert selection['manifest_sha256'] == sha256((directory/'manifest.json').read_bytes()).hexdigest()
    if not execute:
        return selection
    reader = preparation_reader(selection.get('source_preparation_profile','tex-v2'))
    workers = selection.get('workers', 2)
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('Workers must be between 1 and 16')
    joint.check_worker(joint.DEFAULT_EXECUTABLE)
    (directory/'jobs').mkdir(exist_ok=True)
    with exclusive_lock(directory/'run.lock'):
        policy = {'schema_version': VERSION, 'model': 'gpt-6-luna', 'reasoning': 'medium',
                  'timeout': 900, 'executable': joint.DEFAULT_EXECUTABLE, 'workers': workers,
                  'context_sha256': sha256(joint.context().encode()).hexdigest(),
                  'taxonomies_sha256': sha256(json.dumps(joint.taxonomies(),sort_keys=True).encode()).hexdigest(),
                  'scientific_runner_sha256': sha256(Path(joint.__file__).read_bytes()).hexdigest(),
                  'manifest_sha256': selection['manifest_sha256'], 'first': str(first),
                  'source': str(source), 'corpus': str(corpus)}
        if selection.get('selection_scope') == 'blocked_before_extraction':
            from . import tex_source
            policy['selection_scope'] = selection['selection_scope']
            policy['source_preparation_sha256'] = sha256(Path(tex_source.__file__).read_bytes()).hexdigest()
            policy['cleaner_version'] = tex_source.CLEANER_VERSION
            if selection.get('source_preparation_profile') == 'tex-v3':
                from . import tex_source_v3
                policy['source_preparation_profile'] = 'tex-v3'
                policy['base_source_preparation_sha256'] = policy['source_preparation_sha256']
                policy['source_preparation_sha256'] = sha256(Path(tex_source_v3.__file__).read_bytes()).hexdigest()
                policy['cleaner_version'] = tex_source_v3.CLEANER_VERSION
        if (directory/'policy.json').exists() and read(directory/'policy.json') != policy:
            raise ValueError('Frozen recovery settings changed')
        write_json(directory/'policy.json', policy)
        write_json(directory/'response.schema.json', joint.response_schema())
        restore(directory, source, corpus, reader=reader)
        items = read(directory/'manifest.json')['papers']
        from .recovery_progress import RecoveryProgress
        progress = RecoveryProgress(directory, read)
        stop, active, stopping = None, {}, Event()
        previous = {sig: signal.signal(sig, lambda *_: stopping.set()) for sig in (signal.SIGTERM, signal.SIGINT)}
        probe_used = (directory/'access-probe.json').exists()
        instructions, definitions = joint.context(), joint.taxonomies()
        last_checkpoint = 0
        def checkpoint(phase, waiting=None):
            for job in active.values():
                progress.refresh(job)
            counts, usage = progress.snapshot()
            value = {'phase': phase, 'pid': os.getpid(), 'updated': joint.now(), 'model': 'gpt-6-luna',
                     'reasoning': 'medium', 'workers': workers, 'selected': len(items), 'counts': dict(counts),
                     'active_workers': len(active), 'reason': stop or waiting, 'usage': dict(usage)}
            write_json(directory/'status.json', value)
            return value
        def worker(job, paper, body, provenance, slot):
            try:
                return joint.run_worker(job, paper, body, provenance, instructions, definitions, policy)
            finally:
                release(slot)
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                while True:
                    if stopping.is_set() or (directory/'STOP').exists() or (first/'STOP').exists() or (first/'rolling/run/STOP').exists():
                        stop = 'Stop requested; active calls drain'
                    completed, completed_jobs = [], []
                    for future, job in list(active.items()):
                        if not future.done():
                            continue
                        row = future.result()
                        # Every delta is durable before the shared catalogue lock
                        # is acquired once for this completed group. A crash can
                        # replay individual journals without another model call.
                        write_json(job/'intake.json', row)
                        completed.append(row)
                        completed_jobs.append(job)
                        if row.get('infrastructure'):
                            stop = row['reason']
                        del active[future]
                    if completed:
                        joint.intake(directory, completed, source)
                        for job in completed_jobs:
                            progress.refresh(job)
                    allowed, waiting = permission(first, probe=probe and not probe_used)
                    pending = []
                    if not stop:
                        known = None
                        if allowed:
                            try:
                                known = {p['arxiv']: p.get('extraction_status') for p in read(source)['papers']}
                            except FileNotFoundError:
                                allowed = False
                                waiting = 'Working catalogue unavailable; waiting for the exact file'
                        for item in items:
                            paper = item['paper']; job = directory/'jobs'/job_id(paper['arxiv'])
                            if (job/'state.json').exists() or job in active.values():
                                continue
                            pending.append(item)
                            if not allowed:
                                break
                            if known.get(paper['arxiv']) != 'unresolved':
                                job.mkdir(exist_ok=True)
                                write_json(job/'state.json', {'state':'already_resolved', 'paper':paper})
                                progress.refresh(job)
                                continue
                            if not allowed or len(active) >= (1 if probe else workers):
                                break
                            slot = take()
                            if slot is None:
                                waiting = 'Shared 16-call limit reached'
                                break
                            try:
                                body, provenance = reader(paper['arxiv'], corpus)
                            except (AwaitingSource, ValueError, OSError) as error:
                                release(slot); job.mkdir(exist_ok=True)
                                write_json(job/'state.json', {'state':'source_deferred', 'paper':paper, 'reason':str(error)})
                                progress.refresh(job)
                                continue
                            if (selection.get('selection_scope') == 'blocked_before_extraction' and
                                    provenance.get('text_sha256') != item['source'].get('text_sha256')):
                                release(slot)
                                raise ValueError('Prepared source changed after selection: '+paper['arxiv'])
                            job.mkdir(exist_ok=True)
                            write_json(job/'baseline.json', item)
                            write_json(job/'state.json', {'state':'running', 'paper':paper, 'started':joint.now()})
                            progress.refresh(job)
                            if probe:
                                write_json(directory/'access-probe.json', {'arxiv':paper['arxiv'], 'started':joint.now(),
                                    'authorization':'User requested Luna retries now; one access attempt, no repeated probes'})
                                probe_used = True
                            try:
                                active[pool.submit(worker, job, deepcopy(paper), body, provenance, slot)] = job
                            except BaseException:
                                release(slot)
                                raise
                            if probe:
                                break
                    if probe and probe_used and not active:
                        return checkpoint('blocked' if stop else 'probe_completed', waiting)
                    if not active and (stop or not pending):
                        return checkpoint('blocked' if stop else 'completed', waiting)
                    if time.monotonic()-last_checkpoint >= 10:
                        checkpoint('draining' if stop else ('running' if active else 'waiting'), waiting)
                        last_checkpoint = time.monotonic()
                    if active:
                        wait(active, timeout=2, return_when=FIRST_COMPLETED)
                    else:
                        time.sleep(10)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','run'])
    parser.add_argument('--run-dir', type=Path, default=DEFAULT)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--source-only', action='store_true', help='Only pre-extraction source blocks; exclude all prior model attempts')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--preparation-profile',choices=['tex-v2','tex-v3'],default='tex-v2')
    parser.add_argument('--candidates-from',type=Path)
    parser.add_argument('--exclude-manifest',type=Path,action='append',default=[])
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    value = prepare(args.run_dir,source_only=args.source_only,workers=args.workers,preparation_profile=args.preparation_profile,candidates_from=args.candidates_from,exclude_manifests=args.exclude_manifest) if args.action=='prepare' else run(args.run_dir, execute=args.execute, probe=args.probe)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
