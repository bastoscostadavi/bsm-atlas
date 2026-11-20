#!/usr/bin/env python3
"""Restore three SM generations by explicit curator choice, not source inference.

Dry-run by default. The paper works with one generation; its singlet sector
is retained unchanged. --write updates the working sources under their lock.
Publishing a new immutable data snapshot is a separate operation.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.catalogue import normalize, source_lock, write_json
from bsm_atlas.literature import load_links
from scripts.review_leading_entries import repair

ENTRY = 'dcdm-inverse-seesaw'
EXPECTED = '2a3afdab78c691b6a1f2526c2eee4850978df1447e1eea2e06faa3ac6a44bb75'
NOTE = ('Atlas curator choice: restore three SM fermion generations while retaining '
        'the six singlet Weyl fermions and one complex singlet scalar '
        '(two real scalar components). Sec. 3 explicitly uses one generation '
        'for simplicity and mentions the three-SM-generation extension.')


def candidate(original):
    result = deepcopy(original)
    # The old one-generation alias describes the superseded spectrum. Preserve
    # it in the audit record, rather than attach that description to a new one.
    result.pop('aliases', None)
    fields = result['specification']['matter']
    sm_fermions = [row for row in fields
                   if row['lorentz']['irreps'] == [['1/2', '0']]
                   and row['gauge_representations']['hypercharge']['charge'] != '0']
    if len(sm_fermions) != 5 or any(row['copies'] != 1 for row in sm_fermions):
        raise ValueError('Expected exactly five one-generation SM fermion representations')
    for row in sm_fermions:
        row['copies'] = 3
    result['specification'] = normalize(result['specification'])
    result['references'][0].setdefault('locators', []).append(NOTE)
    return result


def review(data, links):
    original = next(entry for entry in data['entries'] if entry['id'] == ENTRY)
    updated, annotations, report = repair(
        data, links, expected={ENTRY: EXPECTED},
        candidates={ENTRY: candidate(original)}, withdrawals={})
    report.update(date='2026-11-19', scope=NOTE,
                  source_url='https://arxiv.org/html/2509.19596v1#S3',
                  curator_authorization='Restore three SM generations',
                  replacement_entry=candidate(original))
    # The shared repair detaches old annotations. Also retire their old
    # fingerprint and retain it with the detached model for later review.
    for paper_id, models in report['detached_literature'].items():
        receipt = annotations['papers'][paper_id]
        fingerprint = receipt.get('model_fingerprints', {}).pop(ENTRY, EXPECTED)
        receipt.setdefault('detached_models', []).extend(
            {'fingerprint': fingerprint, 'model': deepcopy(model)} for model in models)
        if 'quality' in receipt:
            receipt['quality']['needs_followup'] = True
    return updated, annotations, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--source', type=Path, default=ROOT / 'atlas/catalogue.json')
    parser.add_argument('--report', type=Path,
                        default=ROOT / 'atlas/reviews/2026-11-19-inverse-seesaw-generations.json')
    args = parser.parse_args()
    with source_lock(args.source, wait=True):
        data = json.loads(args.source.read_text())
        links_path = args.source.with_name('literature_links.json')
        updated, annotations, report = review(data, load_links(links_path))
        print(json.dumps(report['changes'], indent=2), flush=True)
        if args.write:
            if args.report.exists():
                raise ValueError('Review report already exists; refusing to overwrite history')
            write_json(args.report, report)
            write_json(args.source, updated)
            write_json(links_path, annotations)
            print('Applied to working sources; original record retained in', args.report)
        else:
            print('Dry run; no files changed')


if __name__ == '__main__':
    main()
