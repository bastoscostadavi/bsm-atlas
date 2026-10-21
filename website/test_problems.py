"""Problem evidence stays source-linked and separate from mathematical identity."""
from contextlib import closing
from copy import deepcopy
import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'atlas'),str(ROOT/'website')]
from catalogue import load,validate,identity,ingest_problem_link,PROBLEM_CATEGORIES
from build_field_catalogue import main_data,database

PROBLEM={'id':'dark-matter','name':'Dark matter','category':'empirical'}
# Shape-validation fixture only; scientific evidence is reviewed against its paper.
CLAIM={'model_id':'real-singlet-z2','problem_id':'dark-matter','paper_id':'P01'}


class ProblemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=load()
        cls.fixture=deepcopy(cls.source)
        cls.fixture.update(problems=[deepcopy(PROBLEM)],model_problems=[])

    def test_intake_is_idempotent_and_does_not_change_identity(self):
        before=deepcopy(self.fixture)
        after,target=ingest_problem_link(before,CLAIM)
        self.assertEqual(before,self.fixture)
        self.assertEqual(after['entries'],before['entries'])
        self.assertEqual(after['model_problems'],[CLAIM])
        self.assertIn(CLAIM['model_id'],target)
        self.assertEqual(ingest_problem_link(after,CLAIM)[0],after)
        for entry in after['entries']:
            old=next(e for e in before['entries'] if e['id']==entry['id'])
            self.assertEqual(identity(entry['specification']),identity(old['specification']))

    def test_malformed_or_unrelated_evidence_is_rejected(self):
        for change in ['problem','model','paper','unrelated-paper','null','blank','result','locators','boolean','missing']:
            claim=deepcopy(CLAIM)
            if change in {'problem','model','paper'}:claim[change+'_id']='missing'
            if change=='unrelated-paper':claim['paper_id']='P10'
            if change=='null':claim['model_id']=None
            if change=='blank':claim['model_id']=' '
            if change=='result':claim['result']='A result'
            if change=='locators':claim['locators']=['Fig. 2']
            if change=='boolean':claim['solves']=1
            if change=='missing':del claim['paper_id']
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                ingest_problem_link(self.fixture,claim)
        for change in ['duplicate-problem','duplicate-name','unknown-field','description','duplicate-link','unknown-category','missing-category']:
            source=deepcopy(self.fixture)
            if change=='duplicate-problem':source['problems']*=2
            if change=='duplicate-name':source['problems'].append({**PROBLEM,'id':'another-target','name':'DARK MATTER'})
            if change=='unknown-field':source['problems'][0]['label']='anything'
            if change=='description':source['problems'][0]['description']='Not stored'
            if change=='duplicate-link':source['model_problems']=[CLAIM,CLAIM]
            if change=='unknown-category':source['problems'][0]['category']='aesthetic-ish'
            if change=='missing-category':del source['problems'][0]['category']
            with self.subTest(change=change),self.assertRaises(ValueError):validate(source)

    def test_multiple_papers_count_as_one_problem_link(self):
        source=deepcopy(self.fixture)
        source['model_problems']=[deepcopy(CLAIM),{**CLAIM,'paper_id':'P02'}]
        data=main_data(source)
        self.assertEqual(data['counts']['problemReferences'],2)
        self.assertEqual(data['counts']['problemLinks'],1)
        self.assertEqual(data['problems'][0]['entryIds'],['real-singlet-z2'])
        self.assertEqual(data['problems'][0]['paperIds'],['P01','P02'])
        entry=next(e for e in data['entries'] if e['id']=='real-singlet-z2')
        self.assertEqual(entry['problemIds'],['dark-matter'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'catalogue.sqlite';database(path,data)
            with closing(sqlite3.connect(path)) as con:
                con.execute('PRAGMA foreign_keys=ON')
                self.assertEqual(con.execute('SELECT count(*) FROM model_problems').fetchone()[0],2)
                self.assertEqual(con.execute('SELECT count(DISTINCT problem_id) FROM model_problems WHERE model_id=?',('real-singlet-z2',)).fetchone()[0],1)
                self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
                self.assertEqual(con.execute('SELECT category FROM problems WHERE problem_id=?',('dark-matter',)).fetchone()[0],'empirical')
                with self.assertRaises(sqlite3.IntegrityError):con.execute("UPDATE problems SET category='unknown'")
                with self.assertRaises(sqlite3.IntegrityError):con.execute('UPDATE problems SET category=NULL')
                matrix=dict(con.execute('SELECT model_id,solves FROM model_problem_matrix'))
                self.assertEqual(len(matrix),len(source['entries']))
                self.assertEqual(matrix['real-singlet-z2'],1)
                self.assertEqual(sum(matrix.values()),1)
                self.assertEqual(matrix['two-higgs-doublets'],0)
                for statement in [
                    "UPDATE model_problems SET paper_id='P10'",
                    "UPDATE model_problems SET problem_id='missing'",
                    "UPDATE model_problems SET model_id='missing'",
                    'UPDATE model_problems SET model_id=NULL',
                    "INSERT INTO model_problems VALUES ('real-singlet-z2','dark-matter','P01')"]:
                    with self.subTest(statement=statement),self.assertRaises(sqlite3.IntegrityError):con.execute(statement)

    def test_source_and_downloads_roundtrip(self):
        self.assertTrue(self.source['model_problems'])
        data=json.loads((ROOT/'website/field-catalogue.json').read_text())
        self.assertEqual(data['model_problems'],self.source['model_problems'])
        for p in self.source['problems']:self.assertEqual(set(p),{'id','name','category'})
        for c in self.source['model_problems']:self.assertEqual(set(c),set(CLAIM))
        with closing(sqlite3.connect(ROOT/'website/downloads/field-catalogue.sqlite')) as con:
            self.assertEqual([r[1] for r in con.execute('PRAGMA table_info(problems)')],['problem_id','name','category'])
            self.assertEqual([r[1] for r in con.execute('PRAGMA table_info(model_problems)')],list(CLAIM))
            for p in self.source['problems']:
                self.assertEqual(con.execute('SELECT name,category FROM problems WHERE problem_id=?',(p['id'],)).fetchone(),(p['name'],p['category']))
            rows=con.execute('SELECT model_id,problem_id,paper_id FROM model_problems').fetchall()
            self.assertEqual(set(rows),{tuple(c[k] for k in CLAIM) for c in self.source['model_problems']})
            matrix=con.execute('SELECT model_id,problem_id,solves FROM model_problem_matrix').fetchall()
            pairs={(c['model_id'],c['problem_id']) for c in self.source['model_problems']}
            self.assertEqual(len(matrix),len(self.source['entries'])*len(self.source['problems']))
            self.assertEqual({(m,p) for m,p,value in matrix if value},pairs)
            self.assertEqual({value for _,_,value in matrix},{0,1})
        with (ROOT/'website/downloads/model-problems.csv').open(newline='') as handle:
            self.assertEqual(list(csv.DictReader(handle)),self.source['model_problems'])
        self.assertFalse((ROOT/'website/downloads/entry-problems.csv').exists())
        with (ROOT/'website/downloads/problems.csv').open(newline='') as handle:
            problems=list(csv.DictReader(handle))
        self.assertEqual(problems,[{'problem_id':p['id'],**{k:v for k,v in p.items() if k!='id'}} for p in self.source['problems']])

    def test_categories_partition_targets_not_model_identity(self):
        current={p['id']:p['category'] for p in self.source['problems']}
        expected={
            'empirical':{'dark-matter','neutrino-masses','baryon-asymmetry'},
            'structural':{'charged-fermion-flavour','electroweak-hierarchy','gauge-coupling-unification','strong-cp','cosmic-inflation'},
            'reported_discrepancy':{'b-meson-cp-asymmetries','bottom-forward-backward-asymmetry'}}
        self.assertEqual(set(expected),PROBLEM_CATEGORIES)
        schema=json.loads((ROOT/'atlas/catalogue.schema.json').read_text())
        self.assertEqual(set(schema['$defs']['problem']['properties']['category']['enum']),PROBLEM_CATEGORIES)
        for category,ids in expected.items():
            for problem_id in ids:self.assertEqual(current[problem_id],category)
        smash=[c for c in self.source['model_problems'] if c['model_id']=='smash-down']
        counts={category:len({c['problem_id'] for c in smash if current[c['problem_id']]==category}) for category in PROBLEM_CATEGORIES}
        self.assertEqual(counts,{'empirical':3,'structural':2,'reported_discrepancy':0})

    def test_evidence_cli_dry_run_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'catalogue.json';source.write_text(json.dumps(self.fixture))
            candidate=Path(directory)/'claim.json';candidate.write_text(json.dumps(CLAIM))
            command=[sys.executable,'-B',str(ROOT/'atlas/catalogue.py'),'--source',str(source),'--add-problem-link',str(candidate)]
            before=source.read_bytes()
            run=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(source.read_bytes(),before)
            run=subprocess.run([*command,'--write'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(load(source)['model_problems'],[CLAIM])
            before=source.read_bytes();candidate.write_text(json.dumps({**CLAIM,'paper_id':'P10'}))
            run=subprocess.run([*command,'--write'],capture_output=True,text=True)
            self.assertEqual(run.returncode,2);self.assertEqual(source.read_bytes(),before)


if __name__=='__main__':unittest.main()
