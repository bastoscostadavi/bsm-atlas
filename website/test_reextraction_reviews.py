"""Acceptance-gate regressions; not an independent scientific source review."""
from copy import deepcopy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from build_field_catalogue import ROOT, TEMPLATES, display_rep, dynkin
from catalogue_identity import canonicalize, normalize_spec, from_regime
from catalogue_identity_v1 import canonicalize as canonicalize_v1, normalize_spec as normalize_v1, from_regime as from_regime_v1
from reextraction_reviews import load_reviews, replace_regime, apply_reviews
from current_reextraction_reviews import load_current_reviews, apply_current_reviews

DATA = json.loads((ROOT / 'website/field-catalogue.json').read_text())


class Acceptance(unittest.TestCase):
    def test_only_explicit_accepted_manifest_is_read(self):
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            self.assertNotIn(path.name, ['queue.json', 'corpus-run-ledger.json'])
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            reviews = load_reviews(ROOT)
        self.assertEqual(len(reviews), 6)
        self.assertEqual({r['decision']['paper'] for r in reviews},
                         {'P01', 'P02', 'P03', 'P04', 'P05'})
        for review in reviews:
            candidate = review['candidate']
            self.assertEqual(candidate, normalize_v1(candidate))
            self.assertEqual(canonicalize_v1(candidate)['fingerprint'], review['decision']['fingerprint'])
            self.assertEqual(normalize_spec(candidate)['schema_version'],'field-content-2')

    def test_changed_evidence_hash_blocks_build(self):
        original = Path.read_bytes
        def changed(path, *args, **kwargs):
            raw = original(path, *args, **kwargs)
            return raw + b' ' if path.name == 'checkpoint.json' else raw
        with patch.object(Path, 'read_bytes', changed), self.assertRaisesRegex(ValueError, 'evidence changed'):
            load_reviews(ROOT)

    def test_source_shaped_payload_is_not_normalized_silently_at_intake(self):
        original = Path.read_text
        def changed(path, *args, **kwargs):
            raw = original(path, *args, **kwargs)
            if path.name == 'lr-normalized-candidate.json':
                spec = json.loads(raw)
                for f in spec['matter']:
                    f['gauge_representations']['bl']['charge'] = str(int(f['gauge_representations']['bl']['charge']) * 2)
                return json.dumps(spec)
            return raw
        with patch.object(Path, 'read_text', changed), self.assertRaisesRegex(ValueError, 'needs normalization'):
            load_reviews(ROOT)

    def test_duplicate_acceptance_decision_blocks_build(self):
        original = Path.read_text
        def changed(path, *args, **kwargs):
            raw = original(path, *args, **kwargs)
            if path.name == 'accepted.json':
                manifest = json.loads(raw)
                manifest['reviews'].append(deepcopy(manifest['reviews'][0]))
                return json.dumps(manifest)
            return raw
        with patch.object(Path, 'read_text', changed), self.assertRaisesRegex(ValueError, 'Duplicate acceptance'):
            load_reviews(ROOT)

    def test_wrong_existing_entry_cannot_be_confirmed(self):
        review = deepcopy(load_reviews(ROOT)[0])
        review['decision']['entry'] = 'two-higgs-doublets'
        def identity_input(r):
            original=deepcopy(r)
            for f in original['fields']:
                for l in f['lorentz']:
                    if l.get('sourceScalar'): l['reality']=l['sourceScalar']['reality']
            return from_regime_v1(original,TEMPLATES,dynkin)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            apply_reviews(deepcopy(DATA['entries']), deepcopy(DATA['papers']),
                          [review], display_rep, identity_input)

    def test_unmapped_original_field_cannot_be_lost(self):
        review = next(r for r in load_reviews(ROOT) if r['decision']['paper'] == 'P04')
        entry = next(e for e in DATA['entries'] if e['id'] == 'lr-triplet-matter')
        regime = deepcopy(entry['variants'][0]['regimes'][0])
        regime['fields'][0]['sourceFieldId'] = 999999
        with self.assertRaisesRegex(ValueError, 'lose an original source field'):
            replace_regime(regime, review, display_rep)

    def test_saved_numerical_review_payload_is_normalized(self):
        db = ROOT / 'website/downloads/field-catalogue.sqlite'
        with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)) as con:
            rows = con.execute('SELECT fingerprint,normalized_entry_json,review_json FROM extraction_reviews').fetchall()
        self.assertEqual(len(rows), 12)
        for expected, payload, provenance in rows:
            spec = json.loads(payload)
            review = json.loads(provenance)
            self.assertEqual(spec, normalize_spec(spec))
            self.assertEqual(canonicalize(spec)['fingerprint'], expected)
            self.assertFalse(review['wholePaperRead'])
            self.assertEqual(review['reviewStatus'], 'agent_source_checked_curator_integrated')

    def test_current_gate_ignores_mutable_agent_manifest(self):
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'integration-manifest.json')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            reviews = load_current_reviews(ROOT)
        self.assertEqual(len(reviews), 6)
        for review in reviews:
            entry = next(e for e in DATA['entries'] if e['id'] == review['decision']['entry'])
            self.assertEqual(entry['identity']['fingerprint'], review['decision']['fingerprint'])

    def test_current_evidence_is_hash_pinned(self):
        original = Path.read_bytes
        def changed(path, *args, **kwargs):
            raw = original(path, *args, **kwargs)
            return raw + b' ' if path.name.endswith('-field-evidence.json') else raw
        with patch.object(Path, 'read_bytes', changed), self.assertRaisesRegex(ValueError, 'evidence changed'):
            load_current_reviews(ROOT)

    def test_su5_inheritance_is_explicit_and_regimes_do_not_mix(self):
        entries = {e['id']:e for e in DATA['entries']}
        e = entries['su5-gg-extra5-two10']
        regimes = {r['id']:r for v in e['variants'] for r in v['regimes']}
        self.assertEqual({f['sourceFieldId'] for f in regimes[36]['fields']},{120,121,122,123,125,126})
        self.assertEqual({f['sourceFieldId'] for f in regimes[37]['fields']},{127,128})
        self.assertEqual(next(f for f in regimes[36]['fields'] if f['sourceFieldId']==120)['reextraction']['sourceMapping']['source_regime_id'],35)
        self.assertIsNone(entries['su5-rpv-trilinear-sector']['identity']['fingerprint'])

    def test_current_adapter_cannot_drop_unmapped_matter(self):
        entries = deepcopy(DATA['entries'])
        e = next(e for e in entries if e['id']=='su5-georgi-glashow-review')
        r = next(r for v in e['variants'] for r in v['regimes'] if r['id']==35)
        r['fields'][0]['sourceFieldId'] = 999999
        with self.assertRaisesRegex(ValueError, 'lose or ambiguously map'):
            apply_current_reviews(entries,deepcopy(DATA['papers']),load_current_reviews(ROOT),display_rep)

    def test_so10_source_scope_and_real_module_multiplicities(self):
        entries={e['id']:e for e in DATA['entries']}
        for entry_id,regime_id,ids in [('so10-45-126-sector',61,{229,230,234}),
                                       ('so10-45-126-complex10',64,{231,232,233,234})]:
            entry=entries[entry_id]
            regimes={r['id']:r for v in entry['variants'] for r in v['regimes']}
            regime=regimes[regime_id]
            self.assertEqual(entry['publicationStatus'],'ready')
            self.assertIsNone(regime['baseline'])
            self.assertEqual([a['id'] for a in regime['factors']],['D5'])
            self.assertEqual({f['sourceFieldId'] for f in regime['fields']},ids)
            fields={f['label']:f for f in regime['fields']}
            expected={'45H':([0,1,0,0,0],1,'real'),
                      '126H':([0,0,0,2,0],1,'complex'),
                      '16F':([0,0,0,1,0],3,None)}
            if regime_id==64:expected['10H']=([1,0,0,0,0],2,'complex')
            for name,(weight,multiplicity,reality) in expected.items():
                f=fields[name];l=f['lorentz'][0]
                self.assertEqual(f['components'][0]['dynkin'],weight)
                self.assertEqual(l['gaugeComponents'][0]['dynkin'],weight)
                self.assertEqual(l['copies'],multiplicity)
                self.assertEqual(l['irreps'],[['1/2','0']] if name=='16F' else [['0','0']])
                self.assertIn('legacyProjection',f)
                if reality:
                    self.assertEqual(l['reality'],'real_module')
                    self.assertEqual(l['sourceScalar']['reality'],reality)
                    self.assertEqual(l['sourceScalar']['copies'],1)
            if regime_id==61:
                self.assertNotIn('10H',fields)
                self.assertIn('scalar',regime['legacyDescription'].lower())
                inherited=fields['16F']['reextraction']['sourceMapping']
                self.assertEqual(inherited['source_regime_id'],64)
                self.assertEqual(inherited['source_model_id'],'so10-45-126-complex10')
                self.assertIn('explicitly_inherited',inherited['mapping_basis'])
                self.assertEqual(regimes[62]['fields'],[])
                self.assertEqual(regimes[63]['fields'],[])

    def test_so10_independent_review_pins_the_final_intake_files(self):
        reviews=[r for r in load_current_reviews(ROOT) if r['decision']['paper']=='P19']
        self.assertEqual(len(reviews),2)
        for review in reviews:
            math=review['mathematics']
            pins=math['final_artifact_hashes'];base=ROOT/pins['base_directory']
            for filename,expected in pins.items():
                if filename!='base_directory':
                    self.assertEqual(hashlib.sha256((base/filename).read_bytes()).hexdigest(),expected)
            self.assertEqual(math['review_status'],'frozen_final_source_artifacts_verified')
            self.assertFalse(math['source']['whole_paper_read'])

    def test_current_manifest_cannot_escape_its_review_directory(self):
        original=Path.read_text
        def changed(path,*args,**kwargs):
            raw=original(path,*args,**kwargs)
            if path.name=='accepted-so10.json':
                manifest=json.loads(raw)
                manifest['reviews'][0]['files']['source']['path']='atlas/field_content_curations.json'
                return json.dumps(manifest)
            return raw
        with patch.object(Path,'read_text',changed),self.assertRaisesRegex(ValueError,'outside accepted evidence'):
            load_current_reviews(ROOT)


if __name__ == '__main__':
    unittest.main()
