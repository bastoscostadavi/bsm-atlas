"""Both branches are projections of the same complete catalogue, not new models."""
from contextlib import closing
from copy import deepcopy
import csv
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parent.parent
from bsm_atlas.nonabelian_core import algebra_key, full_algebra_key
from bsm_atlas.core_projection import algebra_sort_key, attach_layers
from bsm_atlas.presentation import simple_algebra_dimension

DATA = json.loads((ROOT / 'website/field-catalogue.json').read_text())
ENTRIES = {entry['id']: entry for entry in DATA['entries']}
FULL = {group['id']: group for group in DATA['fullAlgebras']}
CORES = {group['id']: group for group in DATA['cores']}


class AlgebraOrdering(unittest.TestCase):
    def test_dimensions_cover_every_simple_family(self):
        for family,rank,dimension in [('A',1,3),('A',2,8),('A',9,99),('A',10,120),
                                      ('B',3,21),('C',2,10),('C',4,36),('D',5,45),
                                      ('E',6,78),('E',7,133),('E',8,248),('F',4,52),('G',2,14)]:
            with self.subTest(family=family,rank=rank):
                self.assertEqual(simple_algebra_dimension(family,rank),dimension)

    def test_rank_dimension_cartan_and_abelian_ties(self):
        # Expected order is mathematical, independent of display labels or IDs.
        types=[[],[('U1',1)],[('U1',1)]*2,
               [('A',2)],[('A',2),('A',1)],
               [('A',2),('A',1),('U1',1)],
               [('A',2),('A',1),('U1',1),('U1',1)],
               [('B',3)],[('C',3)],
               [('A',2),('A',1),('A',1)],
               [('A',2),('A',2)],[('A',3),('A',1)],[('A',4)],
               [('A',3),('A',1),('A',1)],[('A',5)],[('D',5)],[('E',6)]]
        groups=[{'id':str(100-i),'canonical':{'gauge_factors':[
            {'family':family,'rank':rank} for family,rank in factors]}}
            for i,factors in enumerate(types)]
        before=deepcopy(groups)
        self.assertEqual(sorted(reversed(groups),key=algebra_sort_key),before)
        # Source factor permutations cannot alter browsing order or mutate data.
        for group in groups:
            permuted=deepcopy(group)
            permuted['canonical']['gauge_factors'].reverse()
            self.assertEqual(algebra_sort_key(group),algebra_sort_key(permuted))
        self.assertEqual(groups,before)

    def test_all_derived_layers_share_the_semisimple_order(self):
        labels=['su(3)','su(3) ⊕ su(2)','su(3) ⊕ su(2) ⊕ su(2)',
                'su(3) ⊕ su(3)','su(4) ⊕ su(2)','su(5)',
                'su(4) ⊕ su(2) ⊕ su(2)','so(10)','e6']
        algebras={group['algebra']:group for group in DATA['semisimpleAlgebras']}
        entries=[deepcopy(ENTRIES[algebras[label]['entryIds'][0]]) for label in reversed(labels)]
        expected_ids=[algebras[label]['id'] for label in labels]
        for groups in attach_layers(entries):
            self.assertEqual([group.get('semisimpleId',group['id']) for group in groups],expected_ids)
        for entry in entries:
            original=ENTRIES[entry['id']]
            for key in ['specification','identity','coreId','semisimpleId','fullAlgebraId']:
                self.assertEqual(entry[key],original[key])


