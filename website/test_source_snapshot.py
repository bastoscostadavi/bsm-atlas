"""Keep the archival source and SQL restore checks without the retired UI."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parent.parent


class SourceSnapshot(unittest.TestCase):
    def test_frozen_followup_evidence_is_unchanged(self):
        manifest = json.loads((ROOT / 'atlas/reextraction/followup-20261016/frozen-files.json').read_text())
        for filename, digest in manifest['files'].items():
            self.assertEqual(sha256((ROOT / filename).read_bytes()).hexdigest(), digest, filename)

    def test_readonly_source_integrity_and_lossless_sql_restore(self):
        source = ROOT / 'atlas/atlas.sqlite'
        metadata = json.loads((ROOT / 'atlas/source_snapshot.json').read_text())
        self.assertEqual(sha256(source.read_bytes()).hexdigest(), metadata['database_sha256'])
        self.assertEqual(metadata['database_sha256'],
                         'd4dbf023b667fe810296c43c8f72e0d0b3f6559e66b344a2920c9e2e520e6c4c')
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as original, \
                closing(sqlite3.connect(':memory:')) as restored:
            self.assertEqual(original.execute('PRAGMA user_version').fetchone()[0], metadata['schema_user_version'])
            self.assertEqual(original.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
            self.assertEqual(original.execute('PRAGMA foreign_key_check').fetchall(), [])
            restored.executescript((ROOT / 'atlas/atlas.sql').read_text())
            tables = lambda con: dict(con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
            self.assertEqual(tables(original), tables(restored))
            for table in tables(original):
                quoted = '"' + table.replace('"', '""') + '"'
                rows = lambda con: sorted(con.execute('SELECT * FROM ' + quoted).fetchall(), key=repr)
                self.assertEqual(rows(original), rows(restored), table)


if __name__ == '__main__':
    unittest.main()
