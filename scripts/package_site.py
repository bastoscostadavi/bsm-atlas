#!/usr/bin/env python3
"""Package only runtime assets and static chunks, excluding bulk research exports."""
from pathlib import Path
import json
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.snapshot import verify

FILES = ['index.html', 'field-catalogue.css', 'atlas-bootstrap.js', 'atlas-store.js',
         'field-catalogue.js', 'field-matrix.js', 'representation-diagrams.js',
         'problem-explorer.js', 'connection-explorer.js', 'favicon.svg', 'favicon-dark.svg',
         'social-preview.svg', 'social-preview.png', 'entry.schema.json', 'catalogue.schema.json']


def package(root=ROOT, output=None):
    root = Path(root); verify(root)
    output = Path(output or root / '.build/site')
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in FILES:
        shutil.copyfile(root / 'website' / name, output / name)
    for name in ['data', 'vendor']:
        shutil.copytree(root / 'website' / name, output / name)
    boot = (output / 'atlas-bootstrap.js').read_text()
    manifest_path = json.loads(boot.split(' = ', 1)[1].strip().removesuffix(';'))
    manifest = json.loads((output / manifest_path).read_text())
    snapshot = json.loads((root / 'atlas/snapshot.json').read_text())
    if manifest['sourceSha256'] != snapshot['sources']['catalogue.json']['sha256']:
        raise ValueError('Public bundle does not match pinned source snapshot')
    size = sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    print(f'Public site: {size / 1024**2:.2f} MiB; complete downloads are release assets.')
    return output


if __name__ == '__main__':
    package()
