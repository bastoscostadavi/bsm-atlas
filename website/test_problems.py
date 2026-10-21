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
from catalogue import load,validate,identity,ingest_demonstration,PROBLEM_CATEGORIES
from build_field_catalogue import main_data,database

PROBLEM={'id':'dark-matter','name':'Dark matter','category':'empirical','description':'Reproduce the observed dark-matter abundance.'}
# Shape-validation fixture only; scientific evidence is reviewed against its paper.
CLAIM={'entry_id':'real-singlet-z2','problem_id':'dark-matter','paper_id':'P01',
       'locators':['Fig. 2; Eq. (3.5)'],'result':'A calculated thermal-relic curve reproduces the target abundance under the stated assumptions.'}


class ProblemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=load()
        cls.fixture=deepcopy(cls.source)
        cls.fixture.update(problems=[deepcopy(PROBLEM)],entry_problems=[])

    def test_intake_is_idempotent_and_does_not_change_identity(self):
        before=deepcopy(self.fixture)
        after,target=ingest_demonstration(before,CLAIM)
        self.assertEqual(before,self.fixture)
        self.assertEqual(after['entries'],before['entries'])
        self.assertEqual(after['entry_problems'],[CLAIM])
        self.assertIn(CLAIM['entry_id'],target)
        self.assertEqual(ingest_demonstration(after,CLAIM)[0],after)
        conflict={**CLAIM,'result':'A different result'}
        with self.assertRaises(ValueError):ingest_demonstration(after,conflict)
        for entry in after['entries']:
            old=next(e for e in before['entries'] if e['id']==entry['id'])
            self.assertEqual(identity(entry['specification']),identity(old['specification']))

    def test_malformed_or_unrelated_evidence_is_rejected(self):
        for change in ['problem','entry','paper','unrelated-paper','empty-result','empty-locators','bad-locator','duplicate-locator','extra','missing']:
            claim=deepcopy(CLAIM)
            if change in {'problem','entry','paper'}:claim[change+'_id']='missing'
            if change=='unrelated-paper':claim['paper_id']='P10'
            if change=='empty-result':claim['result']='  '
            if change=='empty-locators':claim['locators']=[]
            if change=='bad-locator':claim['locators']=[None]
            if change=='duplicate-locator':claim['locators']*=2
            if change=='extra':claim['status']='might solve'
            if change=='missing':del claim['result']
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                ingest_demonstration(self.fixture,claim)
        for change in ['duplicate-problem','duplicate-name','unknown-field','duplicate-demonstration','unknown-category','missing-category']:
            source=deepcopy(self.fixture)
            if change=='duplicate-problem':source['problems']*=2
            if change=='duplicate-name':source['problems'].append({**PROBLEM,'id':'another-target','name':'DARK MATTER'})
            if change=='unknown-field':source['problems'][0]['label']='anything'
            if change=='duplicate-demonstration':source['entry_problems']=[CLAIM,CLAIM]
            if change=='unknown-category':source['problems'][0]['category']='aesthetic-ish'
            if change=='missing-category':del source['problems'][0]['category']
            with self.subTest(change=change),self.assertRaises(ValueError):validate(source)

    def test_multiple_papers_count_as_one_problem_link(self):
        source=deepcopy(self.fixture)
        source['entry_problems']=[deepcopy(CLAIM),{**CLAIM,'paper_id':'P02','locators':['Sec. III; Fig. 1']}]
        data=main_data(source)
        self.assertEqual(data['counts']['demonstrations'],2)
        self.assertEqual(data['counts']['problemLinks'],1)
        self.assertEqual(data['problems'][0]['entryIds'],['real-singlet-z2'])
        self.assertEqual(data['problems'][0]['paperIds'],['P01','P02'])
        entry=next(e for e in data['entries'] if e['id']=='real-singlet-z2')
        self.assertEqual(entry['problemIds'],['dark-matter'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'catalogue.sqlite';database(path,data)
            with closing(sqlite3.connect(path)) as con:
                con.execute('PRAGMA foreign_keys=ON')
                self.assertEqual(con.execute('SELECT count(*) FROM entry_problems').fetchone()[0],2)
                self.assertEqual(con.execute('SELECT count(DISTINCT problem_id) FROM entry_problems WHERE entry_id=?',('real-singlet-z2',)).fetchone()[0],1)
                self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
                self.assertEqual(con.execute('SELECT category FROM problems WHERE problem_id=?',('dark-matter',)).fetchone()[0],'empirical')
                with self.assertRaises(sqlite3.IntegrityError):con.execute("UPDATE problems SET category='unknown'")
                with self.assertRaises(sqlite3.IntegrityError):con.execute('UPDATE problems SET category=NULL')
                for statement in [
                    "UPDATE entry_problems SET paper_id='P10'",
                    "UPDATE entry_problems SET problem_id='missing'",
                    "UPDATE entry_problems SET locators_json='[]'",
                    "UPDATE entry_problems SET result=' '"]:
                    with self.subTest(statement=statement),self.assertRaises(sqlite3.IntegrityError):con.execute(statement)
                for locators in [[None],[123],[''],[' '],['\t\n'],['same','same']]:
                    with self.subTest(locators=locators),self.assertRaises(sqlite3.IntegrityError):
                        con.execute('UPDATE entry_problems SET locators_json=?',(json.dumps(locators),))
                    with self.subTest(insert=locators),self.assertRaises(sqlite3.IntegrityError):
                        con.execute('INSERT INTO entry_problems VALUES (?,?,?,?,?)',
                                    ('complex-singlet-portal','dark-matter','P02',json.dumps(locators),'Example'))

    def test_source_and_downloads_roundtrip(self):
        self.assertTrue(self.source['entry_problems'])
        data=json.loads((ROOT/'website/field-catalogue.json').read_text())
        self.assertEqual(data['entry_problems'],self.source['entry_problems'])
        with closing(sqlite3.connect(ROOT/'website/downloads/field-catalogue.sqlite')) as con:
            for problem in self.source['problems']:
                row=con.execute('SELECT name,description,category FROM problems WHERE problem_id=?',(problem['id'],)).fetchone()
                self.assertEqual(row,tuple(problem[k] for k in ['name','description','category']))
            for c in self.source['entry_problems']:
                row=con.execute('SELECT result,locators_json FROM entry_problems WHERE entry_id=? AND problem_id=? AND paper_id=?',
                                tuple(c[k] for k in ['entry_id','problem_id','paper_id'])).fetchone()
                self.assertEqual((row[0],json.loads(row[1])),(c['result'],c['locators']))
        with (ROOT/'website/downloads/entry-problems.csv').open(newline='') as handle:
            rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),len(self.source['entry_problems']))
        for row,claim in zip(rows,self.source['entry_problems']):
            self.assertEqual(json.loads(row.pop('locators_json')),claim['locators'])
            self.assertEqual(row,{k:v for k,v in claim.items() if k!='locators'})
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
        smash=[c for c in self.source['entry_problems'] if c['entry_id']=='smash-down']
        counts={category:len({c['problem_id'] for c in smash if current[c['problem_id']]==category}) for category in PROBLEM_CATEGORIES}
        self.assertEqual(counts,{'empirical':3,'structural':2,'reported_discrepancy':0})

    def test_evidence_cli_dry_run_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'catalogue.json';source.write_text(json.dumps(self.fixture))
            candidate=Path(directory)/'claim.json';candidate.write_text(json.dumps(CLAIM))
            command=[sys.executable,'-B',str(ROOT/'atlas/catalogue.py'),'--source',str(source),'--add-demonstration',str(candidate)]
            before=source.read_bytes()
            run=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(source.read_bytes(),before)
            run=subprocess.run([*command,'--write'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(load(source)['entry_problems'],[CLAIM])
            before=source.read_bytes();candidate.write_text(json.dumps({**CLAIM,'paper_id':'P10'}))
            run=subprocess.run([*command,'--write'],capture_output=True,text=True)
            self.assertEqual(run.returncode,2);self.assertEqual(source.read_bytes(),before)


if __name__=='__main__':unittest.main()
