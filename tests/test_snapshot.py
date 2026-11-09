"""Pinned downloads are checked before restoring, and never overwrite ingestion."""
from copy import deepcopy
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bsm_atlas.snapshot import restore, verify, REPOSITORY


class SnapshotTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'atlas').mkdir()
        records = {'catalogue.json': {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []},
                   'literature_links.json': {'schema_version': 'atlas-literature-links-1', 'papers': {}}}
        descriptor = {'schema_version': 'atlas-data-snapshot-1', 'repository': REPOSITORY,
                      'tag': 'fixture', 'sources': {}}
        compressed = {}
        for name, value in records.items():
            raw = json.dumps(value).encode(); zipped = gzip.compress(raw, mtime=0); compressed[name] = zipped
            descriptor['sources'][name] = {'url': 'https://github.com/' + REPOSITORY + '/releases/download/fixture/' + name + '.gz',
                'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'compressedBytes': len(zipped), 'compressedSha256': sha256(zipped).hexdigest()}
        (root / 'atlas/snapshot.json').write_text(json.dumps(descriptor))
        return descriptor, compressed

    def response(self, compressed):
        return lambda request, **_kwargs: io.BytesIO(compressed[request.full_url.split('/')[-1].removesuffix('.gz')])

    def test_restore_verifies_both_sources_and_preserves_existing_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); _, compressed = self.fixture(root)
            with patch('bsm_atlas.snapshot.urllib.request.urlopen', side_effect=self.response(compressed)) as fetch:
                restore(root); self.assertEqual(fetch.call_count, 2)
                self.assertEqual(verify(root)['tag'], 'fixture')
                current = root / 'atlas/catalogue.json'; current.write_text('new ingestion data')
                restore(root); self.assertEqual(fetch.call_count, 2)
                self.assertEqual(current.read_text(), 'new ingestion data')
                with self.assertRaisesRegex(ValueError, 'differs from pinned'):
                    verify(root)

    def test_wrong_compressed_bytes_never_become_a_catalogue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); _, compressed = self.fixture(root)
            compressed['catalogue.json'] = b'corrupt payload'
            with patch('bsm_atlas.snapshot.urllib.request.urlopen', side_effect=self.response(compressed)):
                with self.assertRaisesRegex(ValueError, 'compressed hash/length'):
                    restore(root)
            self.assertFalse((root / 'atlas/catalogue.json').exists())

    def test_declared_expansion_bound_and_raw_hash_are_enforced(self):
        for change in ['length', 'hash']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); descriptor, compressed = self.fixture(root)
                source = descriptor['sources']['catalogue.json']
                if change == 'length':
                    source['bytes'] -= 1
                else:
                    source['sha256'] = '0' * 64
                (root / 'atlas/snapshot.json').write_text(json.dumps(descriptor))
                with patch('bsm_atlas.snapshot.urllib.request.urlopen', side_effect=self.response(compressed)):
                    with self.assertRaises(ValueError):
                        restore(root)
                self.assertFalse((root / 'atlas/catalogue.json').exists())

    def test_unexpected_download_origin_is_rejected_before_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); descriptor, compressed = self.fixture(root)
            descriptor['sources']['catalogue.json']['url'] = 'https://example.com/catalogue.json.gz'
            (root / 'atlas/snapshot.json').write_text(json.dumps(descriptor))
            with patch('bsm_atlas.snapshot.urllib.request.urlopen') as fetch:
                with self.assertRaisesRegex(ValueError, 'origin'):
                    restore(root)
                fetch.assert_not_called()

class SnapshotPublicationTests(unittest.TestCase):
    def prepare_fixture(self, root):
        from bsm_atlas.snapshot import prepare, DOWNLOAD_FILES
        (root / 'atlas').mkdir();(root / 'website/downloads').mkdir(parents=True)
        raw = json.dumps({'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []}).encode()
        (root / 'atlas/catalogue.json').write_bytes(raw);(root / 'website/catalogue.json').write_bytes(raw)
        (root / 'atlas/literature_links.json').write_text(json.dumps({'schema_version': 'atlas-literature-links-1', 'papers': {}}))
        for filename in DOWNLOAD_FILES.values():
            if filename != 'catalogue.json.gz':
                (root / 'website/downloads' / filename.removesuffix('.gz')).write_bytes(b'validated export fixture')
        output = root / 'prepared';data = prepare(root, output)
        state = {'isDraft': True, 'assets': [{'name': path.name, 'size': path.stat().st_size}
                                           for path in output.iterdir() if path.suffix in {'.gz', '.json'}]}
        return output, data, state

    def test_draft_is_published_only_after_all_assets_are_uploaded(self):
        from bsm_atlas.snapshot import upload
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);output, data, state = self.prepare_fixture(root)
            with patch('bsm_atlas.snapshot.subprocess.run', return_value=CompletedProcess([], 1, '', 'release not found')) as run, \
                 patch('bsm_atlas.snapshot.subprocess.check_output', return_value=json.dumps(state)):
                upload(output, root=root)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn('--draft', commands[1]);self.assertIn('--draft=false', commands[-1])
            self.assertFalse(any('--clobber' in command for command in commands))
            self.assertEqual(json.loads((root / 'atlas/snapshot.json').read_text())['tag'], data['tag'])
            self.assertTrue((root / 'atlas/catalogue.json').exists())

    def test_incomplete_upload_stays_draft_and_does_not_update_descriptor(self):
        from bsm_atlas.snapshot import upload
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);output, data, state = self.prepare_fixture(root);state['assets'].pop(0)
            with patch('bsm_atlas.snapshot.subprocess.run', return_value=CompletedProcess([], 1, '', 'release not found')) as run, \
                 patch('bsm_atlas.snapshot.subprocess.check_output', return_value=json.dumps(state)):
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    upload(output, root=root)
            self.assertFalse((root / 'atlas/snapshot.json').exists())
            self.assertFalse(any('--draft=false' in call.args[0] for call in run.call_args_list))

    def test_published_release_reuses_its_existing_descriptor(self):
        from bsm_atlas.snapshot import upload
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);output, data, state = self.prepare_fixture(root);state['isDraft'] = False
            published = deepcopy(data);published['sources']['catalogue.json']['compressedSha256'] = '1' * 64
            with patch('bsm_atlas.snapshot.subprocess.run', return_value=CompletedProcess([], 0, json.dumps(state), '')) as run, \
                 patch('bsm_atlas.snapshot.subprocess.check_output', side_effect=[json.dumps(published), json.dumps(state)]):
                result = upload(output, root=root)
            self.assertEqual(result, published)
            self.assertEqual(len(run.call_args_list), 1)
            self.assertEqual(json.loads((root / 'atlas/snapshot.json').read_text()), published)
