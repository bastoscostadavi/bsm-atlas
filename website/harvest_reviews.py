"""Accepted complete paper harvests only; unfinished work is never public data."""
from copy import deepcopy
from hashlib import sha256
import json

from catalogue_identity import canonicalize, normalize_spec
from parameterized_entry import normalize_parameterized, EXPRESSION_CONVENTION
from charge_expressions import parse_charge
from scalar_conventions import real_scalar, is_scalar
from field_conventions import irrep_dimension, irrep_dimension_label, young_rows, dynkin_representation
from core_projection import algebra_label


def claim_text(claim):
    value = claim.get('fact', claim.get('value'))
    if not isinstance(value, str) or not value.strip():
        raise ValueError('A harvested claim needs an explicit source fact')
    return value


def normalize_input(spec):
    return normalize_parameterized(spec) if spec.get('schema_version') == 'field-content-3' else normalize_spec(spec)


def input_identity(spec):
    if spec['schema_version'] != 'field-content-3':
        return canonicalize(spec)
    # Exact normalized template identity, NOT a proof of family equivalence
    # under parameter redefinitions, overlaps or multi-U(1) basis changes.
    payload = {k: deepcopy(spec[k]) for k in ['schema_version', 'gauge_factors', 'parameters', 'constraints', 'matter']}
    for row in payload['matter']: row.pop('label', None)
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return {'fingerprint': sha256(raw.encode()).hexdigest(), 'canonical_json': raw}


def symbolic_scalar(row, factors, parameters):
    """Uniform real-module display; never use a neutral probe as a model."""
    source, probe = deepcopy(row), deepcopy(row)
    polynomials = {}
    for a in factors:
        if a['family'] == 'U1':
            p = parse_charge(row['gauge_representations'][a['id']]['charge'], tuple(parameters))
            polynomials[a['id']] = p
            probe['gauge_representations'][a['id']]['charge'] = '0' if p.symbols else p.render()
    projected, kind = real_scalar(probe, factors, source['reality'])
    if any(p.symbols for p in polynomials.values()) and kind == 'real':
        raise ValueError('Symbolic scalar counting changes on charge loci; reviewed piecewise adapter required')
    # A fixed nonzero generator establishes an unambiguous scalar orientation.
    # The current source-reviewed family has nonzero SM hypercharge throughout.
    flip = any(not p.symbols and int(p.render()) != 0 and
               int(projected['gauge_representations'][key]['charge']) == -int(p.render())
               for key, p in polynomials.items())
    for key, p in polynomials.items():
        projected['gauge_representations'][key]['charge'] = parse_charge(
            '-(' + p.render() + ')' if flip else p.render(), tuple(parameters)).render()
    return projected


