"""Build the static explorer and relational downloads from atlas/catalogue.json."""
from contextlib import closing
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile

ROOT=Path(__file__).resolve().parent.parent
from .catalogue import load, identity, validate
from .catalogue_identity import normalize_spec
from .core_projection import attach_layers, spectrum_sort_key
from .presentation import matrix, compact_baseline
from .field_conventions import REPRESENTATION_CONVENTION

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
    entries.sort(key=lambda entry:spectrum_sort_key(entry['identity']['canonical'])+(entry['id'],))
    paper_entries={p['id']:[] for p in source['papers']}
    for entry in entries:
        for paper_id in entry['paperIds']:
            paper_entries[paper_id].append(entry['id'])
    papers=[{**p,'entryIds':sorted(paper_entries[p['id']])} for p in source['papers']]
    return {'version':VERSION,'schema_version':'bsm-atlas-export-1','representationConvention':REPRESENTATION_CONVENTION,
        'entries':entries,'papers':papers,'templates':templates,'cores':cores,
        'semisimpleAlgebras':algebras,'fullAlgebras':full,
        'counts':{'entries':len(entries),'papers':len(papers),'linkedPapers':sum(bool(p['entryIds']) for p in papers),
                  'cores':len(cores),'semisimpleAlgebras':len(algebras),'fullAlgebras':len(full)}}

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
            extractor=p.get('extractor',{})
            con.execute('INSERT INTO papers VALUES (?,?,?,?,?,?,?,?)',
                (*[p[k] for k in ['id','arxiv','title','authors']],
                 p.get('extraction_status','not_started'),
                 extractor.get('provider'),extractor.get('model'),extractor.get('reasoning')))
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
        con.commit()
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or con.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Invalid relational catalogue')

def version_script_assets(html,assets):
    """Version each expected script once, using the bytes that will be served."""
    from hashlib import sha256
    from html import escape
    from html.parser import HTMLParser
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    offsets=[0]
    for line in html.splitlines(keepends=True):offsets.append(offsets[-1]+len(line))
    versions={name:sha256(content).hexdigest()[:16] for name,content in assets.items()}
    counts={name:0 for name in assets};replacements=[]

    class Scripts(HTMLParser):
        def handle_starttag(self,tag,attrs):
            self.script(tag,attrs,False)

        def handle_startendtag(self,tag,attrs):
            self.script(tag,attrs,True)

        def script(self,tag,attrs,closed):
            if tag!='script':return
            sources=[value for name,value in attrs if name=='src']
            for source in sources:
                if source is None:continue
                url=urlsplit(source);name=url.path.removeprefix('./')
                if url.scheme or url.netloc or name not in versions:continue
                if len(sources)!=1:raise ValueError('Duplicate src attribute for '+name)
                counts[name]+=1
                query=[(key,value) for key,value in parse_qsl(url.query,keep_blank_values=True) if key!='v']
                query.append(('v',versions[name]))
                source=urlunsplit((url.scheme,url.netloc,url.path,urlencode(query),url.fragment))
                updated='<script'+''.join(' '+key+('="'+escape(source if key=='src' else value,quote=True)+'"' if value is not None else '') for key,value in attrs)+(' />' if closed else '>')
                line,column=self.getpos();start=offsets[line-1]+column
                replacements.append((start,start+len(self.get_starttag_text()),updated))

    parser=Scripts();parser.feed(html);parser.close()
    for name,count in counts.items():
        if count!=1:raise ValueError('Expected one script reference to '+name+', found '+str(count))
    for start,end,replacement in reversed(replacements):html=html[:start]+replacement+html[end:]
    return html


def write_outputs(data,check=False):
    payload=encoded(data)+'\n'
    outputs={'website/catalogue.json':(ROOT/'atlas/catalogue.json').read_text(encoding='utf-8'),
        'website/field-catalogue.json':payload,
        'website/field-catalogue-data.js':'window.FIELD_CATALOGUE = '+payload.rstrip()+';\n',
        'website/entry.schema.json':(ROOT/'atlas/entry.schema.json').read_text(),
        'website/catalogue.schema.json':(ROOT/'atlas/catalogue.schema.json').read_text(),
        'website/downloads/field-catalogue.csv':csv_text(['entry_id','name','gauge_algebra','paper_ids','fingerprint','specification_json'],
            ([e['id'],e['name'],e['algebraExpanded'],';'.join(e['paperIds']),e['identity']['fingerprint'],encoded(e['specification'])] for e in data['entries']))}
    for kind,file in [('cores','nonabelian-cores'),('semisimpleAlgebras','semisimple-algebras'),('fullAlgebras','full-gauge-algebras')]:
        outputs['website/downloads/'+file+'.csv']=csv_text(['id','gauge_algebra','entry_ids','canonical_json'],
            ([g['id'],g['algebra'],';'.join(g['entryIds']),encoded(g['canonical'])] for g in data[kind]))
    outputs['website/index.html']=version_script_assets((ROOT/'website/index.html').read_text(encoding='utf-8'),{
        'field-catalogue-data.js':outputs['website/field-catalogue-data.js'].encode('utf-8'),
        'field-catalogue.js':(ROOT/'website/field-catalogue.js').read_bytes()})
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
