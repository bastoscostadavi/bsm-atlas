"""The Pages artifact excludes bulk files and must match the pinned source."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from scripts.package_site import package, FILES
from bsm_atlas.snapshot import REPOSITORY


class PackageTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'atlas').mkdir();(root / 'website/data').mkdir(parents=True);(root / 'website/vendor').mkdir()
        raw = b'{"schema_version":"bsm-atlas-1","papers":[],"entries":[]}'
        metadata = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'compressedBytes': 1,
                    'compressedSha256': '0' * 64, 'url': 'https://github.com/' + REPOSITORY + '/releases/download/fixture/source.gz'}
        for name in ['catalogue.json', 'literature_links.json']:
            (root / 'atlas' / name).write_bytes(raw)
        descriptor = {'schema_version': 'atlas-data-snapshot-1', 'repository': REPOSITORY,
                      'tag': 'fixture', 'sources': {name: metadata for name in ['catalogue.json', 'literature_links.json']}}
        (root / 'atlas/snapshot.json').write_text(json.dumps(descriptor))
        for name in FILES:
            (root / 'website' / name).write_text('runtime asset')
        (root / 'website/atlas-bootstrap.js').write_text('window.ATLAS_MANIFEST_URL = "data/manifest-fixture.json";')
        (root / 'website/data/manifest-fixture.json').write_text(json.dumps({'sourceSha256': metadata['sha256']}))
        (root / 'website/vendor/library.js').write_text('vendored code')
        for name in ['catalogue.json', 'field-catalogue.json', 'field-catalogue-data.js', 'problem-data.js', 'mechanism-data.js']:
            (root / 'website' / name).write_text('bulk local research export')
        (root / 'website/downloads').mkdir();(root / 'website/downloads/catalogue.sqlite').write_text('bulk database')

    def test_only_runtime_assets_and_chunks_are_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);self.fixture(root);output = package(root)
            self.assertTrue((output / 'data/manifest-fixture.json').exists())
            self.assertTrue((output / 'vendor/library.js').exists())
            self.assertFalse((output / 'downloads').exists())
            self.assertFalse((output / 'catalogue.json').exists())
            self.assertFalse((output / 'field-catalogue-data.js').exists())
            self.assertFalse((output / 'problem-data.js').exists())

    def test_a_different_snapshot_cannot_be_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);self.fixture(root)
            (root / 'website/data/manifest-fixture.json').write_text(json.dumps({'sourceSha256': '1' * 64}))
            with self.assertRaisesRegex(ValueError, 'does not match pinned'):
                package(root)
