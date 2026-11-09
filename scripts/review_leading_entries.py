#!/usr/bin/env python3
"""Source-backed repair of the seven leading entries reviewed 9 November 2026.

Dry-run by default. --write updates the working catalogue and literature store
under the ingestion lock, retaining every superseded record in the review file.
It does not upload a data release or change the pinned publication snapshot.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.catalogue import identity, ingest, normalize, source_lock, validate, write_json
from bsm_atlas.literature import load_links
from bsm_atlas.matter_ordering import matter_dimension

REVIEW = ROOT / 'atlas/reviews/2026-11-09-leading-entries.json'
EXPECTED = {
    's1-scalar-leptoquark-8a79a78b7a94': '8a79a78b7a94f4b04cb7ae2d7ebc6b5f0e2b118954d8bd7a03be1d7099868807',
    'r2-scalar-leptoquark-9eac3b95c500': '9eac3b95c5005c56f24b4e0083961b17b95f71f7b4039e8f6d1d58accc3f0efe',
    's3-scalar-leptoquark': '9cf5971c8b27ad44796504ead2b61f7db90998148bf5c93ecbd1fe45100ac553',
    'u1-vector-leptoquark': 'ab555d88c512fe8bc1de06e86c4d8730e798ff8351b8a48646f8e4e9f8235038',
    'v2-vector-leptoquark': '9893d0aab2c1cccaab48219edfab0a0fd657a49c2cfd7ba407d094f026715812',
    'deflected-amsb-singlet-vectorlike-messengers': '792d0046a13758b8273caf57b931917ca06791dbaebc6c354441f364eeae0133',
    'u1h-noninvertible-pq': '805a2d91b1c8b262ad3aae1534b2b3f7ec8b19be0323865289dd2fdc25078587',
}
SOURCES = {
    '2211.14172v2': ('2211', 'bclnu_letter_v2.tex'),
    '1512.06715v3': ('1512', 'paper-plb.tex'),
    '2402.12453v1': ('2402', 'draft.tex'),
}


def verify_sources(sources=SOURCES):
    result = {}
    for arxiv, (month, filename) in sources.items():
        directory = ROOT / 'corpus/hep-ph/papers' / month / arxiv.replace('/', '_')
        metadata = json.loads((directory / 'meta.json').read_text())
        record = next(row for row in metadata['files'] if row['path'] == filename)
        raw = (directory / 'source' / filename).read_bytes()
        digest = sha256(raw).hexdigest()
        if len(raw) != record['bytes'] or digest != record['sha256']:
            raise ValueError('Retained paper source hash mismatch: ' + arxiv)
        result[arxiv] = {'file': filename, 'sha256': digest}
    return result


def replacements():
    sm = json.loads((ROOT / 'atlas/reference_spectra.json').read_text())['R_SM']['specification']
    result = {}
    # Hypercharges are restored from Sec. III of 2211.14172v2 in q = 6Y
    # units. They cannot be recovered by rescaling the isolated stored rows.
    for old_id, name, colour, weak, charge, vector in [
        ('s1-scalar-leptoquark-8a79a78b7a94', 'S1', [0, 1], [0], '2', False),
        ('r2-scalar-leptoquark-9eac3b95c500', 'R2', [1, 0], [1], '7', False),
        ('s3-scalar-leptoquark', 'S3', [0, 1], [2], '2', False),
        ('u1-vector-leptoquark', 'U1', [1, 0], [0], '4', True),
        ('v2-vector-leptoquark', 'V2', [0, 1], [1], '5', True),
    ]:
        spec = deepcopy(sm)
        spec['matter'].append({
            'lorentz': {'dimension': 4, 'scheme': 'jL_jR',
                        'irreps': [['1/2', '1/2']] if vector else [['0', '0']]},
            'reality': 'complex', 'copies': 1,
            'gauge_representations': {'colour': {'dynkin': colour},
                                      'weak_L': {'dynkin': weak},
                                      'hypercharge': {'charge': charge}},
        })
        section = 'Vector' if vector else 'Scalar'
        result[old_id] = {
            'id': old_id, 'name': f'SM plus {section.lower()} leptoquark {name}',
            'specification': normalize(spec),
            'references': [{'paper_id': 'arxiv-2211-14172v2', 'locators': [
                'Sec. III opening; Sec. IV and Table I: single-particle extensions of the SM',
                f'Sec. III, {section} Leptoquarks: {name} representation; hypercharge q=6Y',
            ]}],
        }
    # 2402.12453v1 Sec. 3.1 explicitly gauges H=B1+B2-2B3 with
    # no additional matter. Use that unbroken phase, not an invented scalar
    # sector or the separate SU(3)_H / SU(9) constructions in the paper.
    spec = deepcopy(sm)
    spec['gauge_factors'].append({'id': 'horizontal', 'family': 'U1', 'rank': 1})
    rows = []
    for row in spec['matter']:
        reps = row['gauge_representations']
        if any(reps['colour']['dynkin']):
            sign = 1 if reps['colour']['dynkin'] == [1, 0] else -1
            for copies, charge in [(2, sign), (1, -2 * sign)]:
                split = deepcopy(row)
                split['copies'] = copies
                split['gauge_representations']['horizontal'] = {'charge': str(charge)}
                rows.append(split)
        else:
            row['gauge_representations']['horizontal'] = {'charge': '0'}
            rows.append(row)
    spec['matter'] = rows
    result['u1h-noninvertible-pq'] = {
        'id': 'u1h-noninvertible-pq', 'name': 'SM plus gauged U(1)_H horizontal symmetry',
        'specification': normalize(spec),
        'references': [{'paper_id': 'arxiv-2402-12453v1', 'locators': [
            'Table 1: SM field representations and integer hypercharge convention',
            'Sec. 3, Eq. (his): H=B1+B2-2B3',
            'Sec. 3.1 opening: U(1)_H gauged with no additional matter; unbroken phase',
        ]}],
    }
    return result


def repair(data, links, *, expected=EXPECTED, candidates=None, withdrawals=None):
    """Pure transaction: reconcile repaired identities and detach stale evidence."""
    data, links = deepcopy(data), deepcopy(links)
    validate(data)
    originals = {entry['id']: entry for entry in data['entries'] if entry['id'] in expected}
    if set(originals) != set(expected):
        raise ValueError('Reviewed entries missing; this review may already have been applied')
    for key, entry in originals.items():
        if identity(entry['specification'])['fingerprint'] != expected[key]:
            raise ValueError('Reviewed entry changed; inspect before applying: ' + key)
    data['entries'] = [entry for entry in data['entries'] if entry['id'] not in expected]
    fingerprints = {identity(e['specification'])['fingerprint']: e for e in data['entries']}
    report = {'date': '2026-11-09', 'scope': 'Seven leading entries in the published full-matter ordering',
              'superseded_entries': originals, 'changes': {}, 'detached_literature': {}}
    for old_id, candidate in (replacements() if candidates is None else candidates).items():
        data, target = ingest(data, candidate, _fingerprints=fingerprints)
        spec = candidate['specification']
        report['changes'][old_id] = {'action': 'repaired', 'target': target,
            'fingerprint': identity(spec)['fingerprint'],
            'real_field_dimension': matter_dimension(json.loads(identity(spec)['canonical_json']))}
    if withdrawals is None:
        withdrawals = {'deflected-amsb-singlet-vectorlike-messengers': {
        'action': 'withdrawn_pending_reextraction',
        'reason': 'Stored one-generation/non-MSSM sector is incomplete. Source Sec. II inherits the MSSM; '
                  'messenger species and multiplicities must be selected from a definite source benchmark. '
                  'Table II fixes NF=N5+3N10=10, not a unique (N5,N10). The displayed SU(5) component '
                  'hypercharge/conjugation conventions also require resolution. Do not invent missing fields.'}}
    report['changes'].update(withdrawals)
    if 'u1h-noninvertible-pq' in report['changes']:
        report['changes']['u1h-noninvertible-pq']['reason'] = (
        'Restore the missing horizontal U(1) and generation-dependent quark charges for the original '
        'paper only. Other aliases and paper links were merged on the erroneous SM-only identity; '
        'they have not been established for this corrected inventory and are retained in this review '
        'for separate re-extraction, not reassigned.')
    # An assessment of an old structure is not an assessment of its replacement.
    # Preserve it in the review rather than automatically transferring evidence.
    affected_papers = set()
    for paper_id, receipt in links['papers'].items():
        detached = [m for m in receipt['models'] if m['entry_id'] in expected]
        if detached:
            report['detached_literature'][paper_id] = detached
            receipt['models'] = [m for m in receipt['models'] if m['entry_id'] not in expected]
            affected_papers.add(paper_id)
    for entry in originals.values():
        affected_papers.update(ref['paper_id'] for ref in entry['references'])
    report['superseded_papers'] = [deepcopy(paper) for paper in data['papers']
                                   if paper['id'] in affected_papers]
    # The leptoquark source has been re-read and all five specified inventories
    # repaired. Other descriptions/annotations still need independent extraction.
    for paper in data['papers']:
        if paper['id'] in affected_papers and paper['id'] != 'arxiv-2211-14172v2':
            paper['extraction_status'] = 'unresolved'
    validate(data)
    return data, links, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--source', type=Path, default=ROOT / 'atlas/catalogue.json')
    parser.add_argument('--report', type=Path, default=REVIEW)
    args = parser.parse_args()
    sources = verify_sources()
    with source_lock(args.source, wait=True):
        data = json.loads(args.source.read_text())
        links_path = args.source.with_name('literature_links.json')
        repaired, links, report = repair(data, load_links(links_path))
        report['sources'] = sources
        report['before_counts'] = {'entries': len(data['entries']), 'papers': len(data['papers'])}
        report['after_counts'] = {'entries': len(repaired['entries']), 'papers': len(repaired['papers'])}
        for key, change in report['changes'].items():
            print(key, json.dumps(change, ensure_ascii=False))
        if args.write:
            if args.report.exists():
                raise ValueError('Review report exists; do not overwrite the original records')
            args.report.parent.mkdir(parents=True, exist_ok=True)
            # Save recovery information before either authoritative file changes.
            write_json(args.report, report)
            write_json(args.source, repaired)
            write_json(links_path, links)
            print('Applied; superseded records retained in', args.report)
        else:
            print('Dry run:', report['before_counts'], '->', report['after_counts'])


if __name__ == '__main__':
    main()
