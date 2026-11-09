"""SM display shorthand must not depend on source-specific factor identifiers."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bsm_atlas.catalogue import normalize
from bsm_atlas.presentation import compact_baseline, matrix

ROOT = Path(__file__).resolve().parents[1]


def rename(spec, names=('c', 'w', 'y')):
    result = deepcopy(spec)
    mapping = dict(zip((f['id'] for f in result['gauge_factors']), names))
    for factor in result['gauge_factors']:
        factor['id'] = mapping[factor['id']]
    for row in result['matter']:
        row['gauge_representations'] = {mapping[key]: rep for key, rep in row['gauge_representations'].items()}
    return result


class PresentationBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads((ROOT / 'atlas/reference_spectra.json').read_text())
        cls.templates = {key: matrix(value['specification']) for key, value in cls.reference.items()}
        cls.templates['F_SM'] = {**cls.templates['R_SM'], 'rows': [r for r in cls.templates['R_SM']['rows'] if r['lorentz']['component'] == 'F']}
        cls.templates['H_SM'] = {**cls.templates['R_SM'], 'rows': [r for r in cls.templates['R_SM']['rows'] if r['lorentz']['component'] == 'S']}

    def test_charged_and_fractional_singlets_compact_with_arbitrary_factor_names(self):
        for charge in ['4', '6']:
            spec = deepcopy(self.reference['R_SM']['specification'])
            extra = deepcopy(spec['matter'][-1])
            extra['gauge_representations']['weak_L']['dynkin'] = [0]
            extra['gauge_representations']['hypercharge']['charge'] = charge
            spec['matter'].append(extra)
            for names in [('colour', 'weak_L', 'hypercharge'), ('c', 'w', 'y'), ('factor_a', 'factor_b', 'factor_c')]:
                for reverse in [False, True]:
                    with self.subTest(charge=charge, names=names, reverse=reverse):
                        candidate = rename(spec, names)
                        if reverse:
                            candidate['gauge_factors'].reverse()
                        before = deepcopy(candidate)
                        regime = matrix(candidate)
                        full_rows = deepcopy(regime['rows'])
                        compact_baseline(regime, self.templates)
                        self.assertEqual(regime['baseline'], 'R_SM')
                        self.assertEqual(len(regime['additionalRows']), 1)
                        extra_charge = next(c['value'] for c in regime['additionalRows'][0]['components'] if c['dynkin'] is None)
                        self.assertEqual(extra_charge, charge)
                        self.assertEqual(regime['rows'], full_rows)
                        self.assertEqual(candidate, before)

    def test_mssm_and_two_higgs_doublets_preserve_existing_shorthand(self):
        mssm = rename(self.reference['R_MSSM']['specification'])
        regime = matrix(mssm)
        compact_baseline(regime, self.templates)
        self.assertEqual(regime['baseline'], 'R_MSSM')
        self.assertEqual(regime['additionalRows'], [])
        two_higgs = rename(self.reference['R_SM']['specification'])
        two_higgs['matter'][-1]['copies'] = 2
        regime = matrix(two_higgs)
        compact_baseline(regime, self.templates)
        self.assertEqual(regime['baseline'], 'F_SM')
        self.assertEqual(regime['additionalRows'][0]['copies'], 2)

    def test_algebra_alone_does_not_establish_sm_matter(self):
        for change in ['missing_generation', 'wrong_charge', 'wrong_lorentz']:
            spec = rename(self.reference['R_SM']['specification'])
            if change == 'missing_generation':
                spec['matter'][0]['copies'] = 2
            elif change == 'wrong_charge':
                spec['matter'][0]['gauge_representations']['y']['charge'] = '2'
            else:
                spec['matter'][0]['lorentz']['irreps'] = [['1/2', '1/2']]
            regime = matrix(normalize(spec))
            compact_baseline(regime, self.templates)
            self.assertNotIn('baseline', regime, change)

    def test_extra_u1_does_not_infer_a_hypercharge_embedding(self):
        spec = rename(self.reference['R_SM']['specification'])
        spec['gauge_factors'].append({'id': 'extra', 'family': 'U1', 'rank': 1})
        for row in spec['matter']:
            row['gauge_representations']['extra'] = {'charge': '0'}
        regime = matrix(spec)
        compact_baseline(regime, self.templates)
        self.assertNotIn('baseline', regime)


if __name__ == '__main__':
    unittest.main()
