"""Complete-only harvest and typed-family regressions; no source PDF cache needed.

These tests verify persisted acceptance and mathematical projections, not the
scientific correctness of papers. Legacy provenance rows hidden by an explicit
baseline or excluded as dependent coordinates are not independent matrix rows.
"""
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import unittest
from unittest.mock import patch

from build_field_catalogue import ROOT, display_rep
from catalogue_identity import IncompleteContent, normalize_spec
from charge_expressions import parse_charge
from harvest_reviews import (
    apply_harvest_reviews, input_identity, load_harvest_reviews,
    normalize_input, publish_complete_entries,
    normalize_source_input, source_input_identity,
)
from nonabelian_core import restrict_nonabelian
from parameterized_entry import specialize
from scalar_conventions import is_scalar

DATA = json.loads((ROOT / 'website/field-catalogue.json').read_text())
ENTRIES = {entry['id']: entry for entry in DATA['entries']}
MANIFEST = ROOT / 'atlas/reextraction/accepted-harvest.json'
DATABASE = ROOT / 'website/downloads/field-catalogue.sqlite'


def primary(entry):
    return next(regime for variant in entry['variants']
                for regime in variant['regimes']
                if regime['id'] == entry['primaryRegime'])


def public_rows(entry):
    for variant in entry['variants']:
        for regime in variant['regimes']:
            for field in regime['fields']:
                if field['excludedCoordinate'] or regime['baseline'] and field.get('inherited'):
                    continue
                yield regime, field


def vector_family(weight):
    return {
        'schema_version': 'field-content-3', 'inventory_complete': True,
        'parameters': {'n': {'domain': 'integer'}}, 'constraints': ['n != 0'],
        'gauge_factors': [
            {'id': 'g', 'family': 'A', 'rank': 2},
            {'id': 'x', 'family': 'U1', 'rank': 1},
        ],
        'matter': [{
            'label': 'fixture vector',
            'lorentz': {'dimension': 4, 'scheme': 'jL_jR',
                        'irreps': [['1/2', '1/2']]},
            'reality': 'complex', 'copies': 1,
            'gauge_representations': {'g': {'dynkin': weight}, 'x': {'charge': 'n'}},
        }],
    }


