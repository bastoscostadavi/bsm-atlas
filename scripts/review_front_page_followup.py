#!/usr/bin/env python3
"""Repair two further source-checked inventories exposed by the leading-entry review."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.catalogue import normalize, source_lock, write_json
from bsm_atlas.literature import load_links
from scripts.review_leading_entries import repair, replacements, verify_sources

EXPECTED = {
    'u1-bminusl-seesaw': '968e75e9668195364e96a0a66cb7a0c43dd259219dafa499708527fcfe4883f5',
    'scalar-leptoquarks-s1prime': '17c89672b905c7550fea73b3ae41c3c8b5e3e77347d5d5a9a3aeb41e4332c681',
}


def candidates():
    # Eq. (1) of hep-ph/9307324v2 contains bar(u_R^c) e_R S1'.
    # Gauge invariance fixes S1'=(bar3,1,Y=1/3), the same structural
    # inventory as SM+S1, not a colour singlet with q=8.
    scalar = deepcopy(replacements()['s1-scalar-leptoquark-8a79a78b7a94'])
    scalar.update(id='scalar-leptoquarks-s1prime', name='SM plus scalar leptoquark S1′')
    scalar['references'] = [{'paper_id': 'arxiv-hep-ph-9307324v2', 'locators': [
        'Eq. (1): SU(3)×SU(2)×U(1)-invariant Lagrangian; bar(u_R^c) e_R S1prime',
        'Text following Eq. (1): ordinary SM quark/lepton fields and charge conjugation',
    ]}]
    # 1703.02471v3 Sec. VII gives Q,uR,dR,L,eR,Na,H,Delta explicitly;
    # colour is a spectator as established in Sec. II. The Abelian basis
    # is (2 I3R, 3(B-L)), and all independent fermions below are LH.
    factors = [
        {'id': 'colour', 'family': 'A', 'rank': 2},
        {'id': 'weak_L', 'family': 'A', 'rank': 1},
        {'id': 'I3R', 'family': 'U1', 'rank': 1},
        {'id': 'B_minus_L', 'family': 'U1', 'rank': 1},
    ]
    rows = []
    for colour, weak, ir, bl in [
        ([1, 0], [1], '0', '1'),
        ([0, 1], [0], '-1', '-1'),
        ([0, 1], [0], '1', '-1'),
        ([0, 0], [1], '0', '-3'),
        ([0, 0], [0], '1', '3'),
        ([0, 0], [0], '-1', '3'),
    ]:
        rows.append({'lorentz': {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['1/2', '0']]},
            'reality': 'none', 'copies': 3,
            'gauge_representations': {'colour': {'dynkin': colour}, 'weak_L': {'dynkin': weak},
                                      'I3R': {'charge': ir}, 'B_minus_L': {'charge': bl}}})
    for weak, ir, bl in [([1], '-1', '0'), ([0], '-2', '6')]:
        rows.append({'lorentz': {'dimension': 4, 'scheme': 'jL_jR', 'irreps': [['0', '0']]},
            'reality': 'complex', 'copies': 1,
            'gauge_representations': {'colour': {'dynkin': [0, 0]}, 'weak_L': {'dynkin': weak},
                                      'I3R': {'charge': ir}, 'B_minus_L': {'charge': bl}}})
    seesaw = {'id': 'u1-bminusl-seesaw',
        'name': 'SM with U(1)_{I3R} × U(1)_{B-L} seesaw sector',
        'specification': normalize({'schema_version': 'field-content-2', 'inventory_complete': True,
                                    'gauge_factors': factors, 'matter': rows}),
        'references': [{'paper_id': 'arxiv-1703-02471v3', 'locators': [
            'Sec. II opening and Eq. (lrSM): spectator SU(3)c and quark colour representations',
            'Sec. VII opening fermion assignments; three RHNs Na; scalar fields H and Delta',
            'Sec. VII Eq. (eq:1): renormalizable Yukawa interactions; basis (2 I3R,3(B-L)); all-LH conversion',
        ]}]}
    return {scalar['id']: scalar, seesaw['id']: seesaw}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    sources = verify_sources({'hep-ph/9307324v2': ('9307', 'main.tex'),
                              '1703.02471v3': ('1703', 'H3_LR_NPB_v2.tex')})
    source = ROOT / 'atlas/catalogue.json'
    destination = ROOT / 'atlas/reviews/2026-11-09-front-page-followup.json'
    with source_lock(source, wait=True):
        original = json.loads(source.read_text())
        links_path = source.with_name('literature_links.json')
        updated, links, report = repair(original, load_links(links_path), expected=EXPECTED,
                                        candidates=candidates(), withdrawals={})
        report['scope'] = 'Two additional erroneous leading/front-page entries in the working catalogue'
        report['sources'] = sources
        report['before_counts'] = {'entries': len(original['entries']), 'papers': len(original['papers'])}
        report['after_counts'] = {'entries': len(updated['entries']), 'papers': len(updated['papers'])}
        for key, change in report['changes'].items():
            print(key, json.dumps(change))
        if args.write:
            if destination.exists():
                raise ValueError('Review already exists; do not overwrite original records')
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_json(destination, report)
            write_json(source, updated)
            write_json(links_path, links)
        else:
            print('Dry run:', report['before_counts'], '->', report['after_counts'])


if __name__ == '__main__':
    main()