class AlgebraSquare(unittest.TestCase):
    def test_full_algebra_keys_forget_matter_names_charges_and_factor_order(self):
        source = deepcopy(ENTRIES['two-higgs-doublets']['specification'])
        expected = full_algebra_key(source)
        source['matter'] = []
        source['gauge_factors'].reverse()
        for factor in source['gauge_factors']:
            factor['id'] = 'source-name-' + factor['id']
        self.assertEqual(full_algebra_key(source), expected)
        source['gauge_factors'].append({'id': 'extra', 'family': 'U1', 'rank': 1})
        extended = full_algebra_key(source)
        self.assertNotEqual(extended['id'], expected['id'])
        self.assertEqual(extended['semisimpleId'], expected['semisimpleId'])
        source['gauge_factors'][-1]['rank'] = 2
        with self.assertRaises(ValueError):
            full_algebra_key(source)

    def test_full_algebra_groups_partition_all_entries(self):
        self.assertEqual(DATA['counts']['fullAlgebras'], len(FULL))
        self.assertGreaterEqual(len(FULL), 14)
        seen = []
        for group in FULL.values():
            with self.subTest(algebra=group['algebra']):
                self.assertNotIn('matter', group['canonical'])
                raw = json.dumps(group['canonical'], sort_keys=True, separators=(',', ':'))
                self.assertEqual(sha256(raw.encode()).hexdigest(), group['id'])
                simple = {'gauge_factors': [factor for factor in group['canonical']['gauge_factors']
                                            if factor['family'] != 'U1']}
                self.assertEqual(algebra_key(simple)['id'], group['semisimpleId'])
                self.assertEqual(sum(factor['type'] == 'U1' for factor in group['factors']),
                                 group['abelianRank'])
                for entry_id in group['entryIds']:
                    entry = ENTRIES[entry_id]
                    self.assertEqual(full_algebra_key(entry['specification'])['id'], group['id'])
                    self.assertEqual(entry['fullAlgebraId'], group['id'])
                    self.assertEqual(entry['semisimpleId'], group['semisimpleId'])
                    self.assertEqual(entry['abelianRank'], group['abelianRank'])
                self.assertEqual(set(group['coreIds']),
                                 {ENTRIES[key]['coreId'] for key in group['entryIds']})
                seen.extend(group['entryIds'])
        self.assertEqual(len(seen),len(ENTRIES))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), set(ENTRIES))

    def test_both_paths_recover_exactly_the_same_parent_entries(self):
        for simple in DATA['semisimpleAlgebras']:
            via_algebras = {key for group in FULL.values()
                            if group['semisimpleId'] == simple['id'] for key in group['entryIds']}
            via_matter = {key for group in CORES.values()
                          if group['semisimpleId'] == simple['id'] for key in group['entryIds']}
            self.assertEqual(via_algebras, via_matter)
            self.assertEqual(via_algebras, set(simple['entryIds']))
            self.assertEqual(set(simple['fullAlgebraIds']),
                             {ENTRIES[key]['fullAlgebraId'] for key in simple['entryIds']})
        for core in CORES.values():
            self.assertEqual(set(core['fullAlgebraIds']),
                             {ENTRIES[key]['fullAlgebraId'] for key in core['entryIds']})

    def test_full_algebra_does_not_merge_matter_or_symbolic_templates(self):
        fixed = ENTRIES['two-higgs-doublets']
        other = ENTRIES['nmssm-matter']
        family = ENTRIES['u1-smnur-all-sm-yukawas']
        self.assertEqual(fixed['fullAlgebraId'], other['fullAlgebraId'])
        self.assertNotEqual(fixed['coreId'], other['coreId'])
        self.assertNotEqual(fixed['identity']['fingerprint'], other['identity']['fingerprint'])
        self.assertEqual(fixed['semisimpleId'], family['semisimpleId'])
        self.assertNotEqual(fixed['fullAlgebraId'], family['fullAlgebraId'])
        self.assertEqual(family['abelianRank'], 2)
        self.assertGreaterEqual(len(ENTRIES),67)

    def test_zero_semisimple_part_is_a_valid_abelian_algebra(self):
        result = full_algebra_key({'gauge_factors': [{'family': 'U1', 'rank': 1}]})
        self.assertEqual(result['semisimpleId'], algebra_key({'gauge_factors': []})['id'])
        self.assertEqual(result['abelianRank'], 1)

    def test_csv_has_one_row_per_full_algebra(self):
        with (ROOT / 'website/downloads/full-gauge-algebras.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows),len(FULL))
        for row in rows:
            group = FULL[row['id']]
            self.assertEqual(json.loads(row['canonical_json']), group['canonical'])
            self.assertEqual(set(row['entry_ids'].split(';')), set(group['entryIds']))

    def test_sqlite_roundtrip_includes_both_branches(self):
        path = ROOT / 'website/downloads/field-catalogue.sqlite'
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(con.execute('SELECT count(*) FROM full_gauge_algebras').fetchone()[0],len(FULL))
            for entry in ENTRIES.values():
                row = con.execute('SELECT semisimple_id,core_id,full_algebra_id FROM entry_layers '
                                  'WHERE entry_id=?', (entry['id'],)).fetchone()
                self.assertEqual(row, (entry['semisimpleId'], entry['coreId'], entry['fullAlgebraId']))
            for group in FULL.values():
                row = con.execute('SELECT canonical_json,semisimple_id,abelian_rank '
                                  'FROM full_gauge_algebras WHERE full_algebra_id=?',
                                  (group['id'],)).fetchone()
                self.assertEqual(json.loads(row[0]), group['canonical'])
                self.assertEqual(row[1:], (group['semisimpleId'], group['abelianRank']))


if __name__ == '__main__':
    unittest.main()
