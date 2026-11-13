"""Whole-snapshot property round trips without repeated ingestion validation."""
from contextlib import closing
import csv
import json
from pathlib import Path
import sqlite3
import unittest

from bsm_atlas.anomalies import specification_hash
from bsm_atlas.properties import summary

ROOT = Path(__file__).resolve().parent.parent


class PropertyExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'website/field-catalogue.json').read_text())
        cls.entries = {entry['id']: entry for entry in cls.data['entries']}

    def test_every_entry_has_matching_provenance_and_status(self):
        for entry in self.entries.values():
            properties = entry['properties']
            self.assertEqual(properties['fingerprint'], entry['identity']['fingerprint'])
            self.assertEqual(properties['anomalies']['specification_sha256'], specification_hash(entry['specification']))
            self.assertFalse(properties['anomalies']['global']['complete'])
            for kind in ('total', 'physical'):
                count = properties['parameters'][kind]
                self.assertEqual(count['value'] is not None, count['status'] in {'computed', 'certified'})
        self.assertEqual(self.data['propertySummary'], summary(list(self.entries.values())))

    def test_sqlite_roundtrip_including_unknown_counts(self):
        path = ROOT / 'website/downloads/field-catalogue.sqlite'
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            rows = connection.execute('SELECT entry_id,fingerprint,properties_json FROM entry_properties').fetchall()
        self.assertEqual(len(rows), len(self.entries))
        for entry_id, fingerprint, properties in rows:
            self.assertEqual(fingerprint, self.entries[entry_id]['identity']['fingerprint'])
            self.assertEqual(json.loads(properties), self.entries[entry_id]['properties'])

    def test_csv_roundtrip_including_blank_unknown_counts(self):
        prior = csv.field_size_limit(16 * 1024 * 1024)
        self.addCleanup(csv.field_size_limit, prior)
        with (ROOT / 'website/downloads/field-catalogue.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), len(self.entries))
        for row in rows:
            properties = self.entries[row['entry_id']]['properties']
            self.assertEqual(json.loads(row['properties_json']), properties)
            self.assertEqual(row['perturbative_anomalies'], properties['anomalies']['perturbative']['status'])
            self.assertEqual(row['global_cover_checks'], properties['anomalies']['global']['status'])
            for column, kind in [('total_parameters', 'total'), ('physical_parameters', 'physical')]:
                value = properties['parameters'][kind]['value']
                self.assertEqual(row[column], '' if value is None else str(value))


if __name__ == '__main__':
    unittest.main()
