"""Fake Claude workers test protocol, isolation, provenance and cleanup offline."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import io

from bsm_atlas import harvest, claude_worker
from bsm_atlas.expansion import expand_batch
from bsm_atlas.catalogue import load, write_json
from bsm_atlas.retention import cleanup_run, compact_record
from tests.test_harvest import BODY, result


class ClaudeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.run = self.root/'catalogue.json', self.root/'run'
        write_json(self.source, {'schema_version':'bsm-atlas-1','papers':[],'entries':[]})
        (self.root/'paper.txt').write_text(BODY)
        self.manifest = self.root/'papers.json'
        write_json(self.manifest, {'papers':[{'arxiv':'2501.00001v1', 'title':'Fixture',
            'authors':'Author', 'text':'paper.txt'}]})
        harvest.prepare_batch(self.manifest, self.run, source=self.source)

    def fake(self, payload=None, error=False, structured=True):
        payload = result() if payload is None else payload
        event = {'type':'result','subtype':'error_during_execution' if error else 'success',
            'is_error':error, 'result':'capacity limit' if error else '',
            'usage':None if error else {'input_tokens':100,'output_tokens':20,
                'cache_read_input_tokens':30,'cache_creation_input_tokens':10},
            'modelUsage':{'claude-fixture-20261027':{}}}
        if structured:
            event['structured_output'] = payload
        path = self.root/'fake-claude'
        path.write_text('#!'+sys.executable+'\nimport json,sys\n'
            'if "--help" in sys.argv:\n'
            ' print("--print --json-schema --output-format --no-session-persistence --safe-mode --tools --strict-mcp-config --effort");sys.exit(0)\n'
            'assert "--safe-mode" in sys.argv and "--no-session-persistence" in sys.argv\n'
            'assert sys.argv[sys.argv.index("--tools")+1]==""\n'
            'assert json.loads(sys.argv[sys.argv.index("--mcp-config")+1])=={"mcpServers":{}}\n'
            'assert "BEGIN PAPER CONTENT" in sys.stdin.read()\n'
            'print('+repr(json.dumps(event))+')\n'
            'sys.exit('+str(1 if error else 0)+')\n')
        path.chmod(0o700)
        return path

    def run_fake(self, **kwargs):
        return harvest.run_batch(self.run, execute=True, provider='claude',
            model='claude-fixture', executable=self.fake(**kwargs), reasoning='medium', workers=1)

    def test_success_uses_shared_ingestion_and_survives_cleanup(self):
        report = self.run_fake()
        self.assertEqual(report['counts'], {'ingested':1})
        self.assertEqual(report['usage']['input_tokens'], 140)
        data = load(self.source)
        self.assertEqual(len(data['entries']), 1)
        self.assertEqual(data['papers'][0]['extractor'], {'provider':'anthropic',
            'model':'claude-fixture-20261027','reasoning':'medium'})
        cleanup_run(self.run,source=self.source,write=True)
        job=self.run/'jobs/2501.00001v1'
        self.assertFalse((job/'prompt.txt').exists())
        self.assertEqual(compact_record(job)['extractor'],data['papers'][0]['extractor'])
        self.assertEqual(harvest.run_batch(self.run,provider='claude')['jobs'],[])

    def test_skip_still_records_extractor(self):
        self.run_fake(payload=result(outcome='skip'))
        data=load(self.source)
        self.assertEqual(data['entries'],[])
        self.assertEqual(data['papers'][0]['extractor']['provider'],'anthropic')

    def test_failure_is_not_a_scientific_skip(self):
        report=self.run_fake(error=True)
        self.assertEqual(report['counts'],{'retry':1})
        self.assertNotIn('extractor',load(self.source)['papers'][0])
        self.assertEqual(load(self.source)['entries'],[])

    def test_missing_structured_output_is_retriable_not_accepted(self):
        report=self.run_fake(structured=False)
        self.assertEqual(report['counts'],{'retry':1})
        self.assertEqual(load(self.source)['entries'],[])

    def test_explicit_model_and_size_guard(self):
        with self.assertRaisesRegex(ValueError,'explicit Claude'):
            claude_worker.command('claude',self.run/'result.schema.json','sonnet','medium')
        job=self.run/'jobs/2501.00001v1'
        # The payload is re-sealed through preparation in a new fixture run.
        (self.root/'paper.txt').write_text('x'*(claude_worker.MAX_PROMPT+1))
        other=self.root/'large-run'
        harvest.prepare_batch(self.manifest,other,source=self.source)
        report=harvest.run_batch(other,execute=True,provider='claude',model='claude-fixture',
                                 executable=self.fake(),workers=1)
        self.assertEqual(report['counts'],{'retry':1})
        self.assertFalse(list((other/'jobs/2501.00001v1').glob('attempt-*')))

    def test_expansion_and_resume_keep_provider_and_do_not_repeat_calls(self):
        executable=self.fake(payload=result(outcome='skip'))
        run=self.root/'expanded'
        with redirect_stdout(io.StringIO()):
            report=expand_batch(self.manifest,run,execute=True,source=self.source,
                provider='claude',model='claude-fixture',executable=executable,workers=1,fetch_size=1)
        self.assertEqual(report['phase'],'extraction_complete')
        self.assertEqual(json.loads((run/'expansion.json').read_text())['config']['provider'],'claude')
        before=list(run.glob('jobs/*/attempt-*/metrics.json'))
        with redirect_stdout(io.StringIO()):
            again=expand_batch(self.manifest,run,execute=True,resume=True,source=self.source,
                provider='claude',model='claude-fixture',executable=executable,workers=1,fetch_size=1)
        self.assertEqual(again['phase'],'extraction_complete')
        self.assertEqual(before,list(run.glob('jobs/*/attempt-*/metrics.json')))

    def test_codex_and_claude_concurrent_writers_merge_one_model(self):
        codex=self.root/'fake-codex';payload=json.dumps(result())
        codex.write_text('#!'+sys.executable+'\nimport json,pathlib,sys\n'
            'if "--help" in sys.argv:\n'
            ' print("--output-schema --output-last-message --json --ignore-user-config --ephemeral");sys.exit(0)\n'
            'sys.stdin.read()\n'
            'pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text('+repr(payload)+')\n'
            'print(json.dumps({"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}))\n')
        codex.chmod(0o700)
        second=self.root/'second.json'
        write_json(second,{'papers':[{'arxiv':'2501.00002v1','title':'Other paper',
                                    'authors':'Author','text':'paper.txt'}]})
        claude=self.fake()
        with redirect_stdout(io.StringIO()),ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(expand_batch,self.manifest,self.root/'codex-expanded',execute=True,
                source=self.source,executable=codex,workers=1,fetch_size=1)
            b=pool.submit(expand_batch,second,self.root/'claude-expanded',execute=True,
                source=self.source,provider='claude',model='claude-fixture',executable=claude,workers=1,fetch_size=1)
            self.assertEqual(a.result()['phase'],'extraction_complete')
            self.assertEqual(b.result()['phase'],'extraction_complete')
        data=load(self.source)
        self.assertEqual(len(data['entries']),1)
        self.assertEqual(len(data['entries'][0]['references']),2)
        self.assertEqual({p['extractor']['provider'] for p in data['papers']},{'openai','anthropic'})
