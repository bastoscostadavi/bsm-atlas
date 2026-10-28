"""Private, immutable paper reservations shared by Codex and Claude batches."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from .catalogue import ROOT, SOURCE, exclusive_lock, load
from .citations import base_id, cached_response, private_json, timestamp


def allocation_root(source):
    source = Path(source).resolve()
    return (ROOT if source == SOURCE.resolve() else source.parent) / '.harvest/allocations'


def rows(root):
    result = []
    for path in sorted(root.glob('*.json')):
        row = json.loads(path.read_text())
        if row.get('schema_version') != 'bsm-paper-allocation-1':
            raise ValueError('Invalid paper-allocation record: ' + str(path))
        if row['provider'] not in {'codex', 'claude'}:
            raise ValueError('Invalid allocation provider')
        if len(row['arxiv_base_ids']) != len(set(map(base_id, row['arxiv_base_ids']))):
            raise ValueError('Duplicate paper in allocation')
        result.append(row)
    return result


def register_unlocked(manifest, provider, root):
    from .harvest import manifest as read_manifest
    manifest = Path(manifest).resolve()
    papers = read_manifest(manifest)['papers']
    ids = sorted({base_id(p['arxiv']) for p in papers})
    if len(ids) != len(papers):
        raise ValueError('A batch cannot reserve different versions of the same paper')
    digest = sha256(manifest.read_bytes()).hexdigest()
    key = sha256(str(manifest).encode()).hexdigest()
    target = root / (key + '.json')
    for row in rows(root):
        if row['manifest'] == str(manifest):
            if (row['manifest_sha256'] != digest or row['provider'] != provider or
                    row['arxiv_base_ids'] != ids):
                raise ValueError('Frozen allocation changed; inspect instead of redispatching')
            return row
        if set(ids).intersection(row['arxiv_base_ids']):
            raise ValueError('Paper already reserved by another batch: ' + row['manifest'])
    value = {'schema_version': 'bsm-paper-allocation-1', 'provider': provider,
             'manifest': str(manifest), 'manifest_sha256': digest,
             'arxiv_base_ids': ids, 'reserved_utc': timestamp()}
    private_json(target, value)
    return value


def register_manifest(manifest, provider='codex', source=SOURCE):
    if provider not in {'codex', 'claude'}:
        raise ValueError('Choose codex or claude for a batch allocation')
    root = allocation_root(source)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive_lock(root / 'registry.lock', wait=True):
        return register_unlocked(manifest, provider, root)


class NoMetadataNetwork:
    def get(self, url):
        raise ValueError('Frozen population cache is incomplete; no new INSPIRE sweep: ' + url)


def reserve_batch(directory, count=1000, *, provider='claude', ranking='citations',
                  population_cache=None, source=SOURCE):
    """Reserve exactly one disjoint primary-hep-ph batch, with zero model calls."""
    from .relevance import select_population
    if provider not in {'codex', 'claude'}:
        raise ValueError('Choose codex or claude')
    directory, source = Path(directory).resolve(), Path(source).resolve()
    root = allocation_root(source)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_relative_to(ROOT / 'website'):
        raise ValueError('Private reservations must not be placed in the public website')
    with exclusive_lock(root / 'registry.lock', wait=True):
        request_path, frozen_input = directory / 'reservation-request.json', directory / 'selection-input.json'
        request = {'provider': provider, 'count': count, 'ranking': ranking, 'source': str(source),
                   'population_cache': str(Path(population_cache).resolve()) if population_cache else None}
        manifest = directory / f'papers-{count}.json'
        if (directory / 'reservation.json').exists():
            if json.loads(request_path.read_text())['request'] != request:
                raise ValueError('Reservation parameters changed')
            registered = register_unlocked(manifest, provider, root)
            return {'reserved': len(registered['arxiv_base_ids']), 'manifest': str(manifest),
                    'provider': provider, 'primary_category': 'hep-ph', 'reused': True, 'model_calls': 0}
        if request_path.exists():
            saved = json.loads(request_path.read_text())
            if saved['request'] != request:
                raise ValueError('Reservation parameters changed')
        else:
            snapshot = load(source)
            saved = {'request': request,
                     'reserved_base_ids': sorted({i for row in rows(root) for i in row['arxiv_base_ids']})}
            # Bibliographic snapshot only: no model inventory, full paper, prompt or response.
            private_json(frozen_input, {**snapshot, 'entries': []})
            private_json(request_path, saved)
        client = None
        if population_cache:
            cache = Path(population_cache).resolve()
            pattern = re.compile(r'(?:population-total|cohort-(?:before|after|undated|\d{4}(?:-\d{2})?)-\d{4}|arxiv-resolution-\d+)\.json\Z')
            for path in sorted(cache.iterdir()):
                if not pattern.fullmatch(path.name):
                    continue
                original = json.loads(path.read_text())
                cached_response(cache, path.name, original['url'], NoMetadataNetwork())
                target = directory / path.name
                if target.exists():
                    cached_response(directory, path.name, original['url'], NoMetadataNetwork())
                    if json.loads(target.read_text())['sha256'] != original['sha256']:
                        raise ValueError('Reservation cache differs from frozen population')
                else:
                    os.link(path, target)
            client = NoMetadataNetwork()
        selected = select_population(directory, count, source=frozen_input, ranking=ranking,
            primary_only=True, client=client, exclude_ids=saved['reserved_base_ids'])
        current = {base_id(p['arxiv']) for p in load(source)['papers']}
        chosen = {item['arxiv'] for item in selected['candidates']}
        if chosen.intersection(current):
            raise ValueError('Unreserved writer added a selected paper during allocation; inspect before dispatch')
        value = register_unlocked(manifest, provider, root)
        private_json(directory / 'reservation.json', value)
        frozen_input.unlink()  # Finished selection needs only manifest, IDs and hashed metadata.
        return {'reserved': len(chosen), 'manifest': str(manifest), 'provider': provider,
                'primary_category': 'hep-ph', 'recorded_overlap': 0, 'reserved_overlap': 0,
                'citation_range': [selected['candidates'][0]['citation_count'],
                                   selected['candidates'][-1]['citation_count']], 'model_calls': 0}
