"""Check the published payload against the retrieved source, not inferred counts."""
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from export_relational import collect


class SnapshotTest(unittest.TestCase):
    def test_publication_matches_source(self):
        site = Path(__file__).resolve().parent
        source = site.parent / "atlas" / "atlas.sqlite"
        data = json.loads((site / "data.js").read_text(encoding="utf-8").removeprefix("window.ATLAS_DATA = ").strip().removesuffix(";"))
        with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            expected = collect(con)
        self.assertEqual(expected["tables"], data["relational"]["tables"])
        self.assertEqual(expected["userVersion"], data["relational"]["userVersion"])
        self.assertEqual(expected["validation"]["integrityCheck"], ["ok"])
        self.assertEqual(expected["validation"]["foreignKeyViolations"], [])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), data["sourceSnapshot"]["database_sha256"])
        for artifact in data["downloads"]:
            path = site / artifact["path"]
            self.assertEqual(path.stat().st_size, artifact["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])
        public_json = json.loads((site / "atlas-data.json").read_text(encoding="utf-8"))
        self.assertEqual(public_json["relational"], data["relational"])
        with sqlite3.connect((site / "downloads" / "atlas.sqlite").resolve().as_uri() + "?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            self.assertEqual(collect(con)["tables"], expected["tables"])
        canonical = lambda rs: sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rs)
        for sql_path in [source.with_suffix(".sql"), site / "downloads" / "atlas.sql"]:
            with sqlite3.connect(":memory:") as con:
                con.row_factory = sqlite3.Row
                con.executescript(sql_path.read_text(encoding="utf-8"))
                restored = collect(con)
                for name, table in expected["tables"].items():
                    self.assertEqual(canonical(restored["tables"][name]["rows"]), canonical(table["rows"]), str(sql_path) + ": " + name)


if __name__ == "__main__":
    unittest.main()
