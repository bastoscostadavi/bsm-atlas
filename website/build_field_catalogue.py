#!/usr/bin/env python3
"""Build the static explorer and relational downloads from atlas/catalogue.json."""
import argparse
from contextlib import closing
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'atlas'),str(ROOT/'website')]
from catalogue import load, identity, validate
from catalogue_identity import normalize_spec
from core_projection import attach_layers
from presentation import matrix, compact_baseline
from field_conventions import REPRESENTATION_CONVENTION

VERSION='gauge-matter-13'

def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def main_data(source=None):
    source=load() if source is None else validate(source)
    entries=[]
    for item in source['entries']:
        entry=deepcopy(item); spec=entry['specification']; key=identity(spec)
        entry['identity']={'fingerprint':key['fingerprint'],'canonical':json.loads(key['canonical_json'])}
        entry['paperIds']=[ref['paper_id'] for ref in entry['references']]
        entry['problemIds']=sorted({c['problem_id'] for c in source['entry_problems'] if c['entry_id']==entry['id']})
        entry['regime']=matrix(spec)
        entry['algebraExpanded']=' ⊕ '.join(a['label'] for a in entry['regime']['factors'])
        entry['algebraSignature']='+'.join(sorted(a['id'] for a in entry['regime']['factors']))
        entries.append(entry)
    cores,algebras,full=attach_layers(entries)
    templates={}
    for code,t in json.loads((ROOT/'atlas/reference_spectra.json').read_text()).items():
        s=normalize_spec(t['specification'])
        if s!=t['specification']:raise ValueError('Reference spectrum must be normalized')
        templates[code]={'name':t['name'],**matrix(s)}
    templates['F_SM']={**templates['R_SM'],'name':'SM fermions','rows':[r for r in templates['R_SM']['rows'] if r['lorentz']['component']!='S']}
    templates['H_SM']={**templates['R_SM'],'name':'SM Higgs','rows':[r for r in templates['R_SM']['rows'] if r['lorentz']['component']=='S']}
    for entry in entries:compact_baseline(entry['regime'],templates)
    papers=[{**p,'entryIds':sorted(e['id'] for e in entries if p['id'] in e['paperIds'])} for p in source['papers']]
    problems=[{**p,'entryIds':sorted({c['entry_id'] for c in source['entry_problems'] if c['problem_id']==p['id']}),
               'paperIds':sorted({c['paper_id'] for c in source['entry_problems'] if c['problem_id']==p['id']})}
              for p in source['problems']]
    return {'version':VERSION,'schema_version':'bsm-atlas-export-2','representationConvention':REPRESENTATION_CONVENTION,
        'entries':entries,'papers':papers,'templates':templates,'cores':cores,
        'problems':problems,'entry_problems':deepcopy(source['entry_problems']),
        'semisimpleAlgebras':algebras,'fullAlgebras':full,
        'counts':{'entries':len(entries),'papers':len(papers),'linkedPapers':sum(bool(p['entryIds']) for p in papers),
                  'cores':len(cores),'semisimpleAlgebras':len(algebras),'fullAlgebras':len(full),
                  'problems':len(problems),'demonstrations':len(source['entry_problems']),
                  'problemLinks':len({(c['entry_id'],c['problem_id']) for c in source['entry_problems']})}}

def csv_text(headers,rows):
    out=io.StringIO(newline='')
    writer=csv.writer(out,lineterminator='\n');writer.writerow(headers);writer.writerows(rows)
    return out.getvalue()

