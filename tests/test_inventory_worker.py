"""The Terra inventory protocol excludes taxonomy input, output and certification."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from bsm_atlas import inventory_worker as inventory, joint_harvest as joint
from bsm_atlas.catalogue import ROOT, identity, write_json
from bsm_atlas.literature import bind_luna_receipt


class InventoryWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root/'run/jobs/2401.00001v1'
        self.paper = {'id': 'paper', 'arxiv': '2401.00001v1', 'title': 'Paper', 'authors': 'A'}
        self.result = {'outcome': 'entries', 'reason': 'Explicit MSSM inventory', 'coverage': 'full_text',
            'confidence': 'high', 'uncertainty_reason': '', 'entries': [{'id': 'mssm', 'name': 'MSSM',
                'specification_json': json.dumps({'reference_spectrum': 'R_MSSM', 'additions': []}),
                'locators': ['Section 2, explicitly adopted MSSM']}]}

    def test_protocol_has_no_taxonomy_fields_or_dependency(self):
        schema = inventory.response_schema()
        self.assertNotIn('problems', json.dumps(schema))
        self.assertNotIn('mechanisms', json.dumps(schema))
        with patch.object(joint, 'taxonomies', side_effect=AssertionError('Terra must not load taxonomies')):
            message = inventory.assemble(self.paper, 'The paper explicitly adopts the MSSM.', inventory.context())
            entries = inventory.validate_response(self.paper, self.result)
        self.assertNotIn('FIXED TAXONOMIES', message)
        self.assertNotIn('JOINT OUTPUT CONTRACT', message)
        expected = joint.read(ROOT/'atlas/reference_spectra.json')['R_MSSM']['specification']
        self.assertEqual(identity(entries[0]['specification'])['fingerprint'], identity(expected)['fingerprint'])

    def test_prompt_is_smaller_than_joint_prompt_for_same_source(self):
        body = 'Model fields and representations.\n'*20
        instructions = inventory.context()
        before = joint.assemble(self.paper, body, instructions, joint.taxonomies())
        after = inventory.assemble(self.paper, body, instructions)
        self.assertLess(len(after), len(before))

    def test_new_outputs_reject_annotations_and_legacy_recovery_ignores_them(self):
        legacy = deepcopy(self.result)
        legacy['entries'][0].update(problems=[{'arbitrary': 'old annotation'}], mechanisms=[])
        with self.assertRaises(ValueError):
            inventory.validate_response(self.paper, legacy)
        entries = inventory.validate_response(self.paper, legacy, legacy=True)
        self.assertEqual(entries, inventory.validate_response(self.paper, self.result))

    def test_confidence_and_unusable_source_still_require_validation(self):
        result = deepcopy(self.result)
        result.update(confidence='low', uncertainty_reason='')
        with self.assertRaisesRegex(ValueError, 'uncertainty'):
            inventory.validate_response(self.paper, result)
        result = {**self.result, 'coverage': 'unusable'}
        with self.assertRaisesRegex(ValueError, 'Unusable text'):
            inventory.validate_response(self.paper, result)

    def test_worker_writes_inventory_metrics_and_sends_reduced_prompt(self):
        self.job.parent.parent.mkdir(parents=True)
        write_json(self.job.parent.parent/'response.schema.json', inventory.response_schema())
        def launch(command, **kwargs):
            write_json(self.job/'result.json', self.result)
            kwargs['stdout'].write(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100}})+'\n')
            return Mock(returncode=0)
        with patch.object(inventory.subprocess, 'Popen', side_effect=launch):
            row = inventory.run_worker(self.job, self.paper, 'Paper source.', {}, inventory.context(),
                {'model': 'gpt-6.1-terra', 'reasoning': 'medium', 'executable': 'fake-codex', 'timeout': 900})
        self.assertEqual(row['state'], 'ready')
        self.assertEqual(row['scope'], 'entries')
        self.assertNotIn('annotations', row)
        metrics = joint.read(self.job/'metrics.json')
        self.assertEqual(metrics['usage']['input_tokens'], 100)
        self.assertEqual(metrics['scope'], 'entries')
        self.assertNotIn('FIXED TAXONOMIES', (self.job/'prompt.txt').read_text())

    def test_timeout_preserves_attempt_without_marking_it_infrastructure_failure(self):
        process = Mock(pid=123456789)
        process.poll.return_value = None
        process.communicate.side_effect = subprocess.TimeoutExpired('fake', 900)
        with patch.object(inventory.subprocess, 'Popen', return_value=process), patch.object(inventory.os, 'killpg'):
            row = inventory.run_worker(self.job, self.paper, 'Paper source.', {}, inventory.context(),
                {'model': 'gpt-6.1-terra', 'reasoning': 'medium', 'executable': 'fake', 'timeout': 900})
        self.assertEqual(row['category'], 'worker_timeout')
        self.assertFalse(row['infrastructure'])
        self.assertTrue((self.job/'metrics.json').exists())

    def test_detached_luna_claim_reattaches_only_to_exact_inventory(self):
        entry = inventory.validate_response(self.paper, self.result)[0]
        fingerprint = identity(entry['specification'])['fingerprint']
        model = {'entry_id': 'old-id', 'problems': [], 'mechanisms': []}
        receipt = {'arxiv': self.paper['arxiv'], 'extractor': {'model': 'gpt-6-luna'}, 'models': [],
                   'detached_models': [{'model': model, 'fingerprint': fingerprint}]}
        rebound = bind_luna_receipt(receipt, [], [entry], self.paper)
        self.assertEqual(rebound['models'][0]['entry_id'], entry['id'])
        self.assertEqual(rebound['detached_models'], [])
        wrong = deepcopy(entry)
        wrong['id'] = 'old-id'
        wrong['specification']['matter'][0]['copies'] += 1
        retained = bind_luna_receipt(receipt, [], [wrong], self.paper)
        self.assertEqual(retained['models'], [])
        self.assertEqual(retained['detached_models'], receipt['detached_models'])


if __name__ == '__main__':
    unittest.main()
