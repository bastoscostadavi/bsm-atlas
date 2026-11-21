"""Fast intake preserves canonical validation and the default public export."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bsm_atlas import build, joint_harvest as joint
from bsm_atlas.catalogue import ROOT, validate, write_json


def fixture():
    specification=json.loads((ROOT/'atlas/examples/two-higgs-doublets.json').read_text())
    return {'schema_version':'bsm-atlas-1','papers':[{
        'id':'source-paper','arxiv':'2401.00001v1','title':'Source paper','authors':'Author'}],
        'entries':[{'id':'doublet-model','name':'Doublet model','specification':specification,
                    'references':[{'paper_id':'source-paper'}]}]}


class IntakePerformanceTests(unittest.TestCase):
    def setUp(self):
        joint._INTAKE_SPECIFICATION_CACHE.clear()
        self.data=fixture()
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.source=self.root/'catalogue.json'
        self.batch=self.root/'run';self.job=self.batch/'jobs/2401.00002v1';self.job.mkdir(parents=True)
        self.paper={'id':'new-paper','arxiv':'2401.00002v1','title':'New paper','authors':'Other Author'}

    def row(self):
        entry=deepcopy(self.data['entries'][0]);entry.update(id='another-name',name='Another name')
        entry['references']=[{'paper_id':'new-paper','locators':['Table 1']}]
        return {'state':'ready','paper':self.paper,'outcome':'entries','coverage':'full_text',
                'reason':'Complete specified extension','entries':[entry],
                'annotations':[{'local_id':'another-name','problems':[],'mechanisms':[]}]}

    def test_projection_without_properties_matches_default_export(self):
        full=build.main_data(deepcopy(self.data))
        self.assertIn('propertySummary',full);self.assertIn('properties',full['entries'][0])
        expected=deepcopy(full);expected.pop('propertySummary')
        for entry in expected['entries']:entry.pop('properties')
        with patch.object(build,'assess_properties',side_effect=AssertionError('Derived physics called')):
            reduced=build.main_data(deepcopy(self.data),include_properties=False)
        self.assertEqual(reduced,expected)

    def test_projection_still_rejects_invalid_and_duplicate_specs(self):
        for change in ['invalid','duplicate']:
            data=deepcopy(self.data)
            if change=='invalid':data['entries'][0]['specification']['matter'][0]['copies']=0
            else:
                entry=deepcopy(data['entries'][0]);entry['id']='duplicate';data['entries'].append(entry)
            with self.subTest(change=change),self.assertRaises(ValueError):
                build.main_data(data,include_properties=False)

    def test_intake_keeps_duplicate_merge_links_and_idempotent_receipts(self):
        write_json(self.source,self.data)
        with patch.object(build,'assess_properties',side_effect=AssertionError('Derived physics called')):
            joint.intake(self.batch,[self.row()],self.source)
            first=json.loads(self.source.read_text())
            joint.intake(self.batch,[self.row()],self.source)
            self.assertEqual(json.loads(self.source.read_text()),first)
        validate(first)
        self.assertEqual(len(first['entries']),1)
        self.assertEqual({r['paper_id'] for r in first['entries'][0]['references']},{'source-paper','new-paper'})
        self.assertEqual(json.loads((self.job/'state.json').read_text())['entry_ids'],['doublet-model'])
        self.assertFalse((self.job/'intake.json').exists())
        links=json.loads(self.source.with_name('literature_links.json').read_text())
        self.assertEqual(links['papers']['new-paper']['models'][0]['entry_id'],'doublet-model')

    def test_cached_validation_does_not_hide_mutation_or_invalid_reference(self):
        write_json(self.source,self.data);joint.intake(self.batch,[self.row()],self.source)
        data=json.loads(self.source.read_text());data['entries'][0]['specification']['matter'][0]['copies']=0
        write_json(self.source,data)
        with self.assertRaises(ValueError):joint.intake(self.batch,[self.row()],self.source)
        write_json(self.source,self.data);joint.intake(self.batch,[self.row()],self.source)
        data=json.loads(self.source.read_text());data['entries'][0]['references'][0]['paper_id']='missing'
        write_json(self.source,data)
        with self.assertRaises(ValueError):joint.intake(self.batch,[self.row()],self.source)

    def test_interrupted_commit_preserves_journal_and_replays_without_call(self):
        write_json(self.source,self.data);real=joint.write_json
        def fail_links(path,value):
            if Path(path).name=='literature_links.json':raise OSError('Interrupted link write')
            return real(path,value)
        with patch.object(joint,'write_json',side_effect=fail_links),self.assertRaises(OSError):
            joint.intake(self.batch,[self.row()],self.source)
        self.assertTrue((self.job/'intake.json').exists())
        with patch.object(joint,'run_worker',side_effect=AssertionError('Paid call repeated')):
            joint.intake(self.batch,[json.loads((self.job/'intake.json').read_text())],self.source)
        self.assertEqual(len(json.loads(self.source.read_text())['entries']),1)
        self.assertFalse((self.job/'intake.json').exists())


if __name__=='__main__':unittest.main()
