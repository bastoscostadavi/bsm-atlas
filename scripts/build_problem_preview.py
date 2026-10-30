#!/usr/bin/env python3
"""Export the frozen Luna annotations as a separate website preview layer."""
import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/problem-mapping-luna'
EXCLUDED_CATEGORIES = {'established_theory_dynamics'}


def payload():
    catalogue = json.loads((ROOT / 'atlas/catalogue.json').read_text())
    entries = {e['id']: e for e in catalogue['entries']}
    manifest = json.loads((RUN / 'manifest.json').read_text())
    frozen = {m['id']: m for p in manifest['papers'] for m in p['models']}
    taxonomy = json.loads((RUN / 'problems.json').read_text())
    categories = [c for c in taxonomy['categories'] if c['id'] not in EXCLUDED_CATEGORIES]
    problems = [p for p in taxonomy['problems'] if p['category_id'] not in EXCLUDED_CATEGORIES]
    visible_problems = {p['id'] for p in problems}
    assessed = set()
    with (RUN / 'classifications.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['processing_state'] == 'completed' and row['model_id'] in entries:
                assessed.add(row['model_id'])
    for model in assessed:
        if entries[model]['specification'] != frozen[model]['specification']:
            raise ValueError('Assessed entry changed since Luna assessment: ' + model)
    links = defaultdict(lambda: defaultdict(list))
    with (RUN / 'problem_links.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['problem_id'] not in visible_problems:
                continue
            model = row['model_id']
            if model not in entries:
                raise ValueError('Positive annotation has no current entry: ' + model)
            if entries[model]['specification'] != frozen[model]['specification']:
                raise ValueError('Entry changed since Luna assessment: ' + model)
            assert row['status'] == 'addresses' and row['processing_state'] == 'completed'
            assert row['paper_id'] in {r['paper_id'] for r in entries[model]['references']}
            links[model][row['problem_id']].append({
                'paperId': row['paper_id'], 'rationale': row['rationale'],
                'evidence': json.loads(row['evidence_json']),
                'needsReview': row['needs_review'] == 'True',
                'reviewReasons': json.loads(row['review_reasons_json']),
            })
    return {'schemaVersion': 1, 'snapshot': '29 October 2026', 'model': 'Luna',
            'catalogueSha256': manifest['catalogue_sha256'],
            'currentCatalogueSha256': sha256((ROOT / 'atlas/catalogue.json').read_bytes()).hexdigest(),
            'classificationsSha256': sha256((RUN / 'classifications.csv').read_bytes()).hexdigest(),
            'categories': categories, 'problems': problems,
            'assessed': sorted(assessed), 'links': links}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = payload()
    content = 'window.ATLAS_PROBLEMS = ' + json.dumps(result, ensure_ascii=False, separators=(',', ':')) + ';\n'
    target = ROOT / 'website/problem-data.js'
    if args.check:
        if target.read_text() != content:
            raise ValueError('Stale website problem preview; run scripts/build_problem_preview.py')
    else:
        target.write_text(content)
    print(f"Problem preview: {len(result['problems'])} problems, {sum(len(x) for x in result['links'].values())} model–problem links; {len(result['assessed'])} assessed entries.")


if __name__ == '__main__':
    main()
