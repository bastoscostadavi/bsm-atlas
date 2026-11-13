#!/usr/bin/env python3
"""Reproduce established counts with the generic solver and save the evidence."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bsm_atlas.parameter_counts import assess as parameters
from bsm_atlas.physical_parameters import METHOD, assess as generic_physical


def neutral(spec, copies=1, fermion=False):
    return {'copies': copies, 'reality': 'none' if fermion else 'real_module',
            'lorentz': {'dimension': 4, 'scheme': 'jL_jR',
                        'irreps': [['1/2', '0']] if fermion else [['0', '0']]},
            'gauge_representations': {a['id']: {'charge': '0'} if a['family'] == 'U1'
                                      else {'dynkin': [0] * a['rank']} for a in spec['gauge_factors']}}


def cases():
    sm = json.loads((ROOT / 'atlas/reference_spectra.json').read_text())['R_SM']['specification']
    yield 'Standard Model', sm, 61, 19
    singlet = deepcopy(sm)
    singlet['matter'].append(neutral(singlet))
    yield 'SM + real singlet', singlet, 67, 24
    sterile = deepcopy(sm)
    sterile['matter'].append(neutral(sterile, 3, True))
    yield 'SM + three sterile Weyl fermions', sterile, 91, 37
    two_higgs = deepcopy(sm)
    two_higgs['matter'][-1]['copies'] = 2
    yield 'SM + second Higgs doublet, general Yukawas', two_higgs, 127, 80
    # Potential-only values from table 1 of arXiv:2102.13120. The full
    # electroweak scalar theory also has g, g' and theta_weak: add three.
    for n, raw, physical in [(1, 2, 2), (2, 14, 11), (3, 54, 46),
                              (4, 152, 137), (5, 350, 326)]:
        model = deepcopy(sm)
        model['gauge_factors'] = [a for a in model['gauge_factors'] if not (a['family'] == 'A' and a['rank'] == 2)]
        model['matter'] = [model['matter'][-1]]
        row = model['matter'][0]
        row['copies'] = n
        row['gauge_representations'] = {a['id']: row['gauge_representations'][a['id']] for a in model['gauge_factors']}
        yield f'{n} Higgs doublets + electroweak gauge/theta', model, raw + 3, physical + 3
    for n, raw, physical in [(1, 4, 3), (2, 14, 11), (3, 34, 28)]:
        model = {'gauge_factors': [], 'matter': []}
        model['matter'] = [neutral(model, n)]
        yield f'{n} ungauged real singlets', model, raw, physical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/physical-parameter-validation.json')
    args = parser.parse_args()
    results = []
    for name, spec, expected_raw, expected_physical in cases():
        total = parameters(spec)['total']
        # Call the generic implementation directly: no name/fingerprint table
        # or previous SM-family formula supplies the physical answer here.
        physical = generic_physical(spec, total)
        if (total['value'], physical['value']) != (expected_raw, expected_physical):
            raise AssertionError((name, total, physical, expected_raw, expected_physical))
        results.append({'name': name, 'expected_total': expected_raw,
                        'expected_physical': expected_physical,
                        'actual_total': total['value'], 'physical': physical})
        print(f'{name}: {total["value"]} total, {physical["value"]} physical — verified', flush=True)
    report = {'schema_version': 'physical-parameter-validation-1', 'method': METHOD,
              'solver_sha256': sha256((ROOT / 'bsm_atlas/physical_parameters.py').read_bytes()).hexdigest(),
              'cases': results, 'passed': len(results),
              'multi_higgs_reference': 'https://arxiv.org/abs/2102.13120'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
