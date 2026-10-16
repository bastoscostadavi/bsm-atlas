"""Hash-pinned current-convention intake; never read a mutable agent queue."""
from copy import deepcopy
import hashlib
import json

from catalogue_identity import canonicalize, normalize_spec
from field_conventions import factor, dimension_a, young_rows, dynkin_representation
from spacetime_conventions import field_reps


def load_current_reviews(root):
    manifest = json.loads((root / 'atlas/reextraction/accepted-followup.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unsupported current-review manifest')
    reviews, seen = [], set()
    for decision in manifest['reviews']:
        entry = decision['entry']
        if entry in seen:
            raise ValueError('Duplicate current-review entry')
        seen.add(entry)
        files = {}
        for kind, pin in decision['files'].items():
            path = (root / pin['path']).resolve()
            if not path.is_relative_to((root / 'atlas/reextraction/followup-20261016').resolve()):
                raise ValueError('Review path outside accepted evidence directory')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != pin['sha256']:
                raise ValueError('Reviewed evidence changed: ' + pin['path'])
            files[kind] = json.loads(raw)
        source, normalized, evidence, fields = (files[k] for k in ['source', 'normalized', 'evidence', 'fields'])
        if normalize_spec(source) != normalized or normalize_spec(normalized) != normalized:
            raise ValueError('Current candidate does not match its source normalization')
        if canonicalize(normalized)['fingerprint'] != decision['fingerprint']:
            raise ValueError('Current accepted fingerprint changed')
        if evidence['target_entry_id'] != entry or evidence['paper_id'] != decision['paper'] or decision['paper'] not in normalized['paper_ids']:
            raise ValueError('Current review target/source mismatch')
        claims = {c['id']: c for c in evidence['claims']}
        if [r['source_row'] for r in fields['rows']] != source['matter']:
            raise ValueError('Every source row needs exact attribute evidence')
        for row in fields['rows']:
            mapping = row['mapping']
            if not mapping['source_field_ids'] or not mapping['claim_ids'] or not set(mapping['claim_ids']) <= claims.keys():
                raise ValueError('Missing current row provenance')
        if [r['mapping'] for r in fields['rows']] != evidence['source_field_mapping']:
            raise ValueError('Current source-field mappings disagree')
        reviews.append({'decision': decision, **files, 'reviewedOn': manifest['reviewed_on'],
                        'reviewStatus': manifest['review_status']})
    return reviews


def public_current_review(review):
    d, evidence = review['decision'], review['evidence']
    sources = evidence['sources']
    return {'paperId': d['paper'], 'arxiv': evidence['arxiv_version'],
            'candidate': d['files']['normalized']['path'].split('/')[-1],
            'fingerprint': d['fingerprint'], 'identitySchema': 'field-content-2',
            'action': 'replace_primary_from_reviewed_source',
            'reviewedOn': review['reviewedOn'], 'reviewStatus': review['reviewStatus'],
            'inspectedScope': d['scope'], 'inspection': {'scope': d['scope'], 'sources': sources},
            'wholePaperRead': False, 'sourceSha256': sources[0]['sha256'],
            'claims': [{**c, 'value': c['fact']} for c in evidence['claims']],
            'limitations': d['limitations'],
            'evidenceURL': 'https://github.com/bastoscostadavi/bsm-atlas/blob/main/' + d['files']['evidence']['path']}


def apply_current_reviews(entries, papers, reviews, display_rep):
    by_id, by_paper = ({e['id']: e for e in entries}, {p['id']: p for p in papers})
    # Snapshot before replacement: inherited fields retain their actual source
    # model/regime, even if the parent is also corrected in this batch.
    originals = {(e['id'], r['id'], f['sourceFieldId']): deepcopy(f)
                 for e in entries for v in e['variants'] for r in v['regimes'] for f in r['fields']}
    for review in reviews:
        d, source = review['decision'], review['source']
        entry, paper = by_id[d['entry']], by_paper[d['paper']]
        if paper['arxiv'] != review['evidence']['arxiv_version'] or entry['primaryRegime'] != d['regime']:
            raise ValueError('Current review source version/regime changed')
        regime = next(r for v in entry['variants'] for r in v['regimes'] if r['id'] == d['regime'])
        factors = []
        for a in source['gauge_factors']:
            # New gauge families/U(1) conversions require a reviewed adapter.
            if a['family'] != 'A':
                raise ValueError('Current source adapter only supports reviewed A-series spectra')
            factors.append({**factor('SU(' + str(a['rank'] + 1) + ')', 'unified'),
                            'key': 'review:' + a['id'], 'candidateId': a['id'],
                            'groupId': None, 'normalization': None})
        mapped_ids = [i for row in review['fields']['rows'] for i in row['mapping']['source_field_ids']]
        connections = [deepcopy(f) for f in regime['fields'] if f['excludedCoordinate']]
        if {f['sourceFieldId'] for f in connections} != set(d.get('excluded_connection_ids', [])):
            raise ValueError('Excluded gauge-connection coordinates need an explicit acceptance decision')
        original_ids = {f['sourceFieldId'] for f in regime['fields'] if not f['excludedCoordinate']}
        if len(mapped_ids) != len(set(mapped_ids)) or not original_ids <= set(mapped_ids):
            raise ValueError('Replacement would lose or ambiguously map an original source field')
        fields = []
        for row in review['fields']['rows']:
            s, mapping = row['source_row'], row['mapping']
            if len(mapping['source_field_ids']) != 1:
                raise ValueError('Current adapter requires one explicit source container per row')
            key = (mapping['source_model_id'], mapping['source_regime_id'], mapping['source_field_ids'][0])
            old = originals[key]
            f, components = deepcopy(old), []
            for a in factors:
                w = s['gauge_representations'][a['candidateId']]['dynkin']
                dimension = dimension_a(w)
                value = str(dimension)
                # A display hint only: identity always uses exact highest weights.
                if tuple(w) < tuple(reversed(w)):
                    value = 'bar(' + value + ')'
                components.append({'factorKey': a['key'], 'factor': a['label'], 'role': a['role'],
                    'value': value, 'dynkin': w, 'youngRows': young_rows(a, w), 'dimension': dimension,
                    'assignmentStatus': 'source_backed_reextraction'})
            kind = 'S' if s['lorentz']['irreps'] == [['0', '0']] else 'F'
            if s['lorentz']['irreps'] not in [[['0', '0']], [['1/2', '0']]]:
                raise ValueError('Unreviewed source Lorentz representation')
            scope = {'dimension': '4', 'algebra': 'so(1,3)', 'basis': 'source_backed_reextraction',
                     'note': d['scope']}
            f.update(label=s['label'], kinds=[kind], copies=s['copies'], reality=s['reality'],
                     components=components, notationComplete=True, unconverted=[], inherited=None,
                     excludedCoordinate=False, legacyProjection=old,
                     reextraction={'paperId': d['paper'], 'sourceMapping': mapping},
                     conversion='Source-backed all-left-handed inventory; scalar containers projected to canonical real modules.')
            f['representation'] = display_rep([c['value'] for c in components], factors)
            f['dynkinRepresentation'] = dynkin_representation(components)
            f['dimension'] = 1
            for c in components:
                f['dimension'] *= c['dimension']
            f['lorentz'] = field_reps([kind], chirality='left-handed' if kind == 'F' else '',
                                      reality=s['reality'], scope=scope)
            for l in f['lorentz']:
                l.update(gaugeComponents=deepcopy(components), dynkinRepresentation=f['dynkinRepresentation'])
            claims = {c['id']: c for c in review['evidence']['claims']}
            f['evidence'] += [{'assertionId': cid, 'claim': claims[cid]['fact'], 'basis': claims[cid]['basis'],
                              'review': 'agent_source_checked', 'stance': 'reviewed_reextraction',
                              'locations': [{'paper_version_id': review['evidence']['arxiv_version'],
                                             'locator': claims[cid]['locator'], 'pdf_page': None}]}
                             for cid in mapping['claim_ids']]
            fields.append(f)
        regime.update(factors=factors, fields=fields+connections, baseline=None, dimension='4',
                      algebra=' ⊕ '.join(a['label'] for a in factors),
                      algebraSignature='+'.join(sorted(a['id'] for a in factors)),
                      reextraction=public_current_review(review))
        regime['algebraExpanded'] = regime['algebra']
        for key in ['algebra', 'algebraExpanded', 'algebraSignature', 'baseline']:
            entry[key] = regime[key]
        entry['status'] = 'recorded_content'
        entry['summaryFields'] = [{k: f[k] for k in ['label', 'kinds', 'copies', 'representation', 'dynkinRepresentation', 'reality']} for f in fields]
        entry.setdefault('reextractions', []).append(public_current_review(review))
        paper.setdefault('reextractions', []).append({'entryId': entry['id'], **public_current_review(review)})
