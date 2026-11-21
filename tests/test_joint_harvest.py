"""Offline joint-harvest regressions: identity, links, source retention, recovery."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import subprocess

from bsm_atlas import joint_harvest as joint, corpus, corpus_queue
from bsm_atlas.catalogue import ROOT, load, write_json
from bsm_atlas.literature import load_links, merge_preview
from tests.test_corpus import FakeClient, tarball


class JointHarvestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.catalogue_sample import catalogue_sample
        cls.catalogue_fixture = catalogue_sample('two-higgs-doublets', 'mssm-matter')

    def test_single_worker_timeout_is_recorded_without_stopping_batch(self):
        job=self.batch/'jobs'/'2401.00001v1'
        process=Mock();process.pid=123456789;process.poll.return_value=None
        process.communicate.side_effect=subprocess.TimeoutExpired('fake isolated worker',900)
        with patch.object(joint.subprocess,'Popen',return_value=process),patch.object(joint.os,'killpg') as kill:
            row=joint.run_worker(job,self.paper,self.body,{},'Instructions',self.definitions,
                {'executable':'fake-codex','reasoning':'medium','timeout':900})
        self.assertEqual(row['state'],'retry');self.assertEqual(row['category'],'worker_timeout')
        self.assertFalse(row['infrastructure']);self.assertTrue(row['quality']['needs_followup'])
        kill.assert_called_once();process.wait.assert_called_once()
        self.assertTrue((job/'metrics.json').exists())

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'catalogue.json'
        self.batch=self.root/'run';(self.batch/'jobs').mkdir(parents=True)
        self.paper={'id':'new-paper','arxiv':'2401.00001v1','title':'A new paper','authors':'An Author'}
        self.data=deepcopy(self.catalogue_fixture);self.entry=deepcopy(next(e for e in self.data['entries'] if e['id']=='two-higgs-doublets'))
        self.body='We explicitly analyze this model as a dark matter candidate.\nThermal freeze-out sets its relic density.\n'+'A source equation. '*30
        self.definitions=joint.taxonomies()
        self.quote={'quote':'We explicitly analyze this model as a dark matter candidate.','locator':'L000001; section 2'}
        self.result={'outcome':'entries','reason':'Complete renormalizable SM plus extra doublet inventory','coverage':'full_text','confidence':'high','uncertainty_reason':'','entries':[{
            'id':'different-doublet-name','name':'A doublet extension','specification_json':json.dumps(self.entry['specification']),
            'locators':['section 2'],'problems':[{'problem_id':'dark_matter','status':'addresses','rationale':'The paper studies this model as dark matter.','evidence':[self.quote]}],
            'mechanisms':[]}]}

    def prepared(self,result=None):
        result=deepcopy(result or self.result)
        entries,annotations=joint.validate_response(self.paper,result,self.body,self.definitions)
        return {'state':'ready','paper':self.paper,'entries':entries,'annotations':annotations,
                'outcome':result['outcome'],'coverage':result['coverage'],'reason':result['reason'],'result_sha256':'hash'}

    def test_canonical_merge_remaps_connections_and_replays_without_duplication(self):
        write_json(self.source,self.data)
        row=self.prepared();job=self.batch/'jobs'/'2401.00001v1';job.mkdir()
        for name in ('prompt.txt','events.jsonl','result.json','stderr.txt'):(job/name).write_text('temporary')
        write_json(job/'metrics.json',{'usage':{'input_tokens':123},'reasoning':'medium'})
        joint.intake(self.batch,[row],self.source)
        result=load(self.source);self.assertEqual(len(result['entries']),len(self.data['entries']))
        self.assertEqual(row['entry_ids'],['two-higgs-doublets'])
        stored=load_links(self.source.with_name('literature_links.json'))
        model=stored['papers']['new-paper']['models'][0]
        self.assertEqual(model['entry_id'],'two-higgs-doublets')
        self.assertEqual(model['problems'][0]['term_id'],'dark_matter')
        self.assertEqual(model['problems'][0]['reviewReasons'],[])
        self.assertFalse((job/'result.json').exists());self.assertTrue((job/'metrics.json').exists())
        joint.intake(self.batch,[row],self.source)
        self.assertEqual(load_links(self.source.with_name('literature_links.json')),stored)
        self.assertEqual(sum(p['id']=='new-paper' for p in load(self.source)['papers']),1)
        paper=next(p for p in result['papers'] if p['id']=='new-paper')
        self.assertEqual(paper['extractor'],{'provider':'openai','model':'gpt-6-luna','reasoning':'medium'})
        preview={'problems':[{'id':'dark_matter'}],'assessed':[],'links':{}}
        self.assertEqual(merge_preview(preview,'problems',self.source)['links']['two-higgs-doublets']['dark_matter'][0]['paperId'],'new-paper')

    def test_source_unavailable_records_paper_without_inventing_model(self):
        write_json(self.source,{'schema_version':'bsm-atlas-1','papers':[],'entries':[]})
        row={'state':'source_unavailable','paper':self.paper,'reason':'pdf_only'}
        job=self.batch/'jobs'/'2401.00001v1';job.mkdir()
        joint.intake(self.batch,[row],self.source)
        result=load(self.source);self.assertFalse(result['entries'])
        self.assertEqual(result['papers'][0]['extraction_status'],'unresolved')

    def test_sparse_links_and_uncertainty_do_not_turn_into_false_positive(self):
        result=deepcopy(self.result);result['entries'][0]['problems'][0]['status']='unclear'
        result['coverage']='partial_text'
        self.assertEqual(self.prepared(result)['annotations'][0]['problems'],[])
        result['entries'][0]['problems'][0]['status']='addresses'
        self.assertIn('limited_text_coverage',self.prepared(result)['annotations'][0]['problems'][0]['reviewReasons'])

    def test_reference_recipes_copy_the_mssm_exactly_and_keep_new_sm_matter(self):
        result=deepcopy(self.result);result['entries'][0]['specification_json']=json.dumps({'reference_spectrum':'R_MSSM','additions':[]})
        row=self.prepared(result)
        from bsm_atlas.catalogue import identity
        expected=next(e for e in self.data['entries'] if e['id']=='mssm-matter')
        self.assertEqual(identity(row['entries'][0]['specification'])['fingerprint'],identity(expected['specification'])['fingerprint'])
        reference=json.loads((ROOT/'atlas/reference_spectra.json').read_text())['R_SM']['specification']
        addition=deepcopy(reference['matter'][-1]);addition['copies']=1
        result['entries'][0]['specification_json']=json.dumps({'reference_spectrum':'R_SM','additions':[addition]})
        spec=self.prepared(result)['entries'][0]['specification']
        self.assertEqual(sum(r['copies'] for r in spec['matter']),sum(r['copies'] for r in reference['matter'])+1)
        self.assertNotEqual(identity(spec)['fingerprint'],identity(reference)['fingerprint'])

    def test_bad_taxonomy_and_missing_evidence_and_invalid_model_are_rejected(self):
        for kind in ['taxonomy','evidence','unusable','specification','repeated_id']:
            result=deepcopy(self.result)
            if kind=='taxonomy':result['entries'][0]['problems'][0]['problem_id']='invented_problem'
            elif kind=='evidence':result['entries'][0]['problems'][0]['evidence']=[]
            elif kind=='unusable':result['coverage']='unusable'
            elif kind=='specification':
                s=json.loads(result['entries'][0]['specification_json']);s['matter'][0]['copies']=0
                result['entries'][0]['specification_json']=json.dumps(s)
            else:result['entries'].append(deepcopy(result['entries'][0]))
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.prepared(result)

    def test_inexact_evidence_is_flagged_not_silently_certified(self):
        result=deepcopy(self.result);result['entries'][0]['problems'][0]['evidence']=[{'quote':'Invented quotation','locator':'L999999'}]
        flags=self.prepared(result)['annotations'][0]['problems'][0]['reviewReasons']
        self.assertIn('quote_found',flags);self.assertIn('locator_has_valid_line',flags)

    def test_interrupted_two_file_commit_recovers_using_validated_delta(self):
        write_json(self.source,self.data);job=self.batch/'jobs'/'2401.00001v1';job.mkdir();row=self.prepared()
        real=joint.write_json
        def fail_store(path,data):
            if Path(path).name=='literature_links.json':raise OSError('simulated interrupted commit')
            real(path,data)
        with patch.object(joint,'write_json',side_effect=fail_store),self.assertRaises(OSError):joint.intake(self.batch,[row],self.source)
        self.assertTrue((job/'intake.json').exists())
        joint.intake(self.batch,[json.loads((job/'intake.json').read_text())],self.source)
        self.assertFalse((job/'intake.json').exists())
        self.assertEqual(load_links(self.source.with_name('literature_links.json'))['papers']['new-paper']['models'][0]['entry_id'],'two-higgs-doublets')

    def test_bounded_worker_run_resumes_without_repeating_paid_attempt(self):
        write_json(self.source,self.data)
        manifest=self.root/'manifest.json';write_json(manifest,{'papers':[self.paper]})
        local=self.root/'corpus';target=corpus.paper_dir(local,'2401.00001','v1')
        raw=('\\documentclass{article}\n\\begin{document}\n'+self.body+'\n\\end{document}').encode()
        corpus._save(target,'2401.00001','v1','single',{'main.tex':raw},[],'test-source',len(raw))
        run_dir=self.root/'bounded'
        def fake(job,paper,body,provenance,instructions,definitions,config):
            job.mkdir(parents=True);write_json(job/'metrics.json',{'usage':{'input_tokens':123},'reasoning':'medium'})
            entries,annotations=joint.validate_response(paper,self.result,body,definitions)
            return {'state':'ready','paper':paper,'entries':entries,'annotations':annotations,
                    'coverage':'full_text','outcome':'entries','reason':'Complete model','infrastructure':False}
        with patch.object(joint,'check_worker'),patch.object(joint,'run_worker',side_effect=fake) as worker:
            first=joint.run(manifest,run_dir,execute=True,workers=1,source=self.source,corpus=local,max_papers=1)
            self.assertEqual(first['counts'],{'ingested':1})
            second=joint.run(manifest,run_dir,execute=True,resume=True,workers=1,source=self.source,corpus=local)
            self.assertEqual(second['phase'],'completed');self.assertEqual(worker.call_count,1)
            # Upgrade is explicit, preserves old attempts and refuses implicit
            # changes to the frozen prompt/model/run settings.
            original=json.loads((run_dir/'config.json').read_text())
            legacy={k:v for k,v in original.items() if k!='quality_protocol'}
            legacy.update(schema_version='joint-luna-run-1',runner_sha256='legacy-code-hash')
            write_json(run_dir/'config.json',legacy)
            with self.assertRaisesRegex(ValueError,'Frozen run settings changed'):
                joint.run(manifest,run_dir,execute=True,resume=True,workers=1,source=self.source,corpus=local)
            upgraded=joint.run(manifest,run_dir,execute=True,resume=True,workers=1,source=self.source,corpus=local,upgrade_quality=True)
            self.assertEqual(upgraded['phase'],'completed');self.assertEqual(worker.call_count,1)
            self.assertEqual(json.loads((run_dir/'pre-quality-config.json').read_text()),legacy)
        self.assertEqual((target/'source/main.tex').read_bytes(),raw)


class CorpusQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_dynamic_priority_skips_later_chronological_duplicate(self):
        rows=[{'arxiv':f'2401.0000{i}','version':'v1'} for i in (1,2,3)]
        queue=corpus_queue.PriorityReader(self.root);count=0
        def respond(url):
            nonlocal count
            count+=1
            if count==1:corpus_queue.enqueue([{'arxiv':'2401.00003v1'}],self.root)
            return 200,b'\\documentclass{article}\nSource text.',{}
        client=FakeClient(respond)
        corpus.fetch(self.root,client,records=rows,priority_records=queue,log=lambda _:None)
        self.assertEqual([u.rsplit('/',1)[-1] for u in client.urls],['2401.00001v1','2401.00003v1','2401.00002v1'])
        corpus.fetch(self.root,client,records=rows,priority_records=queue,log=lambda _:None)
        self.assertEqual(len(client.urls),3)
        self.assertFalse(json.loads((self.root/'retention-policy.json').read_text())['delete_sources_after_extraction'])

    def test_waits_for_publication_and_verifies_preserved_bytes_and_version(self):
        with self.assertRaises(corpus_queue.AwaitingSource):corpus_queue.read_source('2401.00001v1',self.root)
        text=b'\\documentclass{article}\n\\begin{document}\n'+b'Complete source equations and representations. '*10+b'\\end{document}'
        target=corpus.paper_dir(self.root,'2401.00001','v1')
        corpus._save(target,'2401.00001','v1','single',{'main.tex':text},[],'https://arxiv.org/e-print/2401.00001v1',len(text))
        body,provenance=corpus_queue.read_source('2401.00001v1',self.root)
        self.assertIn('Complete source equations',body);self.assertTrue(provenance['corpus_meta_sha256'])
        self.assertEqual((target/'source/main.tex').read_bytes(),text)
        with self.assertRaises(corpus_queue.AwaitingSource):corpus_queue.read_source('2401.00001v2',self.root)
        (target/'source/main.tex').write_bytes(text.replace(b'equations',b'corrupted'))
        with self.assertRaisesRegex(ValueError,'hash mismatch'):corpus_queue.read_source('2401.00001v1',self.root)

    def test_malformed_queue_is_rejected(self):
        (self.root/'priority-requests.jsonl').write_text(json.dumps({'arxiv':'../bad','version':'v1','primary':'hep-ph'})+'\n')
        with self.assertRaises(ValueError):corpus_queue.requests(self.root)


if __name__=='__main__':unittest.main()
