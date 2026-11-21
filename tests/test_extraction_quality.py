"""Confidence routing and selective stronger-model follow-up, without API calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from bsm_atlas.catalogue import ROOT, load, write_json, identity
from bsm_atlas.extraction_quality import assessment, audit_decision
from bsm_atlas import quality_followup as follow
from bsm_atlas.joint_harvest import validate_response, taxonomies


class RoutingTests(unittest.TestCase):
    def test_self_confidence_does_not_override_mechanical_failure(self):
        quality=assessment({'state':'invalid','confidence':'high','uncertainty_reason':''})
        self.assertTrue(quality['needs_followup']);self.assertIn('validation_failed',quality['automatic_flags'])
        self.assertEqual(audit_decision('2401.00001v1',{'state':'invalid','quality':quality}),'flagged')

    def test_unknown_legacy_confidence_is_not_fabricated(self):
        quality=assessment({'state':'ingested','outcome':'skip'})
        self.assertIsNone(quality['confidence']);self.assertEqual(quality['confidence_status'],'not_reported')
        self.assertIsNone(audit_decision('2401.00001v1',{'state':'ingested','outcome':'skip','quality':quality},fraction=0))

    def test_source_failures_wait_for_repair_instead_of_wasting_a_model_call(self):
        row={'state':'source_unavailable','reason':'missing TeX dependency'}
        self.assertEqual(audit_decision('2401.00001v1',row),'source_repair')

    def test_low_confidence_and_failed_quotes_both_route_to_followup(self):
        row={'state':'ingested','confidence':'low','uncertainty_reason':'Variant attribution is unclear'}
        self.assertEqual(audit_decision('a',row),'flagged')
        row={'state':'ingested','confidence':'high','annotations':[{'problems':[{'reviewReasons':['quote_found']}]}]}
        self.assertEqual(audit_decision('a',row),'flagged')

    def test_random_audit_reproducibly_samples_skips_and_entries(self):
        for outcome in ('skip','entries'):
            row={'state':'ingested','outcome':outcome,'confidence':'high','uncertainty_reason':''}
            forward={i for i in range(10000) if audit_decision(str(i),row)}
            reverse={i for i in reversed(range(10000)) if audit_decision(str(i),row)}
            self.assertEqual(forward,reverse);self.assertTrue(140<len(forward)<260)
            self.assertTrue(all('high_confidence' in audit_decision(str(i),row) for i in forward))


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.catalogue_sample import catalogue_sample
        cls.catalogue_fixture = catalogue_sample('two-higgs-doublets')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'catalogue.json';self.run=self.root/'follow';(self.run/'jobs').mkdir(parents=True)
        self.paper={'id':'new-paper','arxiv':'2401.00001v1','title':'New paper','authors':'A'}
        self.data=deepcopy(self.catalogue_fixture);self.entry=deepcopy(next(e for e in self.data['entries'] if e['id']=='two-higgs-doublets'))
        self.data['papers'].append({**self.paper,'extraction_status':'complete'})
        self.body='This model supplies a dark matter candidate.\n'+'Equations and source discussion. '*20
        self.result={'outcome':'entries','reason':'Complete model explicitly supplied','coverage':'full_text',
            'confidence':'high','uncertainty_reason':'','entries':[{'id':'alternate-doublet','name':'Doublet extension',
                'specification_json':json.dumps(self.entry['specification']),'locators':['L000001; section 2'],
                'problems':[],'mechanisms':[]}]}
        self.baseline_dir=self.root/'luna';self.baseline_dir.mkdir()
        self.baseline={'state':'ingested','paper':self.paper,'outcome':'entries','baseline_job':str(self.baseline_dir),
                       'quality':assessment({'state':'ingested','confidence':'high','uncertainty_reason':''})}
        self.job=self.run/'jobs'/'2401.00001v1';self.job.mkdir()
        write_json(self.job/'metrics.json',{'model':'gpt-6.1-terra','reasoning':'medium','usage':{'input_tokens':100}})

    def prepared(self):
        entries,annotations=validate_response(self.paper,self.result,self.body,taxonomies())
        row={'state':'ready','paper':self.paper,'outcome':'entries','reason':'Complete model',
             'coverage':'full_text','confidence':'high','uncertainty_reason':'','entries':entries,'annotations':annotations}
        row['quality']=assessment(row,self.result)
        return row

    def test_disagreement_is_recorded_without_silently_unioning_models(self):
        write_json(self.source,self.data);before=self.source.read_bytes()
        summary=follow.finish(self.run,self.prepared(),self.baseline,{'fingerprints':['another-fingerprint'],'problems':[],'mechanisms':[]},'random_entries_high_confidence',self.source)
        self.assertEqual(summary['state'],'disagreement');self.assertFalse(summary['applied'])
        self.assertEqual(self.source.read_bytes(),before)
        self.assertTrue((self.baseline_dir/'followup.json').exists())

    def test_agreement_is_not_a_new_paid_ingestion_or_truth_certificate(self):
        write_json(self.source,self.data);before=self.source.read_bytes();row=self.prepared()
        snapshot=follow.extracted_snapshot(row)
        # Recovering comparison snapshots from JSON must not change equality.
        snapshot=json.loads(json.dumps(snapshot))
        summary=follow.finish(self.run,row,self.baseline,snapshot,'random_entries_high_confidence',self.source)
        self.assertEqual(summary['state'],'agreement');self.assertFalse(summary['applied'])
        self.assertEqual(self.source.read_bytes(),before)

    def test_valid_terra_recovery_of_a_luna_skip_merges_into_existing_model(self):
        write_json(self.source,self.data);baseline={**self.baseline,'outcome':'skip'}
        summary=follow.finish(self.run,self.prepared(),baseline,{'fingerprints':[],'problems':[],'mechanisms':[]},'pilot_skip',self.source)
        self.assertEqual(summary['state'],'recovered');self.assertTrue(summary['applied'])
        after=load(self.source);self.assertEqual(len(after['entries']),len(self.data['entries']))
        model=next(e for e in after['entries'] if e['id']=='two-higgs-doublets')
        self.assertIn('new-paper',[r['paper_id'] for r in model['references']])
        paper=next(p for p in after['papers'] if p['id']=='new-paper')
        self.assertEqual(paper['extractor']['model'],'gpt-6.1-terra')
        self.assertEqual(json.loads((self.job/'metrics.json').read_text())['model'],'gpt-6.1-terra')

    def test_uncertain_terra_output_does_not_overwrite_a_skipped_inventory(self):
        write_json(self.source,self.data);before=self.source.read_bytes();row=self.prepared()
        row['quality']=assessment({'state':'ready','confidence':'low','uncertainty_reason':'Unclear source'})
        summary=follow.finish(self.run,row,{**self.baseline,'outcome':'skip'}, {'fingerprints':[],'problems':[],'mechanisms':[]},'pilot_skip',self.source)
        self.assertEqual(summary['state'],'uncertain');self.assertFalse(summary['applied'])
        self.assertEqual(self.source.read_bytes(),before)

    def test_missing_reason_for_low_confidence_is_rejected(self):
        self.result['confidence']='low'
        with self.assertRaisesRegex(ValueError,'uncertainty reason'):self.prepared()


if __name__=='__main__':unittest.main()
