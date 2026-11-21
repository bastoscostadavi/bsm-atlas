"""Shared TeX mirror priority queue and verified, read-only corpus access.

Only the mirror fetches sources. Extraction requests exact versions and waits
for atomic publication of meta.json + source/; it never prunes the corpus.
"""
import json
from hashlib import sha256
from pathlib import Path

from .catalogue import exclusive_lock
from .citations import base_id
from .corpus import CORPUS, paper_dir, _safe_member
from .tex_source import _decode, _prepare, MAX_EXPANDED, MAX_MEMBERS


class AwaitingSource(Exception):
    pass


class UnusableSource(ValueError):
    pass


def requests(directory=CORPUS):
    path = Path(directory) / 'priority-requests.jsonl'
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for row in records:
        if set(row) != {'arxiv', 'version', 'primary'} or row['primary'] != 'hep-ph':
            raise ValueError('Invalid primary-hep-ph priority request')
        paper_dir(directory, row['arxiv'], row['version'])
    keys = [(r['arxiv'], r['version']) for r in records]
    if len(set(keys)) != len(keys):
        raise ValueError('Repeated priority source')
    return records


def enqueue(papers, directory=CORPUS, *, front=False):
    from .catalogue import write_json
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(directory / 'priority.lock', wait=True):
        rows = requests(directory)
        keys = {(r['arxiv'], r['version']) for r in rows}
        preferred=[]
        for paper in papers:
            identifier = paper['arxiv']
            base = base_id(identifier)
            version = identifier[len(base):]
            paper_dir(directory, base, version)
            preferred.append((base,version))
            if (base, version) not in keys:
                rows.append({'arxiv': base, 'version': version, 'primary': 'hep-ph'})
                keys.add((base, version))
        if front:
            order={key:i for i,key in enumerate(dict.fromkeys(preferred))}
            rows.sort(key=lambda r:order.get((r['arxiv'],r['version']),len(order)))
        path = directory / 'priority-requests.jsonl'
        # Atomic same-directory replacement; mirror readers see complete lists.
        temporary = directory / 'priority-requests.jsonl.tmp'
        temporary.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        temporary.replace(path)
        write_json(directory / 'retention-policy.json', {
            'retain': 'versioned TeX and paper-specific text dependencies',
            'delete_sources_after_extraction': False,
            'requested_by': 'user', 'effective': '2026-11-08'})
    return len(rows)


class PriorityReader:
    def __init__(self, directory=CORPUS):
        self.directory, self.stamp, self.rows = Path(directory), None, []

    def __call__(self):
        path = self.directory / 'priority-requests.jsonl'
        stamp = (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None
        if stamp != self.stamp:
            self.rows, self.stamp = requests(self.directory), stamp
        return self.rows


def read_source(identifier, directory=CORPUS, *, preparer=None):
    """Verify retained bytes, then clean literal local TeX dependencies in memory."""
    base = base_id(identifier)
    target = paper_dir(directory, base, identifier[len(base):])
    meta_path = target / 'meta.json'
    if not meta_path.exists():
        raise AwaitingSource(identifier)
    if meta_path.is_symlink() or target.is_symlink():
        raise UnusableSource('Symlink corpus source refused')
    meta_bytes = meta_path.read_bytes()
    meta = json.loads(meta_bytes)
    if meta.get('arxiv') != base or meta.get('version') != identifier[len(base):]:
        raise UnusableSource('Corpus version mismatch')
    if meta.get('status') != 'ok':
        raise UnusableSource('Corpus status: ' + str(meta.get('status')))
    listing = meta.get('files', [])
    if not listing or len(listing) > MAX_MEMBERS:
        raise UnusableSource('Missing or oversized corpus source inventory')
    sources, total = {}, 0
    root = (target / 'source').resolve()
    for member in listing:
        parts = _safe_member(member['path'])
        if not parts:
            raise UnusableSource('Unsafe corpus source path')
        path = target / 'source' / Path(*parts)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise UnusableSource('Unsafe corpus dependency')
        if path.stat().st_size != member['bytes']:
            raise UnusableSource('Corpus source length mismatch')
        total += member['bytes']
        if total > MAX_EXPANDED:
            raise UnusableSource('Corpus source exceeds expansion bound')
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != member['sha256']:
            raise UnusableSource('Corpus source hash mismatch')
        decoded = _decode(raw)
        if decoded is not None:
            if member['path'] in sources:
                raise UnusableSource('Duplicate source member')
            sources[member['path']] = decoded
    cleaned, _, preparation = (preparer or _prepare)(sources)
    from .papers import full_text
    full_text(cleaned)
    return cleaned, {'corpus_meta': str(meta_path.resolve()),
                     'corpus_meta_sha256': sha256(meta_bytes).hexdigest(),
                     'text_sha256': sha256(cleaned.encode()).hexdigest(), **preparation}
