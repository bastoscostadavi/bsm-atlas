"""Pinned source snapshots and complete downloads outside ordinary Git blobs."""
import gzip
from hashlib import sha256
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / 'atlas/snapshot.json'
REPOSITORY = 'bastoscostadavi/bsm-atlas'
SOURCES = ['catalogue.json', 'literature_links.json']
DOWNLOAD_FILES = {'catalogue': 'catalogue.json.gz', 'sqlite': 'field-catalogue.sqlite.gz',
                  'field-catalogue': 'field-catalogue.csv.gz', 'nonabelian-cores': 'nonabelian-cores.csv.gz',
                  'semisimple-algebras': 'semisimple-algebras.csv.gz', 'full-gauge-algebras': 'full-gauge-algebras.csv.gz'}


def read_descriptor(root=ROOT):
    path = Path(root) / 'atlas/snapshot.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get('schema_version') != 'atlas-data-snapshot-1' or data.get('repository') != REPOSITORY:
        raise ValueError('Unsupported data snapshot descriptor')
    if not isinstance(data.get('tag'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', data['tag']):
        raise ValueError('Invalid snapshot tag')
    if set(data.get('sources', {})) != set(SOURCES):
        raise ValueError('Snapshot must pin both source files')
    for item in data['sources'].values():
        for key in ['bytes', 'compressedBytes']:
            if type(item.get(key)) is not int or item[key] < 0:
                raise ValueError('Invalid snapshot byte count')
        for key in ['sha256', 'compressedSha256']:
            if not isinstance(item.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', item[key]):
                raise ValueError('Invalid snapshot checksum')
    return data


def download_links(root=ROOT):
    data = read_descriptor(root)
    if not data:
        return {}
    raw = (Path(root) / 'atlas/catalogue.json').read_bytes()
    return data['downloads'] if sha256(raw).hexdigest() == data['sources']['catalogue.json']['sha256'] else {}


def restore(root=ROOT):
    """Restore missing inputs only. Never overwrite a live ingestion store."""
    root = Path(root)
    missing = [name for name in SOURCES if not (root / 'atlas' / name).exists()]
    if not missing:
        return
    descriptor = read_descriptor(root)
    if descriptor is None:
        raise ValueError('No pinned source snapshot; supply atlas/snapshot.json')
    from .catalogue import source_lock
    with source_lock(root / 'atlas/catalogue.json', wait=True):
        for name in missing:
            target = root / 'atlas' / name
            if target.exists():
                continue
            expected = descriptor['sources'][name]
            if not expected['url'].startswith('https://github.com/' + REPOSITORY + '/releases/download/'):
                raise ValueError('Unexpected snapshot download origin')
            request = urllib.request.Request(expected['url'], headers={'User-Agent': 'BSM-Atlas-snapshot'})
            if expected['compressedBytes'] > 256 * 1024**2 or expected['bytes'] > 2 * 1024**3:
                raise ValueError('Snapshot exceeds restoration bound')
            with urllib.request.urlopen(request, timeout=60) as response:
                compressed = response.read(expected['compressedBytes'] + 1)
            if len(compressed) != expected['compressedBytes'] or sha256(compressed).hexdigest() != expected['compressedSha256']:
                raise ValueError('Snapshot compressed hash/length mismatch: ' + name)
            raw = bytearray()
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                while True:
                    chunk = stream.read(min(1024**2, expected['bytes'] + 1 - len(raw)))
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > expected['bytes']:
                        raise ValueError('Snapshot expands beyond declared size')
            if len(raw) != expected['bytes'] or sha256(raw).hexdigest() != expected['sha256']:
                raise ValueError('Snapshot source hash/length mismatch: ' + name)
            parsed = json.loads(raw)
            if name == 'catalogue.json':
                from .catalogue import validate
                validate(parsed)
            elif parsed.get('schema_version') != 'atlas-literature-links-1':
                raise ValueError('Invalid literature snapshot')
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.' + name + '-', delete=False) as handle:
                temporary = Path(handle.name)
                try:
                    handle.write(raw); handle.flush(); os.fsync(handle.fileno())
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)


def verify(root=ROOT):
    descriptor = read_descriptor(root)
    if descriptor is None:
        raise ValueError('Missing snapshot descriptor')
    for name in SOURCES:
        raw = (Path(root) / 'atlas' / name).read_bytes()
        expected = descriptor['sources'][name]
        if len(raw) != expected['bytes'] or sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('Working source differs from pinned publication: ' + name)
    return descriptor


def prepare(root=ROOT, output=None, *, freeze=False, target=None, terra_reviewed_luna=False):
    root = Path(root)
    output = Path(output or root / '.build/data-release').resolve()
    output.mkdir(parents=True, exist_ok=True)
    if terra_reviewed_luna and not freeze:
        raise ValueError('Terra-reviewed Luna publication requires --freeze')
    if freeze:
        # Archive committed code and freeze both live stores under their shared
        # lock. Ingestion resumes immediately; build/check run on the copy.
        from .catalogue import source_lock
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        archive = subprocess.check_output(['git', 'archive', commit], cwd=root)
        with tempfile.TemporaryDirectory(prefix='atlas-publication-') as temporary:
            checkout = Path(temporary)
            with tarfile.open(fileobj=io.BytesIO(archive)) as source:
                source.extractall(checkout, filter='data')
            with source_lock(root / 'atlas/catalogue.json', wait=True):
                if terra_reviewed_luna:
                    from .catalogue import write_json
                    from .publication_filter import reviewed_luna_snapshot
                    raw = {name: (root / 'atlas' / name).read_bytes() for name in SOURCES}
                    review_bytes = (root / 'atlas/extraction_reviews.json').read_bytes()
                    catalogue, literature, report = reviewed_luna_snapshot(
                        json.loads(raw['catalogue.json']), json.loads(raw['literature_links.json']),
                        json.loads(review_bytes))
                    write_json(checkout / 'atlas/catalogue.json', catalogue)
                    write_json(checkout / 'atlas/literature_links.json', literature)
                    report['input_sha256'] = {name: sha256(value).hexdigest() for name, value in raw.items()}
                    report['review_registry_sha256'] = sha256(review_bytes).hexdigest()
                    write_json(output / 'review-selection.json', report)
                else:
                    for name in SOURCES:
                        shutil.copyfile(root / 'atlas' / name, checkout / 'atlas' / name)
            import sys
            subprocess.run(['make', 'build', 'PYTHON=' + sys.executable], cwd=checkout, check=True)
            subprocess.run(['make', 'check', 'PYTHON=' + sys.executable], cwd=checkout, check=True)
            return prepare(checkout, output, target=commit)
    catalogue = (root / 'atlas/catalogue.json').read_bytes()
    if (root / 'website/catalogue.json').read_bytes() != catalogue:
        raise ValueError('Build is stale. Use prepare --freeze while ingestion is running.')
    literature = (root / 'atlas/literature_links.json').read_bytes()
    from .build import VERSION
    tag = 'atlas-' + sha256(catalogue).hexdigest()[:12] + '-' + sha256(literature).hexdigest()[:8] + '-' + VERSION
    base = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag + '/'
    descriptor = {'schema_version': 'atlas-data-snapshot-1', 'repository': REPOSITORY,
                  'tag': tag, 'target': target, 'sources': {},
                  'downloads': {key: base + value for key, value in DOWNLOAD_FILES.items()}}
    for name, raw in [('catalogue.json', catalogue), ('literature_links.json', literature)]:
        compressed = gzip.compress(raw, mtime=0)
        (output / (name + '.gz')).write_bytes(compressed)
        descriptor['sources'][name] = {'url': base + name + '.gz', 'bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                                       'compressedBytes': len(compressed), 'compressedSha256': sha256(compressed).hexdigest()}
    for filename in DOWNLOAD_FILES.values():
        if filename == 'catalogue.json.gz':
            continue
        raw = (root / 'website/downloads' / filename.removesuffix('.gz')).read_bytes()
        (output / filename).write_bytes(gzip.compress(raw, mtime=0))
    data = json.loads(catalogue)
    descriptor['counts'] = {'papers': len(data['papers']), 'entries': len(data['entries'])}
    descriptor['assets'] = {name: {'bytes': (output / name).stat().st_size, 'sha256': sha256((output / name).read_bytes()).hexdigest()} for name in sorted({*DOWNLOAD_FILES.values(), *(name + '.gz' for name in SOURCES)})}
    (output / 'snapshot.json').write_text(json.dumps(descriptor, indent=2) + '\n')
    return descriptor


def upload(output, *, root=ROOT):
    output = Path(output).resolve()
    data = json.loads((output / 'snapshot.json').read_text())
    tag = data['tag']
    command = ['gh', 'release']
    result = subprocess.run([*command, 'view', tag, '--repo', REPOSITORY, '--json', 'isDraft,assets'], capture_output=True, text=True)
    expected_assets = {*DOWNLOAD_FILES.values(), *(name + '.gz' for name in SOURCES)}
    if set(data['assets']) != expected_assets:
        raise ValueError('Unexpected prepared asset names')
    assets = [output / name for name in sorted(expected_assets)] + [output / 'snapshot.json']
    for asset in assets:
        if asset.suffix == '.gz':
            expected = data['assets'][asset.name]
            if asset.stat().st_size != expected['bytes'] or sha256(asset.read_bytes()).hexdigest() != expected['sha256']:
                raise ValueError('Prepared asset was changed: ' + asset.name)
    if result.returncode:
        if 'release not found' not in result.stderr.lower() and '404' not in result.stderr:
            raise RuntimeError(result.stderr.strip() or 'Could not inspect data release')
        notes = output / 'release-notes.txt'
        notes.write_text(f"Complete gauge–matter catalogue: {data['counts']['entries']:,} entries and {data['counts']['papers']:,} paper records.\n\nJSON, CSV and SQLite downloads are gzip-compressed. Source and asset hashes and immutable download URLs are recorded in snapshot.json.\n")
        create = [*command, 'create', tag, '--repo', REPOSITORY, '--draft', '--title', 'BSM Atlas data · ' + tag,
                  '--notes-file', str(notes), *map(str, assets)]
        if data.get('target'):
            create += ['--target', data['target']]
        subprocess.run(create, check=True)
    else:
        existing = json.loads(result.stdout)
        sizes = {asset['name']: asset['size'] for asset in existing['assets']}
        if not existing['isDraft']:
            published = subprocess.check_output([*command, 'download', tag, '--repo', REPOSITORY,
                                                 '--pattern', 'snapshot.json', '--output', '-'], text=True)
            published = json.loads(published)
            if any(published['sources'][name]['sha256'] != data['sources'][name]['sha256'] for name in SOURCES):
                raise ValueError('Existing published snapshot has different source data')
            if published['downloads'] != data['downloads']:
                raise ValueError('Existing published snapshot has different download URLs')
            if any(sizes.get(name) != item['bytes'] for name, item in published['assets'].items()):
                raise ValueError('Published snapshot is incomplete; refusing to change it')
            # Reuse the published bytes and checksums across Python/SQLite
            # versions instead of replacing an immutable release in place.
            data = published
        else:
            for asset in assets:
                if asset.name in sizes and sizes[asset.name] != asset.stat().st_size:
                    raise ValueError('Existing draft asset differs; use its original prepared build: ' + asset.name)
            missing = [str(asset) for asset in assets if asset.name not in sizes]
            if missing:
                subprocess.run([*command, 'upload', tag, '--repo', REPOSITORY, *missing], check=True)
    state = json.loads(subprocess.check_output([*command, 'view', tag, '--repo', REPOSITORY, '--json', 'isDraft,assets'], text=True))
    sizes = {asset['name']: asset['size'] for asset in state['assets']}
    if any(sizes.get(name) != item['bytes'] for name, item in data['assets'].items()):
        raise ValueError('Release upload is incomplete; draft kept for resume')
    if state['isDraft']:
        subprocess.run([*command, 'edit', tag, '--repo', REPOSITORY, '--draft=false'], check=True)
    target = Path(root) / 'atlas/snapshot.json'
    from .catalogue import write_json
    write_json(target, data)
    return data
