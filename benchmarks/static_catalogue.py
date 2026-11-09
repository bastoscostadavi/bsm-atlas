#!/usr/bin/env python3
"""Stress the delivery format with synthetic spectra and papers, never atlas intake."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.build import main_data
from bsm_atlas.web_bundle import make_bundle


def run(paper_count=100000, model_count=5000):
    assert paper_count >= 10 * model_count and paper_count <= 1000000
    base = next(e for e in json.loads((ROOT / 'atlas/catalogue.json').read_text())['entries'] if e['id'] == 'real-singlet-z2')
    entries = []
    for index in range(model_count):
        entry = deepcopy(base);entry.update(id=f'benchmark-model-{index}',name=f'Synthetic benchmark model {index}',references=[]);entry.pop('aliases', None)
        for field in entry['specification']['matter']:
            if field['lorentz']['irreps'] == [['0', '0']] and all(all(x == 0 for x in rep['dynkin']) if 'dynkin' in rep else rep['charge'] == '0' for rep in field['gauge_representations'].values()):
                field['copies'] = index + 1
        entries.append(entry)
    papers, associations = [], []
    for index in range(paper_count):
        identifier = f'benchmark-paper-{index}'
        paper = {'id': identifier, 'arxiv': f'26{1 + index // 90000:02d}.{1 + index % 90000:05d}v1',
                 'title': f'Synthetic benchmark {"quasar" if index % 100 == 0 else "dark"} study {index}',
                 'authors': f'Benchmark Researcher {index % 1000}', 'extraction_status': 'complete'}
        papers.append(paper)
        if index % 5 == 0:
            chosen = 0 if (index // 5) % 2 == 0 else 1 + ((index // 10) % (model_count - 1))
            entries[chosen]['references'].append({'paper_id': identifier})
            if chosen == 0:
                associations.append({'paperId': identifier, 'rationale': 'Synthetic transport benchmark only.',
                                     'evidence': [{'quote': 'Synthetic fixture', 'locator': 'benchmark'}],
                                     'needsReview': False, 'reviewReasons': []})
    source = {'schema_version': 'bsm-atlas-1', 'papers': papers, 'entries': entries}
    started = time.monotonic();data = main_data(source)
    annotation = {'categories': [{'id': 'synthetic', 'label': 'Synthetic benchmark'}],
                  'assessed': [e['id'] for e in entries], 'links': {}}
    problems = {**annotation, 'problems': [{'id': 'dark_matter', 'category_id': 'synthetic', 'label': 'Synthetic benchmark'}],
                'links': {'benchmark-model-0': {'dark_matter': associations}}}
    mechanisms = {**annotation, 'mechanisms': []}
    files = make_bundle(data, {'problems': problems, 'mechanisms': mechanisms}, source_sha256=sha256(b'synthetic benchmark').hexdigest())
    build_seconds = time.monotonic() - started
    manifest = next(name for name in files if name.startswith('data/manifest-'))
    with tempfile.TemporaryDirectory(prefix='atlas-scale-benchmark-') as directory:
        target = Path(directory)
        for name, raw in files.items():
            path = target / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(raw)
        output = subprocess.check_output(['node', str(ROOT / 'benchmarks/probe.mjs'), str(target), str(ROOT / 'website/atlas-store.js'), manifest], text=True)
    result = {'kind': 'synthetic transport benchmark; not extracted scientific data', 'papers': paper_count,
              'models': model_count, 'linked_paper_fraction': 0.2, 'build_seconds': round(build_seconds, 3),
              'data_files': len(files), 'total_data_bytes': sum(map(len, files.values())), **json.loads(output)}
    (ROOT / 'benchmarks/scalability.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--papers', type=int, default=100000);parser.add_argument('--models', type=int, default=5000)
    args = parser.parse_args();run(args.papers, args.models)
