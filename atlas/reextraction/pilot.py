#!/usr/bin/env python3
"""Reproducible STAGING checkpoints, not an atlas database importer.

Human/agent-inspected source statements below are deliberately separated from
baseline conventions and mathematical conversions. Downloads remain local.
"""
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'atlas'))
from catalogue_identity import normalize_spec, canonicalize

SOURCE_HASH = 'd4dbf023b667fe810296c43c8f72e0d0b3f6559e66b344a2920c9e2e520e6c4c'
RUN = '2026-10-16-pilot-1'

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def emit(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def row(label, weights, charge, copies=1, scalar=False, right=False, reality=None):
    factor_ids = list(weights)
    reps = {key: {'dynkin': weight} for key, weight in weights.items()}
    reps['bl' if 'right' in factor_ids else 'hypercharge'] = {'charge': charge}
    return {'label': label, 'lorentz': {'dimension': 4, 'scheme': 'jL_jR',
            'irreps': [['0', '0']] if scalar else [['0', '1/2']] if right else [['1/2', '0']]},
            'reality': reality or ('complex' if scalar else 'none'),
            'copies': copies, 'gauge_representations': reps}

def lr_source():
    def w(c, l, r):
        return {'colour': c, 'left': [l], 'right': [r]}
    return {'schema_version': 'field-content-1', 'inventory_complete': True,
            'name': 'Minimal triplet left-right matter content', 'paper_ids': ['P04'],
            'gauge_factors': [{'id': 'colour', 'family': 'A', 'rank': 2},
                              {'id': 'left', 'family': 'A', 'rank': 1},
                              {'id': 'right', 'family': 'A', 'rank': 1},
                              {'id': 'bl', 'family': 'U1', 'rank': 1}],
            'matter': [row('Q_L', w([1, 0], 1, 0), '1/3', 3),
                       row('Q_R', w([1, 0], 0, 1), '1/3', 3, right=True),
                       row('l_L', w([0, 0], 1, 0), '-1', 3),
                       row('l_R', w([0, 0], 0, 1), '-1', 3, right=True),
                       row('Phi', w([0, 0], 1, 1), '0', scalar=True),
                       row('Delta_L', w([0, 0], 2, 0), '2', scalar=True),
                       row('Delta_R', w([0, 0], 0, 2), '2', scalar=True)]}

SM_FACTORS = [{'id': 'colour', 'family': 'A', 'rank': 2},
              {'id': 'weak', 'family': 'A', 'rank': 1},
              {'id': 'hypercharge', 'family': 'U1', 'rank': 1}]

def sm_fermions(hypercharge_scale=1):
    # Explicit atlas F_SM baseline in textbook Y units. These are not claimed
    # to be a newly printed multiplet table in each source.
    fields = [('Q', [1, 0], 1, '1/6'), ('u^c', [0, 1], 0, '-2/3'),
              ('d^c', [0, 1], 0, '1/3'), ('L', [0, 0], 1, '-1/2'),
              ('e^c', [0, 0], 0, '1')]
    return [row(label, {'colour': c, 'weak': [w]}, str(Fraction(q) * hypercharge_scale), 3)
            for label, c, w, q in fields]

def sm_candidate(name, paper, scalar_fields, source_hypercharge_scale=1):
    return {'schema_version': 'field-content-1', 'inventory_complete': True,
            'name': name, 'paper_ids': [paper], 'gauge_factors': deepcopy(SM_FACTORS),
            'matter': sm_fermions(source_hypercharge_scale) + scalar_fields}

def higgs(label='H', charge='1/2'):
    return row(label, {'colour': [0, 0], 'weak': [1]}, charge, scalar=True)

def singlet_source(paper='P01', complex_field=False):
    singlet = row('S', {'colour': [0, 0], 'weak': [0]}, '0', scalar=True,
                  reality='complex' if complex_field else 'real')
    return sm_candidate('Complex singlet extension' if complex_field else 'Real singlet extension',
                        paper, [higgs(), singlet])

def thdm_source():
    # P03 Eq.(2) has Y_source(H)=1, i.e. twice textbook Y. Appendix E
    # uses a coupling on Y_source/2; preserve that distinction in evidence.
    return sm_candidate('Two-Higgs-doublet matter content', 'P03',
                        [higgs('Phi_1', '1'), higgs('Phi_2', '1')], 2)

def nmssm_source():
    matter = []
    for fermion in sm_fermions():
        scalar = deepcopy(fermion)
        scalar['label'] = 'scalar ' + scalar['label']
        scalar['lorentz']['irreps'] = [['0', '0']]
        scalar['reality'] = 'complex'
        matter += [scalar, fermion]
    for label, q in [('H_u', '1/2'), ('H_d', '-1/2')]:
        scalar = higgs(label, q)
        fermion = deepcopy(scalar)
        fermion['label'] = 'higgsino ' + label
        fermion['lorentz']['irreps'] = [['1/2', '0']]
        fermion['reality'] = 'none'
        matter += [scalar, fermion]
    matter += [row('gluino', {'colour': [1, 1], 'weak': [0]}, '0'),
               row('wino', {'colour': [0, 0], 'weak': [2]}, '0'),
               row('bino', {'colour': [0, 0], 'weak': [0]}, '0'),
               row('S scalar', {'colour': [0, 0], 'weak': [0]}, '0', scalar=True),
               row('singlino', {'colour': [0, 0], 'weak': [0]}, '0')]
    return {'schema_version': 'field-content-1', 'inventory_complete': True,
            'name': 'NMSSM matter content (general and Z3 variants)', 'paper_ids': ['P05'],
            'gauge_factors': deepcopy(SM_FACTORS), 'matter': matter}

BASELINE_NOTE = {
 'id': 'declared-baseline', 'basis': 'atlas_baseline_expansion_not_new_source_table',
 'locator': 'atlas/FIELD_CONTENT_CONVENTIONS.md, explicit F_SM/R_SM/R_MSSM templates; source model-definition locator below',
 'value': 'Expand the expressly inherited SM/MSSM with its standard three families and exact representations. Dynkin maps: su(3) 3=[1,0], anti-3=[0,1], adjoint=[1,1]; su(2) d has label [d-1]. All Weyl fields are LH, including u^c,d^c,e^c. Ordinary textbook Y is used only as the declared baseline coordinate, not claimed to be individually tabulated by this source. No right-handed neutrino or additional sector is invented.'}

PILOT_LIMITS = ['Scoped definition reread, not a complete phenomenology or viability review.',
                'Source evidence is agent checked, not independently reviewed.',
                'Scalar realification is not quotiented by the current identity checker.',
                'No database ingestion or website update is performed.']

PAPERS = {
 'P04': {
  'arxiv_version': '1005.5160v1', 'temporary_pdf': '/tmp/bsm-p04-1005.5160v1.pdf',
  'filename': '1005.5160v1.pdf', 'source_url': 'https://arxiv.org/pdf/1005.5160v1',
  'first_observed_utc': '2026-10-16T17:47:13Z',
  'scientific_read_started_observed_utc': None,
  'inspection': {'text_pages': [1, 2, 3, 4, 5, 6, 7, 8, 22, 24, 26, 27],
                 'visual_pages': [4, 5, 6, 7, 22],
                 'scope': 'Symmetric-phase minimal triplet LR gauge/matter definition, parity/C implementation; selected surrounding paragraphs only. Not a full phenomenology reread.'},
  'retrievals': [
      {'method': 'web.open', 'url': 'https://arxiv.org/html/1005.5160v1', 'outcome': 'cache_miss'},
      {'method': 'web.open', 'url': 'https://arxiv.org/pdf/1005.5160v1', 'outcome': 'cache_miss'},
      {'method': 'web.open', 'url': 'https://arxiv.org/src/1005.5160v1', 'outcome': 'cache_miss'},
      {'method': 'curl_sandbox', 'url': 'https://arxiv.org/pdf/1005.5160v1', 'outcome': 'sandbox_dns_block'},
      {'method': 'curl_authorized_network', 'url': 'https://arxiv.org/pdf/1005.5160v1', 'outcome': 'success', 'observed_command_wall_seconds': 0.262022083}],
  'claims': [
    {'id': 'lr-gauge', 'basis': 'source_statement', 'locator': 'Section 2, PDF/printed p.4, opening paragraph before Eq.(1)',
     'value': 'SU(2)_L x SU(2)_R x U(1)_(B-L); colour explicitly suppressed, not absent.'},
    {'id': 'lr-fermions', 'basis': 'source_statement', 'locator': 'Section 2, PDF/printed p.4 Eq.(1); p.7 Eq.(16) and paragraph below',
     'value': 'Q_(L,R)=(u,d)_(L,R), l_(L,R)=(nu,e)_(L,R); Q_R charge conjugate is explicitly a left-chiral spinor.'},
    {'id': 'lr-charge', 'basis': 'source_statement', 'locator': 'Section 2, PDF/printed p.4 Eq.(2)',
     'value': 'Q_em = I_3L + I_3R + (B-L)/2.'},
    {'id': 'lr-scalars', 'basis': 'source_statement', 'locator': 'Section 2, PDF/printed p.4 paragraph before Eq.(3) and Eq.(3)',
     'value': 'One Phi in (2,2,0); Delta_L in (3,1,2), Delta_R in (1,3,2), in source B-L units.'},
    {'id': 'lr-complex', 'basis': 'source_supported_derivation', 'locator': 'Section 2, PDF/printed pp.4-6 Eqs.(3),(5),(8), heavy-Higgs paragraph and Eq.(15)',
     'value': 'Phi is an unconstrained complex bidoublet: source has two SU(2)_L doublets and a complex heavy neutral component, not a single real bidoublet. Delta_L/R are complex since their continuous B-L charge is nonzero. No dependent conjugate multiplets are counted.'},
    {'id': 'lr-generations', 'basis': 'source_statement_and_derivation', 'locator': 'Section 2, PDF/printed p.5 generation-indices sentence after Eq.(8); p.6 Eq.(11); section 4.1, PDF/printed p.22 Flavor structure',
     'value': 'Eq.(11) enumerates u,c,t and d,s,b in both chiralities, fixing three quark families. p.22 explicitly describes the three nu_R mass eigenstates; combined with Eq.(1), the lepton doublets have three copies.'},
    {'id': 'lr-inherited-colour', 'basis': 'declared_SM_baseline_interpretation', 'locator': 'Section 2, PDF/printed p.4 explicitly suppresses colour; p.4 Eq.(1); p.4 Eqs.(3)-(4)',
     'value': 'Restore the ordinary SM colour algebra su(3), fundamental quarks and singlet leptons/Higgs. This is expansion of the paper\'s explicitly suppressed ordinary colour sector using the atlas SM baseline, not a new colour tuple printed by P04. No global quotient is asserted.'},
    {'id': 'lr-derived-fermion-charges', 'basis': 'source_supported_derivation_with_declared_SM_charge_baseline', 'locator': 'Section 2, PDF/printed p.4 Eqs.(1)-(2)',
     'value': 'Using the ordinary identified u,d charges 2/3,-1/3 and nu,e charges 0,-1, Eq.(2) gives source B-L=1/3 for Q_L/R and -1 for l_L/R. The opposite SU(2) factor acts trivially. These charges are derived, not a fermion charge table quoted from P04.'},
    {'id': 'lr-normalization', 'basis': 'atlas_mathematical_conversion', 'locator': 'lr-source-candidate.json and lr-preflight.json',
     'value': 'One positive primitive scale 3 over fermions AND scalars: q=3(B-L). Source Q_R,l_R convert to LH conjugates with colour conjugation and charges -1,+3; triplets have +6. The source coupling on p.5 multiplies (B-L)/2, so g_atlas=g_source/6 if that covariant-derivative convention is retained.'},
    {'id': 'lr-variants', 'basis': 'source_statement_and_scope_reconciliation', 'locator': 'Section 2, PDF/printed p.7 Eqs.(16)-(17)',
     'value': 'P exchanges Q_L and Q_R and maps Phi to Phi^dagger; C exchanges Q_L with (Q_R)^c and maps Phi to Phi^T. Hermitian versus symmetric Yukawa restrictions differ. Both use the same gauge/matter inventory, hence ONE staged field-content candidate with two source variants.'}],
  'legacy_targets': {'entry_id': 'lr-triplet-matter', 'regime_ids': [6, 7], 'field_ids': list(range(16, 30)),
                     'source_model_ids': ['lr-triplet-parity', 'lr-triplet-charge-conjugation']},
  'old_extraction_gaps_resolved': ['Suppressed colour sector explicitly identified and restored with a declared SM baseline.',
      'Opposite SU(2) singlets, full fermion B-L charges, three-family counts and scalar reality established.',
      'Whole-spectrum primitive integer unit replaces legacy source:2 scalar display with q=6.',
      'R-handed quarks become LH anti-colour doublets, not merely charge-sign flips.'],
  'remaining_limitations': ['Source evidence is agent checked, not independently reviewed.',
      'Ordinary SM colour/electric-charge baseline is explicitly inherited, not re-enumerated by P04.',
      'Scalar-realification equivalence and general multi-U1 basis canonicalization are not implemented.',
      'No source or website database is changed; reconciliation with legacy LR entry requires a curator.'],
  'candidate_factory': lr_source,
  'candidate_stem': 'lr',
 }
}

PAPERS.update({
 'P01': {
  'arxiv_version': 'hep-ph/0011335v3', 'filename': 'hep-ph_0011335v3.pdf',
  'source_url': 'https://arxiv.org/pdf/hep-ph/0011335v3',
  'first_observed_utc': '2026-10-16T17:48:15Z',
  'scientific_read_started_observed_utc': '2026-10-16T17:48:30Z',
  'inspection': {'text_pages': [1, 2, 3, 4, 5, 6], 'visual_pages': [5],
                 'scope': 'Introduction/model definition through initial vacuum discussion; full Eq.(2.1) definition visually checked. PDF pages have one-page offset from printed numbering.'},
  'retrievals': [{'method': 'curl_authorized_network', 'url': 'https://arxiv.org/pdf/hep-ph/0011335v3', 'outcome': 'success', 'observed_command_wall_seconds': 0.052738709}],
  'claims': [BASELINE_NOTE,
    {'id': 'p01-field', 'basis': 'source_statement', 'locator': 'Section 1, PDF p.3 / printed p.2; section 2, PDF p.5 / printed p.4, Eq.(2.1) and paragraph below',
     'value': 'SM Lagrangian plus a single new real scalar S, completely neutral under SM gauge group and the only new electroweak-scale degree of freedom. Higgs H is the SM Higgs doublet. This fixes one real (Lorentz scalar, gauge singlet), not one complex singlet.'},
    {'id': 'p01-interactions', 'basis': 'source_statement', 'locator': 'Section 2, PDF pp.5-6 / printed pp.4-5, Eqs.(2.1)-(2.2)',
     'value': 'Potential contains real-singlet mass, quartic and portal with coefficient lambda S^2 H^dagger H; S -> -S imposed. These interaction choices do not alter the gauge/matter row.'},
    {'id': 'p01-unit', 'basis': 'atlas_mathematical_conversion', 'locator': 'singlet-source-candidate.json and singlet-preflight.json',
     'value': 'Inherited textbook hypercharge baseline normalizes jointly by 6; the new scalar has exactly zero charge. This is an atlas baseline coordinate, not a new source hypercharge table.'}],
  'legacy_targets': {'entry_id': 'real-singlet-z2'},
  'old_extraction_gaps_resolved': ['Fresh pinned-source confirmation of one real, not complex, gauge singlet and explicit SM inheritance.'],
  'remaining_limitations': PILOT_LIMITS,
  'candidate_factory': singlet_source, 'candidate_stem': 'singlet',
 },
 'P02': {
  'arxiv_version': '1306.4710v5', 'filename': '1306.4710v5.pdf',
  'source_url': 'https://arxiv.org/pdf/1306.4710v5',
  'first_observed_utc': '2026-10-16T17:48:17Z',
  'scientific_read_started_observed_utc': '2026-10-16T17:48:30Z',
  'inspection': {'text_pages': [1, 2, 12, 13], 'visual_pages': [1, 12],
                 'scope': 'Main singlet model definition in section 1 and bounded complex-singlet generalization in section 6.4. Other extensions are deferred; not a whole-paper reread.'},
  'retrievals': [{'method': 'curl_authorized_network', 'url': 'https://arxiv.org/pdf/1306.4710v5', 'outcome': 'success', 'observed_command_wall_seconds': 0.199876167}],
  'claims': [BASELINE_NOTE,
    {'id': 'p02-main', 'basis': 'source_statement_and_source_internal_crosscheck', 'locator': 'Section 1, PDF/printed p.1 Eqs.(1)-(2) and paragraphs below; section 6.4, PDF/printed p.12 contrasting complex and real singlet model',
     'value': 'Main model is SM plus one real scalar singlet S with Z2 stability. Eq.(1) only displays phenomenologically relevant mass/portal terms; surrounding text explicitly mentions the kinetic and quartic self-coupling, so the omitted S^4 in Eq.(1) is not evidence that the interaction is absent.'},
    {'id': 'p02-convention', 'basis': 'comparison_derivation', 'locator': 'P01 Eq.(2.1), PDF p.5; P02 Eq.(1), PDF p.1',
     'value': 'P01 writes lambda S^2 H^dagger H, P02 writes (lambda_hS/2) S^2 |H|^2. Thus lambda_hS=2 lambda for the same canonically normalized real S. These are not different gauge/matter content.'},
    {'id': 'p02-complex', 'basis': 'source_statement', 'locator': 'Section 6.4, PDF/printed p.12 Eq.(26) and immediately surrounding paragraphs',
     'value': 'Bounded generalization is one complex gauge singlet with no extra gauge interactions. Source explicitly writes S=(S1+iS2)/sqrt(2), identifies S1,S2 as canonically normalized real singlets, and states the equivalence to two real singlets. Later extra X and dark-radiation possibilities are not part of this bounded candidate.'},
    {'id': 'p02-identity', 'basis': 'atlas_scope_reconciliation', 'locator': 'singlet and complex-singlet preflight outputs',
     'value': 'Reuse real-singlet-z2 for the main P01/P02 field content; reuse complex-singlet-portal for section 6.4 under current complex-scalar convention. Do not add another row for the alternative two-real description; current checker lacks that realification quotient, so the explicit source equivalence is retained separately.'},
    {'id': 'p02-unit', 'basis': 'atlas_mathematical_conversion_of_declared_baseline', 'locator': 'singlet and complex-singlet source candidates/preflight reports; declared F_SM/R_SM baseline',
     'value': 'One shared scale 6 over inherited textbook Y yields primitive integer hypercharges. Both candidate singlet sectors have zero hypercharge. P02 does not newly tabulate the full inherited SM charges; these are the explicit baseline coordinate.'}],
  'legacy_targets': {'entry_id': 'real-singlet-z2', 'additional_entry_ids': ['complex-singlet-portal']},
  'old_extraction_gaps_resolved': ['Real vs complex scalar distinction explicitly checked against same-version full text.',
      'Source-backed equivalence of one neutral complex singlet and two real singlets recorded without claiming checker migration.'],
  'deferred_scope': ['Section 6.2 gamma-line augmentation with charged sigma and new SU(N) is not a complete fixed numerical candidate here.',
                     'Section 6.4 extra X/dark radiation extensions left for future investigation by source.'],
  'remaining_limitations': PILOT_LIMITS,
  'candidate_factory': lambda: singlet_source('P02'), 'candidate_stem': 'singlet',
  'additional_candidates': [('complex-singlet', lambda: singlet_source('P02', True))],
 },
 'P03': {
  'arxiv_version': '1106.0034v3', 'filename': '1106.0034v3.pdf',
  'source_url': 'https://arxiv.org/pdf/1106.0034v3',
  'first_observed_utc': '2026-10-16T17:48:20Z',
  'scientific_read_started_observed_utc': None,
  'inspection': {'text_pages': [1, 5, 6, 7, 8, 9, 10, 11, 98, 151],
                 'visual_pages': [6, 9, 10, 11, 98, 151],
                 'scope': 'Initial scalar definition, Type-I/II Yukawa restrictions/Table 1; targeted section 5.9 colour and Appendix E gauge/generation checks. Not all 180 pages read.'},
  'retrievals': [{'method': 'curl_authorized_network', 'url': 'https://arxiv.org/pdf/1106.0034v3', 'outcome': 'success', 'observed_command_wall_seconds': 0.625757333}],
  'claims': [BASELINE_NOTE,
    {'id': 'p03-scalars', 'basis': 'source_statement', 'locator': 'Initial scalar-sector definition, PDF/printed p.6 Eqs.(2)-(4)',
     'value': 'Two complex scalar SU(2) doublets Phi_1,Phi_2 with source hypercharge +1. These replace the one-doublet SM scalar sector; do not add two more to R_SM.'},
    {'id': 'p03-colour', 'basis': 'source_supported_derivation', 'locator': 'Section 5.9, PDF/printed p.98 opening discussion, combined with two-doublet definition p.6',
     'value': 'Source explicitly rules out colour breaking in this two-doublet scalar inventory, supporting colour-singlet Higgs doublets; no colour-octet interpretation is introduced.'},
    {'id': 'p03-factors-families', 'basis': 'source_statement', 'locator': 'Appendix E, PDF/printed p.151, opening paragraph and Eqs.(401)-(405)',
     'value': 'Source explicitly identifies SU(3)_colour, SU(2), U(1), and then specializes the 2HDM to three fermion families. No new fermion inventory is introduced in Type-I/II.'},
    {'id': 'p03-unit', 'basis': 'source_statement_and_conversion', 'locator': 'PDF/printed p.6 Eq.(2); Appendix E PDF/printed p.151 opening normalization paragraph',
     'value': 'Early source label Y_source(H)=+1, while Appendix E says its coupling uses Higgs U(1) charge +1/2. In the early coordinate q=3 Y_source=6 Y_textbook; all fermions are expanded consistently in the same doubled-source coordinate. Do not mix the two source coordinate descriptions.'},
    {'id': 'p03-variants', 'basis': 'source_statement_and_scope_reconciliation', 'locator': 'Section 2 opening Yukawa discussion, PDF/printed pp.9-11, Table 1 p.11',
     'value': 'Type I: all RH quarks/leptons couple to Phi_2. Type II: up to Phi_2, down and charged leptons to Phi_1, with stated Z2 implementations. Same local algebra/matter, so one candidate linked to both variants. No independent rows for physical mass eigenstates or eaten Goldstones.'}],
  'legacy_targets': {'entry_id': 'two-higgs-doublets'},
  'old_extraction_gaps_resolved': ['Both Higgs colour-singlet assignments reconfirmed with specific source context.',
                                 'Whole-inventory source hypercharge coordinate and three-family count checked.'],
  'deferred_scope': ['Type III, lepton-specific, flipped, inert, neutrino-specific and other review variants outside seed Type-I/II first-pass scope.'],
  'remaining_limitations': PILOT_LIMITS + ['Pinned URL/watermark says v3 (19 Dec 2011), but arXiv PDF reprocessing gives a 2024 generated front-page date/metadata. Recorded without changing version.'],
  'candidate_factory': thdm_source, 'candidate_stem': 'thdm',
 },
 'P05': {
  'arxiv_version': '0910.1785v5', 'filename': '0910.1785v5.pdf',
  'source_url': 'https://arxiv.org/pdf/0910.1785v5',
  'first_observed_utc': '2026-10-16T17:48:23Z',
  'scientific_read_started_observed_utc': None,
  'inspection': {'text_pages': [1, 4, 5, 7, 8, 12, 13],
                 'visual_pages': [7, 8, 12],
                 'scope': 'Introduction field-content definition and section 2.1 general/Z3 superpotentials, doublets and soft/gaugino terms. Targeted neutralino paragraph. Not full 144-page review.'},
  'retrievals': [{'method': 'curl_authorized_network', 'url': 'https://arxiv.org/pdf/0910.1785v5', 'outcome': 'success', 'observed_command_wall_seconds': 0.976393708}],
  'claims': [BASELINE_NOTE,
    {'id': 'p05-gauge-singlet', 'basis': 'source_statement', 'locator': 'Introduction, PDF p.4 / printed p.3; section 2.1, PDF p.7 / printed p.6 before Eq.(2.1)',
     'value': 'NMSSM defined as MSSM plus one gauge-singlet chiral superfield S. Scalar S is explicitly complex and has no SU(3)xSU(2)xU(1)_Y quantum numbers. Introduction also explicitly identifies its fermionic superpartner.'},
    {'id': 'p05-chirals', 'basis': 'source_statement_and_declared_MSSM_baseline_expansion', 'locator': 'Section 2.1, PDF p.7 / printed p.6 Eqs.(2.2)-(2.5); introduction PDF p.5 / printed p.4',
     'value': 'Source gives Q,U_R^c,D_R^c,L,E_R^c with family indices and Hu,Hd doublets, and specifies unhatted fields are complex scalar components. Expand three inherited MSSM chiral families into one complex scalar and one LH Weyl each. Hu,Hd charges are +1/2,-1/2 in textbook Y from their component charges and inherited MSSM embedding. Source U_R^c,D_R^c,E_R^c are already conjugate chiral superfields: do not conjugate them a second time.'},
    {'id': 'p05-gauginos', 'basis': 'source_statement_and_representation_conversion', 'locator': 'Section 2.1, PDF p.12 / printed p.11 Eq.(2.30) and preceding paragraph; PDF p.13 / printed p.12 Eqs.(2.31)-(2.32)',
     'value': 'One U(1) gaugino, SU(2) adjoint gauginos i=1..3, SU(3) adjoint gauginos a=1..8. Each is ONE adjoint Weyl multiplet, not 3 or 8 copies. Singlino is one independent neutral Weyl, not the auxiliary F component; neutralino mass eigenstates are not extra fields.'},
    {'id': 'p05-variants', 'basis': 'source_statement_and_scope_reconciliation', 'locator': 'Section 2.1, PDF pp.7-8 / printed pp.6-7 Eqs.(2.1),(2.5)-(2.8)',
     'value': 'General NMSSM has mu,mu-prime,xi_F and associated soft terms. Z3 version sets these dimensionful superpotential terms and corresponding soft terms to zero; all chiral components transform by exp(2pi i/3). These restrictions do not change gauge/matter inventory, so one normalized candidate represents both source variants.'},
    {'id': 'p05-unit', 'basis': 'atlas_mathematical_conversion', 'locator': 'nmssm-source-candidate.json and nmssm-preflight.json',
     'value': 'Normalize the inherited complete MSSM-plus-singlet inventory by q=6Y. Adjoint gauginos and singlet scalar/fermion have zero hypercharge. No auxiliary fields or Hermitian-conjugate dependent fields are counted.'}],
  'legacy_targets': {'entry_id': 'nmssm-matter'},
  'old_extraction_gaps_resolved': ['Pinned-source confirmation of S scalar plus singlino; exact component accounting and superfield chirality checked.',
                                 'General and Z3 specifications retained as source variants of one matter-content candidate.'],
  'deferred_scope': ['Sections 7-9 and extra U(1), R-parity violating, constrained and mediation scenarios outside seed general/Z3 definition scope.'],
  'remaining_limitations': PILOT_LIMITS + ['Three-family MSSM representations are a declared inherited baseline, not a newly reprinted representation table in P05.'],
  'candidate_factory': nmssm_source, 'candidate_stem': 'nmssm',
 }
})

def queue():
    manifest = ROOT / 'BSM_ATLAS_SEED.md'
    text = manifest.read_text()
    pattern = r'\| (P\d\d) \| \[([^]]+)\]\([^)]+\) \| ([^|]+) \| \[PDF\]\(([^)]+)\) \| `([^`]+)` \|'
    sections = {m.group(1): {'title': m.group(2), 'text': m.group(3).strip()}
                for m in re.finditer(r'^### (P\d\d) — ([^\n]+)\n(.*?)(?=^### |^## Coverage|\Z)', text, re.M | re.S)}
    papers = []
    for pid, version, kind, url, filename in re.findall(pattern, text):
        existing = HERE / pid / 'checkpoint.json'
        checkpoint = json.loads(existing.read_text()) if existing.exists() else None
        papers.append({'paper_id': pid, 'arxiv_version': version, 'kind': kind.strip(),
                       'pdf_url': url, 'suggested_filename': filename,
                       'title': sections[pid]['title'], 'seed_scope_text': sections[pid]['text'],
                       'reextraction_status': checkpoint['status'] if checkpoint else 'queued_not_reextracted',
                       'checkpoint': str(existing.relative_to(ROOT)) if checkpoint else None,
                       'next_action': 'Curator review of staged evidence and reconciliation; no automatic ingestion.' if checkpoint else 'Read pinned source definition scope, extract, normalize and validate before proposing ingestion.'})
    assert len(papers) == 50 and len({p['paper_id'] for p in papers}) == 50
    emit(HERE / 'queue.json', {'run_id': RUN, 'authoritative_manifest': 'BSM_ATLAS_SEED.md',
         'manifest_sha256': sha256(manifest.read_bytes()).hexdigest(),
         'generated_utc': utc(), 'paper_count': 50, 'papers': papers})

def run_ledger():
    papers = []
    for pid in ['P04', 'P01', 'P02', 'P03', 'P05']:
        checkpoint_path = HERE / pid / 'checkpoint.json'
        if not checkpoint_path.exists():
            continue
        c = json.loads(checkpoint_path.read_text())
        papers.append({'paper_id': pid, 'arxiv_version': c['arxiv_version'],
          'started_utc': c['first_observed_utc'],
          'start_definition': 'Earliest recorded access observation (P04) or completed public PDF download file timestamp (others); not a sampled model-compute start.',
          'ended_utc': c['measurement'].get('first_checkpoint_utc', c['measurement']['checkpoint_utc']),
          'status': c['status'], 'source_bytes': c['source']['bytes'],
          'source_sha256': c['source']['sha256'], 'inspected': c['inspection'],
          'retrieval_attempts': len(c['retrievals']),
          'failed_or_blocked_attempts': sum(r['outcome'] != 'success' for r in c['retrievals']),
          'successful_retrieval_command_wall_seconds': sum(r.get('observed_command_wall_seconds', 0) for r in c['retrievals'] if r['outcome'] == 'success'),
          'candidates': c['reconciliation']['candidates'],
          'measurement': c['measurement'], 'checkpoint': str(checkpoint_path.relative_to(ROOT))})
    all_candidates = [r for p in papers for r in p['candidates']]
    emit(HERE / 'run-ledger.json', {'run_id': RUN, 'generated_utc': utc(),
      'status': 'pilot_staged_for_curator_review' if len(papers) == 5 else 'pilot_in_progress',
      'completed_scoped_papers': len(papers), 'queued_not_reextracted': 50 - len(papers),
      'paper_candidate_occurrences': len(all_candidates),
      'distinct_current_schema_fingerprints': len({r['fingerprint'] for r in all_candidates}),
      'source_bytes_downloaded': sum(p['source_bytes'] for p in papers),
      'successful_retrieval_command_wall_seconds': sum(p['successful_retrieval_command_wall_seconds'] for p in papers),
      'normalization_preflight_wall_seconds': sum(p['measurement']['normalization_preflight_wall_seconds'] for p in papers),
      'model_input_tokens': None, 'model_cached_input_tokens': None, 'model_output_tokens': None,
      'api_dollars': None, 'gpu_hours': None,
      'cost_warning': 'Deterministic CPU checks are cheap, but their time is NOT scientific-model inference cost. Five definition-focused papers do not establish a per-paper dollar rate or a full-50 extrapolation.',
      'immutable_source_db_sha256': SOURCE_HASH, 'database_writes': 0,
      'engineering_notes': ['During initial staging, manifest-section regex parsing and old-checkpoint timestamp compatibility required repairs; fixed and regression-tested. These were checkpoint-generation issues, not unresolved source physics.',
                            'Local Python imports may produce atlas/__pycache__; this is not source database content.'],
      'papers': papers})

def field_evidence(pid, results, data, folder):
    """Bind every submitted row/attribute back to the detailed scoped claims."""
    rows = []
    for result in results:
        stem = result['stem']
        raw = json.loads((folder / f'{stem}-source-candidate.json').read_text())
        normal = json.loads((folder / result['candidate']).read_text())
        for source_row, normalized_row in zip(raw['matter'], normal['matter']):
            label = source_row['label']
            if pid == 'P04':
                scalar = source_row['lorentz']['irreps'] == [['0', '0']]
                refs = {'gauge_algebra': ['lr-gauge', 'lr-inherited-colour'],
                    'nonabelian_irreps': ['lr-scalars' if scalar else 'lr-fermions', 'lr-inherited-colour'],
                    'source_charge': ['lr-scalars' if scalar else 'lr-derived-fermion-charges'],
                    'copies': ['lr-scalars' if scalar else 'lr-generations'],
                    'lorentz_and_reality': ['lr-complex' if scalar else 'lr-fermions'],
                    'conversion': ['lr-normalization']}
                field_ids = {'Q_L': [16,23], 'Q_R': [17,24], 'l_L': [18,25], 'l_R': [19,26],
                             'Phi': [20,27], 'Delta_L': [21,28], 'Delta_R': [22,29]}[label]
            else:
                field_ids = None
                if pid == 'P01':
                    claims = ['p01-field'] if label == 'S' else ['declared-baseline', 'p01-field']
                    conversion = 'p01-unit'
                elif pid == 'P02':
                    claims = ['p02-complex' if stem == 'complex-singlet' else 'p02-main'] if label == 'S' else ['declared-baseline', 'p02-main']
                    conversion = 'p02-unit'
                elif pid == 'P03':
                    claims = ['p03-scalars','p03-colour'] if label.startswith('Phi') else ['declared-baseline','p03-factors-families']
                    conversion = 'p03-unit'
                else:
                    claims = ['p05-gauge-singlet'] if label in {'S scalar','singlino'} else ['p05-gauginos'] if label in {'bino','wino','gluino'} else ['declared-baseline','p05-chirals']
                    conversion = 'p05-unit'
                refs = {key: claims[:] for key in ['gauge_algebra','nonabelian_irreps','source_charge','copies','lorentz_and_reality']}
                refs['conversion'] = [conversion]
            valid = {claim['id'] for claim in data['claims']}
            assert all(ref in valid for values in refs.values() for ref in values)
            rows.append({'candidate': result['candidate'], 'source_label': label,
              'normalized_label': normalized_row['label'], 'legacy_source_field_ids': field_ids,
              'source_coordinate_row': source_row, 'normalized_row': normalized_row,
              'attribute_evidence_claim_ids': refs})
    emit(folder / 'field-evidence.json', {'paper_id': pid, 'arxiv_version': data['arxiv_version'],
         'claim_dictionary': 'checkpoint.json#claims',
         'note': 'Claim IDs resolve to precise locators/basis in checkpoint.json. SM/MSSM baseline expansion is not claimed as a new source-printed table; Dynkin/Lorentz coordinates are mathematical conversions.',
         'rows': rows})

def checkpoint(pid):
    data = PAPERS[pid]
    folder = HERE / pid
    folder.mkdir(exist_ok=True)
    previous_checkpoint = folder / 'checkpoint.json'
    previous = json.loads(previous_checkpoint.read_text()) if previous_checkpoint.exists() else None
    source = HERE / 'sources' / data['filename']
    if not source.exists():
        raise SystemExit(f'Place pinned PDF at {source} before checkpointing')
    assert sha256((ROOT / 'atlas/atlas.sqlite').read_bytes()).hexdigest() == SOURCE_HASH
    preflight_start = time.perf_counter()
    cpu_start = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    stem = data['candidate_stem']
    results = []
    for stem, factory in [(stem, data['candidate_factory']), *data.get('additional_candidates', [])]:
        candidate = factory()
        emit(folder / f'{stem}-source-candidate.json', candidate)
        prepared = subprocess.run([sys.executable, str(ROOT / 'atlas/prepare_entry.py'),
                    str(folder / f'{stem}-source-candidate.json'), '--database',
                    str(ROOT / 'website/downloads/field-catalogue.sqlite')],
                   capture_output=True, text=True, check=True)
        result = json.loads(prepared.stdout)
        normalized = deepcopy(result['normalized_entry'])
        for raw, converted in zip(candidate['matter'], normalized['matter']):
            if raw['lorentz']['irreps'] == [['0', '1/2']]:
                converted['label'] = raw['label'] + '^c'
        emit(folder / f'{stem}-normalized-candidate.json', normalized)
        emit(folder / f'{stem}-preflight.json', result)
        checked = subprocess.run([sys.executable, str(ROOT / 'atlas/prepare_entry.py'),
                      str(folder / f'{stem}-normalized-candidate.json'), '--require-normalized',
                      '--database', str(ROOT / 'website/downloads/field-catalogue.sqlite')],
                     capture_output=True, text=True, check=True)
        strict_result = json.loads(checked.stdout)
        emit(folder / f'{stem}-require-normalized.json', strict_result)
        duplicate = subprocess.run([sys.executable, str(ROOT / 'atlas/check_entry.py'),
                     str(folder / f'{stem}-normalized-candidate.json'), '--database',
                     str(ROOT / 'website/downloads/field-catalogue.sqlite')],
                    capture_output=True, text=True, check=True)
        emit(folder / f'{stem}-duplicate-check.json', json.loads(duplicate.stdout))
        assert normalized == normalize_spec(normalized)
        assert result['fingerprint'] == strict_result['fingerprint']
        results.append({'stem': stem, 'fingerprint': result['fingerprint'],
                        'candidate': f'{stem}-normalized-candidate.json',
                        'duplicate_check': result['duplicate_check']})
    if pid == 'P02':
        alternative = normalize_spec(singlet_source('P02', True))
        alternative['matter'][-1]['reality'] = 'real'
        alternative['matter'][-1]['copies'] = 2
        alternative['matter'][-1]['label'] = 'S1,S2 (two real copies)'
        emit(folder / 'complex-two-real-description.json', alternative)
        emit(folder / 'scalar-equivalence.json', {
           'source': '1306.4710v5 section 6.4, PDF/printed p.12 Eq.(26) and following definition',
           'field_map': 'S=(S1+i S2)/sqrt(2)',
           'scope': 'One unconstrained neutral complex scalar and two real scalar copies, gauge/matter level.',
           'primary_description': 'complex-singlet-normalized-candidate.json',
           'alternative_description': 'complex-two-real-description.json',
           'primary_current_schema_fingerprint': results[1]['fingerprint'],
           'alternative_current_schema_fingerprint': canonicalize(alternative)['fingerprint'],
           'fingerprints_currently_equal': False,
           'action': 'Do NOT create a second catalogue entry. Explicit source equivalence is established but scalar-realification canonicalization still needs a separate implementation/migration.'})
    field_evidence(pid, results, data, folder)
    cpu_end = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu_end = resource.getrusage(resource.RUSAGE_CHILDREN)
    end = utc()
    evidence = {k: v for k, v in data.items() if k not in {'candidate_factory', 'temporary_pdf', 'additional_candidates'}}
    evidence.update({'paper_id': pid, 'run_id': RUN,
       'source': {'local_path': str(source.relative_to(ROOT)), 'bytes': source.stat().st_size,
                  'sha256': sha256(source.read_bytes()).hexdigest(), 'url': data['source_url'],
                  'version_requested': data['arxiv_version'],
                  'full_pdf_downloaded': True, 'whole_paper_scientifically_read': False},
       'status': 'completed_scoped_reextraction_staged',
       'inspection_coverage_note': 'Listed text pages identify inspected passages, not necessarily every sentence; visual pages were rendered and inspected as complete pages. Whole-paper read remains false.',
       'staged_numerical_candidates': [r['candidate'] for r in results],
       'database_write_performed': False,
       'reconciliation': {'existing_entry_to_review': data.get('legacy_targets', {}).get('entry_id'),
                          'candidates': results,
                          'policy': 'A newly complete correction is NOT a new model just because the old incomplete registry has no exact signature. Reuse the known legacy entry after review.'},
       'measurement': {'checkpoint_utc': end,
          'first_checkpoint_utc': previous['measurement'].get('first_checkpoint_utc', previous['measurement']['checkpoint_utc']) if previous else end,
          'normalization_preflight_wall_seconds': time.perf_counter() - preflight_start,
          'parent_process_user_cpu_seconds': cpu_end.ru_utime - cpu_start.ru_utime,
          'parent_process_system_cpu_seconds': cpu_end.ru_stime - cpu_start.ru_stime,
          'child_preflight_user_cpu_seconds': child_cpu_end.ru_utime - child_cpu_start.ru_utime,
          'child_preflight_system_cpu_seconds': child_cpu_end.ru_stime - child_cpu_start.ru_stime,
          'input_tokens': None, 'cached_input_tokens': None, 'output_tokens': None,
          'api_dollars': None, 'gpu_hours': None,
          'scientific_extraction_active_seconds': None,
          'source_access_active_seconds': None,
          'notes': 'Exact model token/billing/GPU telemetry and active-reading time are not exposed. UTC observations include orchestration and other work; never infer tokens from source words.'}})
    emit(folder / 'checkpoint.json', evidence)
    queue()
    run_ledger()
    print(json.dumps({'paper': pid, 'status': evidence['status'], 'checkpoint': str(folder),
                      'candidates': results,
                      'measurement': evidence['measurement']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paper', choices=[*PAPERS, 'queue'])
    args = parser.parse_args()
    if args.paper == 'queue':
        queue()
    else:
        checkpoint(args.paper)