def database(path,data):
    with closing(sqlite3.connect(path)) as con:
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript((ROOT/'atlas/schema.sql').read_text())
        con.execute('INSERT INTO metadata VALUES (?,?)',('convention',VERSION))
        for p in data['papers']:
            con.execute('INSERT INTO papers VALUES (?,?,?,?)',tuple(p[k] for k in ['id','arxiv','title','authors']))
        for p in data['problems']:
            con.execute('INSERT INTO problems VALUES (?,?,?)',tuple(p[k] for k in ['id','name','description']))
        for a in data['semisimpleAlgebras']:
            con.execute('INSERT INTO semisimple_algebras VALUES (?,?,?)',(a['id'],a['algebra'],encoded(a['canonical'])))
        for a in data['fullAlgebras']:
            con.execute('INSERT INTO full_gauge_algebras VALUES (?,?,?,?,?)',(a['id'],a['algebra'],a['semisimpleId'],a['abelianRank'],encoded(a['canonical'])))
        for c in data['cores']:
            con.execute('INSERT INTO nonabelian_cores VALUES (?,?,?,?)',(c['id'],c['algebra'],c['semisimpleId'],encoded(c['canonical'])))
        for e in data['entries']:
            s=e['specification']
            con.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)',
                (e['id'],e['name'],s['schema_version'],encoded(s),e['identity']['fingerprint'],e['semisimpleId'],e['fullAlgebraId'],e['coreId']))
            for ref in e['references']:
                con.execute('INSERT INTO entry_papers VALUES (?,?,?,?)',(e['id'],ref['paper_id'],encoded(ref.get('locators',[])),encoded(ref.get('parameter_names',{}))))
            for alias in e.get('aliases',[]):
                con.execute('INSERT INTO aliases VALUES (?,?,?)',(alias['id'],e['id'],alias['name']))
            for position,a in enumerate(s['gauge_factors']):
                con.execute('INSERT INTO gauge_factors VALUES (?,?,?,?,?)',(e['id'],a['id'],position,a['family'],a['rank']))
            for name,declaration in s.get('parameters',{}).items():
                con.execute('INSERT INTO entry_parameters VALUES (?,?,?)',(e['id'],name,declaration['domain']))
            for i,expression in enumerate(s.get('constraints',[])):
                con.execute('INSERT INTO entry_constraints VALUES (?,?,?)',(e['id'],i,expression))
            for i,f in enumerate(s['matter']):
                con.execute('INSERT INTO matter VALUES (?,?,?,?,?)',(e['id'],i,encoded(f['lorentz']),f['reality'],f['copies']))
                for a in s['gauge_factors']:
                    r=f['gauge_representations'][a['id']];symbolic=s['schema_version']=='field-content-3'
                    con.execute('INSERT INTO matter_representations VALUES (?,?,?,?,?,?)',
                        (e['id'],i,a['id'],encoded(r['dynkin']) if 'dynkin' in r else None,
                         r.get('charge') if not symbolic else None,r.get('charge') if symbolic else None))
        for c in data['entry_problems']:
            con.execute('INSERT INTO entry_problems VALUES (?,?,?,?,?)',
                        (c['entry_id'],c['problem_id'],c['paper_id'],encoded(c['locators']),c['result']))
        con.commit()
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or con.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Invalid relational catalogue')

def write_outputs(data,check=False):
    payload=encoded(data)+'\n'
    outputs={'website/catalogue.json':(ROOT/'atlas/catalogue.json').read_text(encoding='utf-8'),
        'website/field-catalogue.json':payload,'atlas/FIELD_CONTENT_CATALOGUE.json':payload,
        'website/field-catalogue-data.js':'window.FIELD_CATALOGUE = '+payload.rstrip()+';\n',
        'website/entry.schema.json':(ROOT/'atlas/entry.schema.json').read_text(),
        'website/catalogue.schema.json':(ROOT/'atlas/catalogue.schema.json').read_text(),
        'website/downloads/field-catalogue.csv':csv_text(['entry_id','name','gauge_algebra','paper_ids','problem_ids','fingerprint','specification_json'],
            ([e['id'],e['name'],e['algebraExpanded'],';'.join(e['paperIds']),';'.join(e['problemIds']),e['identity']['fingerprint'],encoded(e['specification'])] for e in data['entries'])),
        'website/downloads/problems.csv':csv_text(['problem_id','name','description'],
            ([p['id'],p['name'],p['description']] for p in data['problems'])),
        'website/downloads/entry-problems.csv':csv_text(['entry_id','problem_id','paper_id','result','locators_json'],
            ([c['entry_id'],c['problem_id'],c['paper_id'],c['result'],encoded(c['locators'])] for c in data['entry_problems']))}
    for kind,file in [('cores','nonabelian-cores'),('semisimpleAlgebras','semisimple-algebras'),('fullAlgebras','full-gauge-algebras')]:
        outputs['website/downloads/'+file+'.csv']=csv_text(['id','gauge_algebra','entry_ids','canonical_json'],
            ([g['id'],g['algebra'],';'.join(g['entryIds']),encoded(g['canonical'])] for g in data[kind]))
    for relative,content in outputs.items():
        path=ROOT/relative
        if check:
            if not path.exists() or path.read_text()!=content:raise ValueError('Stale generated file: '+relative)
        else:path.write_text(content,encoding='utf-8')
    target=ROOT/'website/downloads/field-catalogue.sqlite'
    with tempfile.TemporaryDirectory() as directory:
        temporary=Path(directory)/'catalogue.sqlite';database(temporary,data)
        if check:
            with closing(sqlite3.connect(temporary)) as new,closing(sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True)) as old:
                if list(new.iterdump())!=list(old.iterdump()):raise ValueError('Stale relational export')
        else:target.write_bytes(temporary.read_bytes())
    print('Catalogue:',data['counts'],'(verified)' if check else '(built)')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();write_outputs(main_data(),args.check)
