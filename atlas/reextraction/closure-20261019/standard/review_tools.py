"""Read-only artifact assembly for independently checked October 19 source scopes.

Prints file contents for apply_patch; never edits frozen/source/public data.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'atlas')]
from prepare_entry import prepare
from catalogue_identity import normalize_spec, canonicalize

DEST = Path('atlas/reextraction/closure-20261019/standard')

def assemble(config):
    files = {}
    data = json.loads(subprocess.check_output(['git','show','9d8017b:website/field-catalogue.json'],cwd=ROOT))
    entries = {x['id']: x for x in data['entries']}
    papers = {x['id']: x for x in data['papers']}
    for decision in config:
        entry = entries[decision['entry']]
        d = deepcopy(decision)
        d.update(paper=d.get('paper', entry['paperIds'][0]), regime=entry['primaryRegime'])
        d['arxiv'] = papers[d['paper']]['arxiv']
        d.setdefault('limitations', [])
        d['source_pdfs'] = []
        for source in d.pop('sources'):
            raw = (ROOT / source['path']).read_bytes()
            d['source_pdfs'].append({**source, 'sha256': sha256(raw).hexdigest()})
        stem = DEST / d['entry']
        if d['decision'] == 'accept':
            old = ROOT / 'atlas/reextraction/followup-20261016'
            if 'candidate' in d:
                source = d.pop('candidate')
                mapping = d.pop('source_field_mapping')
            else:
                source = json.loads((old / (d['entry'] + '-source-candidate.json')).read_text())
                prior = json.loads((old / (d['entry'] + '-evidence.json')).read_text())
                mapping = prior['source_field_mapping']
                d['claims'] = prior.get('claims',[]) + d['claims']
                d['previous_evidence_lead'] = str((old / (d['entry'] + '-evidence.json')).relative_to(ROOT))
            source['schema_version'] = 'field-content-2'
            source['paper_ids'] = d.get('paper_ids', [d['paper']])
            report = prepare(source, ROOT / 'website/downloads/field-catalogue.sqlite')
            normalized = report['normalized_entry']
            if normalize_spec(normalized) != normalized:
                raise AssertionError('Normalizer is not idempotent')
            d.update(source_path=str(stem)+'-source.json', normalized_path=str(stem)+'-normalized.json',
                     evidence_path=str(stem)+'-evidence.json', fields_path=str(stem)+'-fields.json',
                     preflight_path=str(stem)+'-preflight.json', fingerprint=canonicalize(normalized)['fingerprint'],
                     normalizer_idempotent=True)
            evidence = deepcopy(d)
            evidence.update(target_entry_id=d['entry'], paper_id=d['paper'], arxiv_version=d['arxiv'],
                source_field_mapping=mapping, description_regime={'source_regime_id': d['regime'],
                'description':d['inspected_scope']}, review='fresh_definition_scope_source_check_20261019',
                whole_paper_read=False)
            rows=[]
            offset=0
            for row, item in zip(source['matter'], mapping, strict=True):
                count=len(normalize_spec({**source, 'matter':[row]})['matter'])
                selected=normalized['matter'][offset:offset+count]
                offset+=count
                rows.append({'source_row':row,'normalized_components':selected,'mapping':item})
            for suffix, value in [('source',source),('normalized',normalized),('evidence',evidence),
                                  ('fields',{'target_entry_id':d['entry'],'rows':rows}),('preflight',report)]:
                files[str(stem)+'-'+suffix+'.json']=value
        files[str(stem)+'-decision.json']=d
    return files

if __name__ == '__main__':
    config=json.loads(Path(sys.argv[1]).read_text())
    if len(sys.argv)>2: config=[x for x in config if x['entry']==sys.argv[2]]
    print(json.dumps(assemble(config),ensure_ascii=False))