class HarvestPublication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = load_harvest_reviews(ROOT)

    def test_acceptance_pins_normalization_and_ordered_source_provenance(self):
        self.assertEqual(len(self.reviews), 48)
        self.assertEqual(len({review['decision']['entry'] for review in self.reviews}), 48)
        for review in self.reviews:
            decision, source, normalized, evidence = (
                review[key] for key in ['decision', 'source', 'normalized', 'evidence'])
            with self.subTest(entry=decision['entry']):
                for pin in decision['files'].values():
                    path = (ROOT / pin['path']).resolve()
                    self.assertTrue(path.is_relative_to(
                        (ROOT / 'atlas/reextraction/closure-20261019').resolve()))
                    self.assertEqual(sha256(path.read_bytes()).hexdigest(), pin['sha256'])
                self.assertEqual(normalize_source_input(source), normalized)
                self.assertEqual(normalize_source_input(normalized), normalized)
                self.assertEqual(source_input_identity(normalized)['fingerprint'],
                                 decision['fingerprint'])
                self.assertTrue(normalized['inventory_complete'])
                self.assertEqual(evidence['target_entry_id'], decision['entry'])
                self.assertEqual(evidence['paper_id'], decision['paper'])
                self.assertEqual(evidence['arxiv_version'], decision['arxiv'])
                self.assertIn(decision['paper'], normalized['paper_ids'])
                mapping = evidence['source_field_mapping']
                self.assertEqual([row['candidate_label'] for row in mapping],
                                 [row['label'] for row in source['matter']])
                claim_ids = {claim['id'] for claim in evidence['claims']}
                for row in mapping:
                    self.assertTrue(row['mapping_basis'])
                    self.assertTrue(row['claim_ids'])
                    self.assertLessEqual(set(row['claim_ids']), claim_ids)

    def test_ci_never_needs_ignored_pdfs_or_mutable_research_ledgers(self):
        original_bytes, original_text = Path.read_bytes, Path.read_text

        def guarded_bytes(path, *args, **kwargs):
            self.assertNotEqual(path.suffix, '.pdf')
            return original_bytes(path, *args, **kwargs)

        def guarded_text(path, *args, **kwargs):
            self.assertNotIn(path.name, {
                'queue.json', 'reviews.json', 'integration-manifest.json',
                'corpus-run-ledger.json',
            })
            return original_text(path, *args, **kwargs)

        with patch.object(Path, 'read_bytes', guarded_bytes), \
                patch.object(Path, 'read_text', guarded_text):
            self.assertEqual(len(load_harvest_reviews(ROOT)), 48)

    def test_new_symbolic_reviews_can_pin_the_standardized_identity(self):
        manifest = json.loads(MANIFEST.read_text())
        by_id = {review['decision']['entry']: review for review in self.reviews}
        changed = 0
        for decision in manifest['reviews']:
            normalized = by_id[decision['entry']]['normalized']
            if normalized['schema_version'] == 'field-content-3':
                decision['fingerprint'] = input_identity(normalized)['fingerprint']
                changed += 1
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            return json.dumps(manifest) if path == MANIFEST else original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_text):
            self.assertEqual(len(load_harvest_reviews(ROOT)), 48)
        self.assertEqual(changed, 2)

    def test_publication_has_only_complete_fixed_algebras_and_known_matrix_rows(self):
        self.assertEqual(len(DATA['entries']), 67)
        self.assertEqual(DATA['referenceRecords'], [])
        self.assertEqual(DATA['counts']['referenceRecords'], 0)
        self.assertNotIn('exclusions', DATA)
        self.assertNotIn('pendingEntries', DATA)
        for algebra in DATA['semisimpleAlgebras']:
            self.assertNotEqual(algebra['algebra'], 'su(2)')
            self.assertEqual(algebra['pendingEntryIds'], [])
            self.assertEqual(set(algebra['entryIds']), set(algebra['readyEntryIds']))
        for entry in DATA['entries']:
            with self.subTest(entry=entry['id']):
                self.assertEqual(entry['publicationStatus'], 'ready')
                self.assertEqual(entry['coreStatus']['status'], 'resolved')
                self.assertEqual(entry['semisimpleStatus']['status'], 'resolved')
                self.assertIsNotNone(entry['coreId'])
                self.assertIsNotNone(entry['semisimpleId'])
                spec = entry['identity']['input']
                self.assertTrue(spec['inventory_complete'])
                for row in spec['matter']:
                    self.assertIs(type(row['copies']), int)
                    self.assertGreater(row['copies'], 0)
                    self.assertEqual(set(row['gauge_representations']),
                                     {factor['id'] for factor in spec['gauge_factors']})
                for regime, field in public_rows(entry):
                    self.assertTrue(field['notationComplete'])
                    for lorentz in field['lorentz']:
                        self.assertEqual(lorentz['status'], 'resolved')
                        self.assertGreater(lorentz['copies'], 0)
                        self.assertEqual(len(lorentz['gaugeComponents']), len(regime['factors']))
                        for factor, component in zip(regime['factors'],
                                                     lorentz['gaugeComponents']):
                            self.assertNotIn('?', str(component['value']))
                            self.assertIsNotNone(component['value'])
                            if factor['type'] != 'U1':
                                self.assertEqual(len(component['dynkin']), factor['rank'])

    def test_all_public_identities_are_normalized_and_unique(self):
        fingerprints = []
        for entry in DATA['entries']:
            identity = entry['identity']
            with self.subTest(entry=entry['id']):
                self.assertEqual(identity['input'], normalize_input(identity['input']))
                calculated = input_identity(identity['input'])
                self.assertEqual(calculated['fingerprint'], identity['fingerprint'])
                self.assertEqual(json.loads(calculated['canonical_json']), identity['canonical'])
                fingerprints.append(identity['fingerprint'])
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        self.assertEqual(sum(entry['identity']['input']['schema_version'] == 'field-content-3'
                             for entry in DATA['entries']), 2)

    def test_new_unreviewed_ready_entry_is_blocked(self):
        fixture = deepcopy(ENTRIES['real-singlet-z2'])
        fixture.update(id='unit-test-unreviewed-target', reextractions=[])
        with self.assertRaisesRegex(ValueError, 'source-reviewed acceptance'):
            publish_complete_entries([fixture])

    def test_pending_entry_is_not_published_or_saved_as_an_exclusion(self):
        complete = deepcopy(ENTRIES['real-singlet-z2'])
        pending = {'id': 'unit-test-pending', 'publicationStatus': 'pending',
                   'identity': {'fingerprint': None}}
        unchanged = deepcopy(pending)
        output = publish_complete_entries([complete, pending])
        self.assertIsInstance(output, list)
        self.assertEqual([entry['id'] for entry in output], ['real-singlet-z2'])
        self.assertEqual(pending, unchanged)

    def test_retained_pin_does_not_authorize_a_changed_entry(self):
        fixture = deepcopy(ENTRIES['real-singlet-z2'])
        fixture['reextractions'] = []
        old = fixture['identity']['fingerprint']
        fixture['identity']['input']['matter'][-1]['copies'] += 1
        fixture['identity']['fingerprint'] = input_identity(
            fixture['identity']['input'])['fingerprint']
        with self.assertRaisesRegex(ValueError, 'source-reviewed acceptance'):
            publish_complete_entries([fixture], {'real-singlet-z2': old})

    def test_publication_gate_rejects_unnormalized_retained_input(self):
        fixture = deepcopy(ENTRIES['real-singlet-z2'])
        fixture['reextractions'] = []
        for row in fixture['identity']['input']['matter']:
            for factor in fixture['identity']['input']['gauge_factors']:
                if factor['family'] == 'U1':
                    rep = row['gauge_representations'][factor['id']]
                    rep['charge'] = str(2 * int(rep['charge']))
        self.assertNotEqual(fixture['identity']['input'],
                            normalize_input(fixture['identity']['input']))
        with self.assertRaisesRegex(ValueError, '[Nn]ormaliz'):
            publish_complete_entries(
                [fixture], {'real-singlet-z2': fixture['identity']['fingerprint']})

    def load_mutated_evidence(self, mutate):
        manifest = json.loads(MANIFEST.read_text())
        pin = manifest['reviews'][0]['files']['evidence']
        target = (ROOT / pin['path']).resolve()
        payload = json.loads(target.read_text())
        mutate(payload)
        replacement = json.dumps(payload).encode()
        pin['sha256'] = sha256(replacement).hexdigest()
        original_bytes, original_text = Path.read_bytes, Path.read_text

        def read_bytes(path, *args, **kwargs):
            return replacement if path.resolve() == target else original_bytes(path, *args, **kwargs)

        def read_text(path, *args, **kwargs):
            return json.dumps(manifest) if path == MANIFEST else original_text(path, *args, **kwargs)

        with patch.object(Path, 'read_bytes', read_bytes), \
                patch.object(Path, 'read_text', read_text):
            return load_harvest_reviews(ROOT)

    def test_reordered_source_row_provenance_is_rejected_even_when_repinned(self):
        with self.assertRaisesRegex(ValueError, 'ordered provenance'):
            self.load_mutated_evidence(
                lambda evidence: evidence['source_field_mapping'].reverse())

    def test_incomplete_source_verdict_is_rejected_even_when_repinned(self):
        def incomplete(evidence):
            evidence['decision'] = {
                'inventory_complete': True, 'not_extracted': ['missing field count'],
                'not_specified_by_source': [],
            }
        with self.assertRaisesRegex(ValueError, 'Only complete'):
            self.load_mutated_evidence(incomplete)

    def test_missing_claim_mapping_is_rejected_even_when_repinned(self):
        def missing(evidence):
            evidence['source_field_mapping'][0]['claim_ids'] = ['unit-test-nonexistent-claim']
        with self.assertRaisesRegex(ValueError, 'row evidence'):
            self.load_mutated_evidence(missing)

    def test_source_path_and_hash_guards(self):
        original = Path.read_text
        for mutation, expected in [
            (lambda manifest: manifest['reviews'][0]['files']['source'].update(
                path='atlas/field_content_curations.json'), 'outside accepted directory'),
            (lambda manifest: manifest['reviews'][0]['files']['source'].update(
                sha256='0' * 64), 'evidence changed'),
            (lambda manifest: manifest.update(
                evidence_directories=['../closure-20261019']), 'explicitly named'),
        ]:
            with self.subTest(expected=expected):
                def changed(path, *args, **kwargs):
                    raw = original(path, *args, **kwargs)
                    if path == MANIFEST:
                        manifest = json.loads(raw)
                        mutation(manifest)
                        return json.dumps(manifest)
                    return raw
                with patch.object(Path, 'read_text', changed), \
                        self.assertRaisesRegex(ValueError, expected):
                    load_harvest_reviews(ROOT)

    def test_new_paper_and_entry_intake_does_not_fabricate_legacy_ids(self):
        review = deepcopy(self.reviews[0])
        decision = review['decision']
        decision.update(entry='unit-test-new-entry', paper='TEST-PAPER',
                        arxiv='unit-test-version-v1', regime=None,
                        paper_metadata={'title': 'Intake fixture, not a source paper',
                                        'authors': 'Unit test',
                                        'arxiv': 'unit-test-version-v1'})
        for spec in [review['source'], review['normalized']]:
            spec['paper_ids'] = ['TEST-PAPER']
        review['evidence'].update(target_entry_id=decision['entry'],
                                  paper_id=decision['paper'],
                                  arxiv_version=decision['arxiv'])
        for mapping in review['evidence']['source_field_mapping']:
            mapping['source_field_ids'] = []
            mapping['source_model_id'] = None
            mapping['source_regime_id'] = None
            mapping['mapping_basis'] = 'source_defined_new_inventory_fixture'
        entries, papers = [], []
        apply_harvest_reviews(entries, papers, [review], display_rep)
        published = publish_complete_entries(entries)
        self.assertEqual(len(published), 1)
        self.assertEqual(papers[0]['id'], 'TEST-PAPER')
        self.assertEqual(papers[0]['arxiv'], decision['arxiv'])
        entry = published[0]
        self.assertEqual(entry['id'], 'unit-test-new-entry')
        self.assertGreaterEqual(entry['primaryRegime'], 10 ** 9)
        self.assertEqual(entry['paperIds'], ['TEST-PAPER'])
        self.assertTrue(entry['primaryVariant'].startswith('harvest:'))
        for field in primary(entry)['fields']:
            self.assertIsNone(field['sourceFieldId'])
            self.assertEqual(field['sourceFieldIds'], [])

    def test_new_paper_requires_bibliographic_metadata(self):
        review = deepcopy(self.reviews[0])
        review['decision'].update(paper='TEST-MISSING-METADATA')
        review['decision'].pop('paper_metadata', None)
        with self.assertRaisesRegex(ValueError, 'bibliographic metadata'):
            apply_harvest_reviews([], [], [review], display_rep)

    def test_nmssm_exact_dedup_keeps_the_p28_association(self):
        self.assertNotIn('lns-single-singlet-quarks', ENTRIES)
        entry = ENTRIES['nmssm-matter']
        self.assertIn('lns-single-singlet-quarks',
                      {alias['id'] for alias in entry['aliases']})
        self.assertIn('P05', entry['paperIds'])
        self.assertIn('P28', entry['paperIds'])
        paper = next(paper for paper in DATA['papers'] if paper['id'] == 'P28')
        self.assertIn('nmssm-matter', paper['entryIds'])
        accepted = next(review for review in self.reviews
                        if review['decision']['entry'] == 'lns-single-singlet-quarks')
        self.assertEqual(accepted['decision']['fingerprint'],
                         entry['identity']['fingerprint'])
        with closing(sqlite3.connect(DATABASE.resolve().as_uri() + '?mode=ro',
                                     uri=True)) as con:
            self.assertEqual(con.execute(
                'SELECT count(*) FROM entry_papers WHERE entry_id=? AND paper_id=?',
                ('nmssm-matter', 'P28')).fetchone()[0], 1)

    def test_three_higgs_doublets_restore_colour_and_three_scalar_copies(self):
        entry = ENTRIES['three-higgs-doublets']
        spec = entry['identity']['input']
        self.assertEqual([(factor['family'], factor['rank'])
                          for factor in spec['gauge_factors']],
                         [('A', 2), ('A', 1), ('U1', 1)])
        scalars = [row for row in spec['matter'] if is_scalar(row['lorentz'])]
        self.assertEqual(sum(row['copies'] for row in scalars), 3)
        for row in scalars:
            reps = row['gauge_representations']
            self.assertEqual(reps['colour']['dynkin'], [0, 0])
            self.assertEqual(reps['weak']['dynkin'], [1])
            self.assertEqual(reps['hypercharge']['charge'], '3')
        self.assertEqual(len(spec['matter']) - len(scalars), 5)

    def test_ued_is_the_source_5d_branch_not_a_4d_lh_conversion(self):
        entry = ENTRIES['ued-orbifold-framework']
        regime = primary(entry)
        self.assertEqual(entry['primaryRegime'], 147)
        self.assertEqual([regime['id'] for variant in entry['variants']
                          for regime in variant['regimes']], [147])
        self.assertEqual(regime['dimension'], '5')
        fields = {field['label']: field for field in regime['fields']}
        self.assertEqual(set(fields), {'Q', 'U', 'D', 'L', 'E', 'H'})
        for label, field in fields.items():
            lorentz = field['lorentz'][0]
            self.assertEqual(lorentz['scheme'], 'B2_Dynkin')
            self.assertEqual(lorentz['irreps'], [[0, 0]] if label == 'H' else [[0, 1]])
            self.assertEqual(lorentz['component'], 'S' if label == 'H' else 'F')
            self.assertIsNone(field['sourceChirality'])
            self.assertNotIn('LH fermions', field['conversion'])
        for label, charge in [('U', '4'), ('D', '-2'), ('E', '-6')]:
            component = next(component for component in fields[label]['components']
                             if component['role'] == 'hypercharge')
            self.assertEqual(component['value'], charge)
        self.assertEqual(next(component for component in fields['U']['components']
                              if component['role'] == 'colour')['dynkin'], [1, 0])


