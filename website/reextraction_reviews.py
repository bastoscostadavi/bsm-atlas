"""Explicit, hash-pinned intake of reviewed numerical re-extractions.

Unaccepted work queues are deliberately not read by the public build. This is
an additive projection: original source fields/assertions remain recoverable.
"""
from copy import deepcopy
import hashlib
import json

from catalogue_identity import canonicalize, normalize_spec
from field_conventions import factor, dimension_a, young_rows, dynkin_representation
from spacetime_conventions import field_reps


def load_reviews(root):
    base = root / 'atlas/reextraction'
    manifest = json.loads((base / 'accepted.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unsupported accepted extraction format')
    reviews = []
    seen = set()
    for decision in manifest['reviews']:
        paper, stem = decision['paper'], decision['stem']
        if not paper.startswith('P') or not paper[1:].isdigit() or not stem.replace('-', '').isalnum():
            raise ValueError('Invalid extraction reference')
        key = (paper, stem)
        if key in seen:
            raise ValueError('Duplicate acceptance decision')
        seen.add(key)
        def pinned(name, expected):
            raw = (base / paper / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Reviewed evidence changed: ' + paper + '/' + name)
            return json.loads(raw)
        checkpoint = pinned('checkpoint.json', decision['checkpoint_sha256'])
        evidence = pinned('field-evidence.json', decision['fields_sha256'])
        filename = stem + '-normalized-candidate.json'
        candidate = json.loads((base / paper / filename).read_text())
        if candidate != normalize_spec(candidate):
            raise ValueError('Accepted payload still needs normalization')
        if canonicalize(candidate)['fingerprint'] != decision['fingerprint']:
            raise ValueError('Accepted fingerprint changed')
        if paper not in candidate.get('paper_ids', []) or checkpoint['paper_id'] != paper:
            raise ValueError('Candidate/source paper mismatch')
        rows = [r for r in evidence['rows'] if r['candidate'] == filename]
        if [r['normalized_row'] for r in rows] != candidate['matter']:
            raise ValueError('Every accepted row needs matching attribute evidence')
        claims = {c['id']: c for c in checkpoint['claims']}
        for row in rows:
            refs = row['attribute_evidence_claim_ids']
            for attribute in ['gauge_algebra', 'nonabelian_irreps', 'source_charge',
                              'copies', 'lorentz_and_reality', 'conversion']:
                if not refs.get(attribute) or not set(refs[attribute]) <= claims.keys():
                    raise ValueError('Incomplete attribute provenance')
        reviews.append({'decision': decision, 'candidate': candidate,
                        'checkpoint': checkpoint, 'fieldEvidence': rows,
                        'reviewedOn': manifest['reviewed_on'],
                        'reviewStatus': manifest['review_status'],
                        'limitations': manifest['limitations']})
    return reviews


def public_review(review):
    d, c = review['decision'], review['checkpoint']
    return {'paperId': d['paper'], 'arxiv': c['arxiv_version'],
            'candidate': d['stem'] + '-normalized-candidate.json',
            'fingerprint': d['fingerprint'], 'action': d['action'],
            'reviewedOn': review['reviewedOn'], 'reviewStatus': review['reviewStatus'],
            'inspectedScope': c['inspection']['scope'],
            'inspection': c['inspection'], 'wholePaperRead': False,
            'sourceSha256': c['source']['sha256'],
            'claims': c['claims'], 'limitations': review['limitations'],
            'evidenceURL': 'https://github.com/bastoscostadavi/bsm-atlas/tree/main/atlas/reextraction/' + d['paper']}


def replace_regime(regime, review, display_rep):
    """Replace one explicitly mapped legacy spectrum, never append duplicates."""
    spec, decision = review['candidate'], review['decision']
    roles = decision['factor_roles']
    factors = []
    for a in spec['gauge_factors']:
        if a['family'] not in {'A', 'U1'}:
            raise ValueError('This intake needs an explicit non-A-series display adapter')
        label = 'U(1)' if a['family'] == 'U1' else 'SU(' + str(a['rank'] + 1) + ')'
        parsed = factor(label, roles[a['id']])
        factors.append({**parsed, 'key': 'review:' + a['id'], 'candidateId': a['id'],
                        'groupId': None, 'normalization': None})
    factors.sort(key=lambda a: (a['type'] == 'U1', a['type'], -a['rank'], a['role']))
    for a in factors:
        if a['type'] == 'U1':
            # P04 explicitly defines the source gauge coupling for (B-L)/2.
            if decision['paper'] != 'P04' or a['candidateId'] != 'bl':
                raise ValueError('A new charge conversion needs a reviewed normalization rule')
            a['normalization'] = {'status': 'primitive_full_inventory_reextracted',
                'scale': '3', 'scope': 'complete quark/lepton/scalar inventory; q = 3(B−L)',
                'sourceReferenceUnit': 'B−L', 'sign': 'positive scaling; source orientation retained',
                'couplingRule': 'Source coupling multiplies (B−L)/2: g_atlas = g_source / 6'}
    mapping = {}
    for row in review['fieldEvidence']:
        for field_id in row['legacy_source_field_ids']:
            if field_id in mapping:
                raise ValueError('Ambiguous legacy field mapping')
            mapping[field_id] = row
    source_ids = {f['sourceFieldId'] for f in regime['fields']}
    if not source_ids or not source_ids <= mapping.keys():
        raise ValueError('Replacement would lose an original source field')
    if len(source_ids) != len(spec['matter']):
        raise ValueError('Replacement must explicitly reconcile every independent row')
    claims = {c['id']: c for c in review['checkpoint']['claims']}
    scope = {'dimension': '4', 'algebra': 'so(1,3)',
             'basis': 'source_backed_reextraction',
             'note': 'Four-dimensional quark/lepton/scalar field description checked in the pinned P04 definition scope.'}
    for f in regime['fields']:
        row = mapping[f['sourceFieldId']]
        normalized = row['normalized_row']
        # Keep the complete previous projection, including its raw source evidence.
        previous = deepcopy(f)
        kind = 'S' if normalized['lorentz']['irreps'] == [['0', '0']] else 'F'
        components = []
        for a in factors:
            rep = normalized['gauge_representations'][a['candidateId']]
            w = rep.get('dynkin')
            dim = 1 if a['type'] == 'U1' else dimension_a(w)
            if a['type'] == 'U1':
                value = rep['charge']
            else:
                # Dimensions are a display only. Exact labels always remain stored.
                value = str(dim)
                if a['rank'] > 1 and w[0] < w[-1]:
                    value = 'bar(' + value + ')'
            components.append({'factorKey': a['key'], 'factor': a['label'],
                'role': a['role'], 'value': value, 'dynkin': w,
                'youngRows': young_rows(a, w), 'dimension': dim,
                'assignmentStatus': 'source_backed_reextraction'})
        f.update(label=normalized['label'].replace('^c', 'ᶜ'), kinds=[kind],
                 copies=normalized['copies'], reality=normalized['reality'],
                 components=components, notationComplete=True, unconverted=[], inherited=None,
                 excludedCoordinate=False, legacyProjection=previous,
                 reextraction={'paperId': decision['paper'],
                    'sourceCoordinateRow': row['source_coordinate_row'],
                    'attributeEvidenceClaimIds': row['attribute_evidence_claim_ids']},
                 conversion='Source-backed re-extraction in the all-LH basis; conjugate every gauge factor, then use one shared primitive integer charge unit.')
        f['representation'] = display_rep([c['value'] for c in components], factors)
        f['dynkinRepresentation'] = dynkin_representation(components)
        f['dimension'] = 1
        for c in components:
            f['dimension'] *= c['dimension']
        f['lorentz'] = field_reps([kind], chirality='left-handed' if kind == 'F' else '',
                                  reality=normalized['reality'], scope=scope)
        for l in f['lorentz']:
            l.update(gaugeComponents=deepcopy(components), dynkinRepresentation=f['dynkinRepresentation'])
        refs = sorted({cid for ids in row['attribute_evidence_claim_ids'].values() for cid in ids})
        f['evidence'] = previous['evidence'] + [
            {'assertionId': cid, 'claim': claims[cid]['value'], 'basis': claims[cid]['basis'],
             'review': 'agent_source_checked', 'stance': 'reviewed_reextraction',
             'locations': [{'paper_version_id': review['checkpoint']['arxiv_version'],
                            'locator': claims[cid]['locator'], 'pdf_page': None}]}
            for cid in refs]
    regime.update(factors=factors, baseline=None, dimension='4',
        chargeConvention='q = 3(B−L)',
        algebra=' ⊕ '.join(a['label'] + ('_' + a['role'] if a['id'] in {'A1', 'u1'} else '') for a in factors),
        algebraSignature='+'.join(sorted(a['id'] for a in factors)),
        reextraction=public_review(review))
    regime['algebraExpanded'] = regime['algebra']
    regime['notes'] += [c['value'] for c in review['checkpoint']['claims']
                        if c['id'] in {'lr-inherited-colour', 'lr-derived-fermion-charges', 'lr-normalization', 'lr-variants'}]


def apply_reviews(entries, papers, reviews, display_rep, identity_input):
    """Only explicitly accepted reviews enter public files; staged queue is inert."""
    by_id = {e['id']: e for e in entries}
    by_paper = {p['id']: p for p in papers}
    for review in reviews:
        d, c = review['decision'], review['checkpoint']
        e = by_id[d['entry']]
        p = by_paper[d['paper']]
        if p['arxiv'] != c['arxiv_version']:
            raise ValueError('Pinned source version mismatch')
        if d['action'] == 'replace_existing':
            regimes = [r for v in e['variants'] for r in v['regimes']]
            if {r['id'] for r in regimes} != set(d['regimes']):
                raise ValueError('Replacement regime scope changed')
            for r in regimes:
                replace_regime(r, review, display_rep)
                if canonicalize(identity_input(r))['fingerprint'] != d['fingerprint']:
                    raise ValueError('Published spectrum differs from accepted normalized candidate')
            primary = next(r for r in regimes if r['id'] == e['primaryRegime'])
            for key in ['algebra', 'algebraExpanded', 'algebraSignature', 'baseline']:
                e[key] = primary[key]
            e['status'] = 'recorded_content'
            e['groupingBasis'] = 'P04 parity/C variants share one re-extracted gauge/matter spectrum; their different Yukawa restrictions do not create duplicate field-content rows.'
            e['summaryFields'] = [{k: f[k] for k in ['label', 'kinds', 'copies', 'representation', 'dynkinRepresentation', 'reality']} for f in primary['fields']]
        elif d['action'] == 'confirm_existing':
            r = next(r for v in e['variants'] for r in v['regimes'] if r['id'] == e['primaryRegime'])
            if canonicalize(identity_input(r))['fingerprint'] != d['fingerprint']:
                raise ValueError('Confirmed candidate does not match its existing entry')
        else:
            raise ValueError('Unknown acceptance action')
        e['paperIds'] = sorted(set(e['paperIds']) | {d['paper']})
        e.setdefault('reextractions', []).append(public_review(review))
        p.setdefault('reextractions', []).append({'entryId': e['id'], **public_review(review)})
    return {'acceptedPapers': len({r['decision']['paper'] for r in reviews}),
            'acceptedEntries': len({r['decision']['entry'] for r in reviews}),
            'acceptedCandidates': len(reviews), 'seedPapers': 50,
            'note': 'Accepted scoped numerical re-extractions only; unaccepted staging and agent progress do not change these counts.'}