def load_harvest_reviews(root):
    manifest = json.loads((root / 'atlas/reextraction/accepted-harvest.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unsupported harvest acceptance version')
    reviews, seen = [], set()
    names=manifest.get('evidence_directories',['closure-20261019'])
    if not names or any(not isinstance(name,str) or len(name.split('/'))!=1 or name in {'.','..',''} for name in names):
        raise ValueError('Use explicitly named harvest evidence directories')
    directories=[(root/'atlas/reextraction'/name).resolve() for name in names]
    for decision in manifest['reviews']:
        if decision['entry'] in seen:
            raise ValueError('Duplicate harvest target')
        seen.add(decision['entry'])
        files = {}
        for kind, pin in decision['files'].items():
            path = (root / pin['path']).resolve()
            if not any(path.is_relative_to(directory) for directory in directories):
                raise ValueError('Harvest evidence outside accepted directory')
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != pin['sha256']:
                raise ValueError('Harvest evidence changed: ' + pin['path'])
            files[kind] = json.loads(raw)
        source, normalized, evidence = (files[k] for k in ['source', 'normalized', 'evidence'])
        verdict=evidence.get('decision',{})
        complete=(verdict.get('inventory_complete') and not verdict.get('not_extracted') and not verdict.get('not_specified_by_source')) if isinstance(verdict,dict) else verdict=='accept' and source.get('inventory_complete')
        if not complete:
            raise ValueError('Only complete source-supported inventories may be accepted')
        if normalize_input(source) != normalized or normalize_input(normalized) != normalized:
            raise ValueError('Harvest still needs normalization')
        if input_identity(normalized)['fingerprint'] != decision['fingerprint']:
            raise ValueError('Harvest fingerprint mismatch')
        if evidence['target_entry_id'] != decision['entry'] or evidence['paper_id'] != decision['paper']:
            raise ValueError('Harvest source target mismatch')
        if evidence['arxiv_version'] != decision['arxiv'] or decision['paper'] not in normalized['paper_ids']:
            raise ValueError('Harvest paper version mismatch')
        claims = {c['id']: c for c in evidence['claims']}
        for claim in claims.values(): claim_text(claim)
        mapping = evidence['source_field_mapping']
        if [r['candidate_label'] for r in mapping] != [r['label'] for r in source['matter']]:
            raise ValueError('Every harvested source row needs ordered provenance')
        for row in mapping:
            if not row['claim_ids'] or not set(row['claim_ids']) <= claims.keys() or not row.get('mapping_basis'):
                raise ValueError('Missing harvested row evidence')
            if not row['source_field_ids'] and row['mapping_basis'] != 'supersymmetric_gauge_multiplet_derivation' and not any(word in row['mapping_basis'].lower() for word in ['inherit', 'baseline', 'source', 'expanded']):
                raise ValueError('Unrecorded source row requires an explicit origin')
        reviews.append({'decision': decision, **files, 'reviewedOn': manifest['reviewed_on']})
    return reviews


def public_review(review):
    d, e = review['decision'], review['evidence']
    return {'paperId': d['paper'], 'arxiv': d['arxiv'],
            'candidate': d['files']['normalized']['path'].split('/')[-1],
            'fingerprint': d['fingerprint'], 'identitySchema': review['normalized']['schema_version'],
            'reviewedOn': review['reviewedOn'],
            'reviewStatus': 'agent_source_checked_curator_integrated',
            'inspectedScope': d['scope'], 'wholePaperRead': False,
            'inspection': e.get('inspection', {}), 'claims': [{**c, 'fact': claim_text(c)} for c in e['claims']],
            'limitations': d.get('limitations', []),
            'evidenceURL': 'https://github.com/bastoscostadavi/bsm-atlas/blob/main/' + d['files']['evidence']['path']}


def source_rows(source):
    """Keep source containers distinct from normalized independent LH rows."""
    result = []
    for row in source['matter']:
        l = row['lorentz']
        pair = l['dimension'] == 4 and sorted(l['irreps']) == sorted([['1/2', '0'], ['0', '1/2']])
        result.extend([row] * (2 if pair and row['reality'] != 'majorana' else 1))
    return result


def apply_harvest_reviews(entries, papers, reviews, display_rep):
    by_id, by_paper = {e['id']: e for e in entries}, {p['id']: p for p in papers}
    for review in reviews:
        d, spec, source, evidence = (review[k] for k in ['decision', 'normalized', 'source', 'evidence'])
        if d['paper'] not in by_paper:
            p=deepcopy(d.get('paper_metadata',{}))
            if not p.get('title') or not p.get('authors') or p.get('arxiv')!=d['arxiv']:
                raise ValueError('A newly harvested paper needs verified bibliographic metadata')
            p.update(id=d['paper'],kind='arxiv',inspectionStatus='field_definitions_checked',
                     reviewStatus='agent_source_checked',inspectedScope=d['scope'],
                     limitations='Definition-scope review, not whole-paper or independent physics certification.',
                     noModelReason=None)
            papers.append(p);by_paper[p['id']]=p
        if d['entry'] not in by_id:
            # Internal catalogue IDs are not fabricated legacy source IDs.
            d=deepcopy(d)
            if d.get('regime') is None:
                d['regime']=10**9+int(sha256(d['entry'].encode()).hexdigest()[:8],16)
            if any(r['id']==d['regime'] for existing in entries for v in existing['variants'] for r in v['regimes']):
                raise ValueError('New catalogue regime ID collides with an existing regime')
            variant='harvest:'+d['entry']
            e={'id':d['entry'],'name':d.get('name') or spec.get('name') or d['entry'],
               'paperIds':[d['paper']],'primaryRegime':d['regime'],'primaryVariant':variant,
               'variants':[{'id':variant,'name':d.get('name') or d['entry'],'revision':1,
                            'scope':d['scope'],'baselineSource':None,'baselineParent':None,
                            'regimes':[{'id':d['regime'],'sourceGroups':[]}]}]}
            entries.append(e);by_id[e['id']]=e
        e, paper = by_id[d['entry']], by_paper[d['paper']]
        e['paperIds']=sorted(set(e['paperIds']+[d['paper']]))
        if paper['arxiv'] != d['arxiv'] or not any(r['id'] == d['regime'] for v in e['variants'] for r in v['regimes']):
            raise ValueError('Harvest target version/regime changed')
        factors = []
        roles = d.get('factor_roles', {})
        for a in spec['gauge_factors']:
            family, rank, key = a['family'], a['rank'], a['id']
            role = roles.get(key, key)
            if key in {'colour', 'color', 'c', 'su3c'} and family == 'A' and rank == 2: role = 'colour'
            if key in {'weak', 'weak_L', 'w', 'su2l'} and family == 'A' and rank == 1: role = 'weak_L'
            if key in {'hypercharge', 'Y', 'y', 'u1y'} and family == 'U1': role = 'hypercharge'
            factors.append({'key': key, 'id': 'u1' if family == 'U1' else family + str(rank),
                            'type': family, 'rank': rank, 'label': 'u(1)' if family == 'U1' else algebra_label(family, rank),
                            'role': role, 'normalization': {'status': 'primitive_full_inventory',
                                'scope': d['scope'], 'scale': None} if family == 'U1' else None})
        origins = source_rows(source)
        if len(origins) != len(spec['matter']):
            raise ValueError('Harvest source/component correspondence changed')
        mappings = {r['candidate_label']: r for r in evidence['source_field_mapping']}
        claims = {c['id']: c for c in evidence['claims']}
        fields = []
        for i, (stored, original) in enumerate(zip(spec['matter'], origins)):
            s = deepcopy(stored)
            if spec['schema_version'] == 'field-content-3' and s['lorentz']['irreps'] == [['0', '0']]:
                s = symbolic_scalar(s, spec['gauge_factors'], spec['parameters'])
            mapping = mappings[original['label']]
            components = []
            for a in factors:
                rep = s['gauge_representations'][a['key']]
                weight = rep.get('dynkin')
                dimension = 1 if a['type'] == 'U1' else irrep_dimension(a, weight)
                components.append({'factorKey': a['key'], 'factor': a['label'], 'role': a['role'],
                    'value': rep['charge'] if a['type'] == 'U1' else irrep_dimension_label(a, weight),
                    'dynkin': weight, 'dimension': dimension, 'youngRows': young_rows(a, weight),
                    'assignmentStatus': 'source_backed_harvest'})
                if a['type'] == 'U1' and spec['schema_version'] == 'field-content-3':
                    components[-1]['chargeExpression'] = rep['charge']
            l = s['lorentz']
            kind = 'S' if is_scalar(l) else 'F' if l['dimension'] == 5 and l['irreps'] == [[0, 1]] or l['irreps'] == [['1/2', '0']] else 'V'
            label = ('(' + ', '.join(l['irreps'][0]) + ')' if l['dimension'] == 4 else
                     ' ⊕ '.join('[' + ','.join(map(str, w)) + ']' for w in l['irreps']))
            lorentz = {'component': kind, 'spacetime': {'dimension': str(l['dimension']),
                'algebra': 'so(1,' + str(l['dimension']-1) + ')', 'basis': 'source_backed_harvest', 'note': d['scope']},
                'scheme': l['scheme'], 'irreps': l['irreps'], 'label': label, 'status': 'resolved',
                'reality': s['reality'], 'copies': s['copies'], 'gaugeComponents': deepcopy(components),
                'dynkinRepresentation': dynkin_representation(components), 'alternatives': [], 'note': ''}
            if kind == 'S':
                lorentz['sourceScalar'] = {'reality': original['reality'], 'copies': original['copies'],
                                           'gaugeRepresentations': original['gauge_representations']}
            ids = mapping['source_field_ids']
            dimension = 1
            for c in components:
                if c['dimension'] is None: dimension = None; break
                dimension *= c['dimension']
            fields.append({'catalogueRowId': 'harvest:' + d['entry'] + ':' + str(i),
                'sourceFieldId': ids[0] if len(ids) == 1 else None, 'sourceFieldIds': ids,
                'label': s['label'], 'kinds': [kind], 'sourceKind': 'Source-backed independent matter row',
                'copies': s['copies'], 'reality': s['reality'], 'sourceMultiplicity': original['copies'],
                'sourceChirality': 'left-handed after normalization' if kind == 'F' and l['dimension'] == 4 else None,
                'sourceNote': mapping['mapping_basis'], 'sourceRepresentations': [],
                'excludedCoordinate': False, 'inherited': None, 'unconverted': [], 'curatedCompletion': None,
                'components': components, 'lorentz': [lorentz], 'dimension': dimension, 'notationComplete': True,
                'representation': display_rep([c['value'] for c in components], factors),
                'dynkinRepresentation': dynkin_representation(components),
                'conversion': ('Full source inventory, primitive integer charges, LH fermions and real-module scalar counting.' if l['dimension'] == 4 else
                               'Full source inventory with dimension-appropriate Lorentz representations; physical source gauge representations retained without a 4D chirality conversion.'),
                'reextraction': {'paperId': d['paper'], 'sourceMapping': mapping},
                'evidence': [{'assertionId': cid, 'claim': claim_text(claims[cid]), 'basis': claims[cid]['basis'],
                    'review': 'agent_source_checked', 'stance': 'source_harvest',
                    'locations': [{'paper_version_id': d['arxiv'], 'locator': str(claims[cid]['locator']), 'pdf_page': None}]}
                    for cid in mapping['claim_ids']]})
        v = next(v for v in e['variants'] if any(r['id'] == d['regime'] for r in v['regimes']))
        old_regime = next(r for r in v['regimes'] if r['id'] == d['regime'])
        regime = {'id': d['regime'], 'description': d['scope'], 'dimension': str(spec['matter'][0]['lorentz']['dimension']),
                  'factors': factors, 'baseline': None, 'fields': fields, 'notes': d.get('limitations', []),
                  'sourceGroups': old_regime.get('sourceGroups', []), 'reextraction': public_review(review)}
        regime['algebraExpanded'] = ' ⊕ '.join(a['label'] for a in factors)
        regime['algebra'] = regime['algebraExpanded']
        regime['algebraSignature'] = '+'.join(sorted(a['id'] for a in factors))
        e.update(name=d.get('name') or spec.get('name') or e['name'], status='recorded_content',
                 primaryRegime=d['regime'], primaryVariant=v['id'],
                 baseline=None, algebra=regime['algebra'], algebraExpanded=regime['algebraExpanded'],
                 algebraSignature=regime['algebraSignature'], publicationStatus='ready',
                 groupingBasis='Full paper-defined gauge–matter inventory. ' + d['scope'],
                 sourceVariantIds=[v['id'] for v in e['variants']],
                 variants=[{**v, 'scope': d['scope'], 'regimes': [regime]}],
                 summaryFields=[{k:f[k] for k in ['label', 'kinds', 'copies', 'representation', 'dynkinRepresentation', 'reality']} for f in fields])
        identity = input_identity(spec)
        e['identity'] = {'status': 'complete_under_stated_conventions', 'fingerprint': identity['fingerprint'],
                         'input': spec, 'canonical': json.loads(identity['canonical_json'])}
        if spec['schema_version'] == 'field-content-3':
            e['identity']['status'] = 'specified_symbolic_template_not_general_family_equivalence'
            e['parameters'], e['constraints'] = spec['parameters'], spec['constraints']
            e['expressionConvention'] = EXPRESSION_CONVENTION
            regime['parameters'], regime['constraints'] = spec['parameters'], spec['constraints']
        e.setdefault('reextractions', []).append(public_review(review))
        paper.setdefault('reextractions', []).append({'entryId': e['id'], **public_review(review)})


def publish_complete_entries(entries, retained_seed_identities=None):
    """No pending table or exclusion log. Reuse exact existing content identities."""
    complete = [e for e in entries if e['publicationStatus'] == 'ready']
    by_fingerprint = {}
    for e in complete:
        fingerprint = e['identity']['fingerprint']
        if not fingerprint:
            raise ValueError('A public entry needs a complete normalized identity')
        if not any(r['fingerprint'] == fingerprint for r in e.get('reextractions', [])) and (retained_seed_identities or {}).get(e['id']) != fingerprint:
            raise ValueError('A new complete entry needs explicit source-reviewed acceptance: ' + e['id'])
        normalized_input=normalize_input(e['identity']['input'])
        if normalized_input!=e['identity']['input'] or input_identity(normalized_input)['fingerprint'] != fingerprint:
            raise ValueError('Public identity is not normalized')
        if fingerprint not in by_fingerprint:
            by_fingerprint[fingerprint] = e
            continue
        existing = by_fingerprint[fingerprint]
        existing['paperIds'] = sorted(set(existing['paperIds'] + e['paperIds']))
        existing.setdefault('aliases', []).append({'id': e['id'], 'name': e['name']})
        existing.setdefault('reextractions', []).extend(e.get('reextractions', []))
        existing['variants'].extend(e['variants'])
    # Only complete, identity-matching regimes are browsable. Historical source
    # sectors and alternative partial regimes remain in the original snapshot.
    for e in by_fingerprint.values():
        e['sourceVariantIds'] = list(dict.fromkeys(e.get('sourceVariantIds', []) + [v['id'] for v in e['variants']]))
        for v in e['variants']:
            valid = []
            for r in v['regimes']:
                if r['id'] == e['primaryRegime'] or r.get('reextraction', {}).get('fingerprint') == e['identity']['fingerprint']:
                    valid.append(r)
            v['regimes'] = valid
        e['variants'] = [v for v in e['variants'] if v['regimes']]
    return list(by_fingerprint.values())