class TypedChargeFamilies(unittest.TestCase):
    def test_sql_parameter_constraint_and_expression_roundtrips(self):
        expected_expressions = {}
        families = [entry for entry in DATA['entries']
                    if entry['identity']['input']['schema_version'] == 'field-content-3']
        with closing(sqlite3.connect(DATABASE.resolve().as_uri() + '?mode=ro',
                                     uri=True)) as con:
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
            for entry in families:
                parameters = dict(con.execute(
                    'SELECT parameter_name,domain FROM entry_parameters WHERE entry_id=?',
                    (entry['id'],)))
                self.assertEqual(parameters, {name: declaration['domain']
                                             for name, declaration in entry['parameters'].items()})
                constraints = [row[0] for row in con.execute(
                    'SELECT expression FROM entry_constraints WHERE entry_id=? '
                    'ORDER BY constraint_order', (entry['id'],))]
                self.assertEqual(constraints, entry['constraints'])
                stored = json.loads(con.execute(
                    'SELECT input_json FROM entry_identity WHERE entry_id=?',
                    (entry['id'],)).fetchone()[0])
                self.assertEqual(stored, entry['identity']['input'])
                for variant in entry['variants']:
                    for regime in variant['regimes']:
                        for field in regime['fields']:
                            key = entry['id'] + ':' + str(regime['id']) + ':' + field['catalogueRowId']
                            for index, lorentz in enumerate(field['lorentz']):
                                for factor, component in zip(regime['factors'],
                                                             lorentz['gaugeComponents']):
                                    if factor['type'] != 'U1':
                                        continue
                                    expression = component['chargeExpression']
                                    parse_charge(expression, tuple(entry['parameters']))
                                    expected_expressions[(key + ':' + str(index), factor['key'])] = expression
            actual = {(component_id, factor_key): expression
                      for component_id, factor_key, expression, convention
                      in con.execute('SELECT * FROM component_charge_expressions')
                      if convention == 'integer-polynomial-1'}
            self.assertEqual(actual, expected_expressions)
            for component_id, factor_key, charge in con.execute(
                    'SELECT component_id,factor_key,charge FROM component_gauge_representations'):
                if charge is not None:
                    self.assertRegex(charge, r'^-?\d+$')
                expression = actual.get((component_id, factor_key))
                if expression is not None and not re.fullmatch(r'-?\d+', expression):
                    self.assertIsNone(charge)

    def test_integer_charge_column_rejects_formulas_lists_and_source_strings(self):
        with closing(sqlite3.connect(DATABASE.resolve().as_uri() + '?mode=ro',
                                     uri=True)) as source:
            schema = source.execute(
                "SELECT sql FROM sqlite_master WHERE name='component_gauge_representations'"
            ).fetchone()[0]
            example = source.execute(
                'SELECT * FROM component_gauge_representations LIMIT 1').fetchone()
        with closing(sqlite3.connect(':memory:')) as con:
            con.execute(schema)
            con.execute('INSERT INTO component_gauge_representations VALUES (?,?,?,?,?,?,?,?,?)',
                        example)
            for invalid in ['n', 'n**2', '[0,-3,3]', '1/2', 'source:2', '?']:
                with self.subTest(value=invalid), self.assertRaises(sqlite3.IntegrityError):
                    con.execute('UPDATE component_gauge_representations SET charge=?', (invalid,))

    def test_symbolic_restriction_agrees_with_valid_numerical_specializations(self):
        points = {
            'u1-ybl-charge-family': [{'q': 0, 'r': 1}, {'q': 1, 'r': -2}],
            'u1-smnur-all-sm-yukawas': [
                {'q': 0, 'r': 1, 'n1': 1, 'n2': 1, 'n3': 1},
                {'q': 2, 'r': 1, 'n1': -5, 'n2': 4, 'n3': 4},
            ],
        }
        for entry_id, assignments in points.items():
            spec = ENTRIES[entry_id]['identity']['input']
            before = deepcopy(spec)
            with self.subTest(entry=entry_id):
                with patch('parameterized_entry.specialize',
                           side_effect=AssertionError('A restriction is not a specialization')):
                    restricted = restrict_nonabelian(spec)
                self.assertEqual(spec, before)
                self.assertEqual(restricted['id'], ENTRIES[entry_id]['coreId'])
                for assignment in assignments:
                    values = {ENTRIES[entry_id]['parameterRenaming'][name]: value for name, value in assignment.items()}
                    member = normalize_spec(specialize(spec, values))
                    self.assertEqual(restrict_nonabelian(member)['id'], restricted['id'])
                self.assertNotIn('parameter_assignment', restricted)
        with self.assertRaisesRegex(IncompleteContent, 'constraint'):
            specialize(ENTRIES['u1-ybl-charge-family']['identity']['input'], {'z1': 0, 'z2': 0})

    def test_complex_vector_restriction_keeps_complex_nonabelian_irrep(self):
        spec = vector_family([1, 0])
        restricted = restrict_nonabelian(spec)
        row = restricted['canonical']['matter'][0]
        self.assertEqual(row['reality'], 'complex')
        self.assertEqual(row['copies'], 1)
        self.assertEqual(restrict_nonabelian(normalize_spec(specialize(
            spec, {'n': 1})))['id'], restricted['id'])

    def test_complex_vector_restriction_splits_when_nonabelian_irrep_is_real(self):
        spec = vector_family([0, 0])
        restricted = restrict_nonabelian(spec)
        row = restricted['canonical']['matter'][0]
        self.assertEqual(row['reality'], 'real')
        self.assertEqual(row['copies'], 2)
        for value in [1, 2, -3]:
            self.assertEqual(restrict_nonabelian(normalize_spec(specialize(
                spec, {'n': value})))['id'], restricted['id'])


if __name__ == '__main__':
    unittest.main()
