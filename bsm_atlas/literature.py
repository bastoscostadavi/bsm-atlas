"""Paper-backed problem/mechanism associations from joint model harvesting.

Gauge/matter identities remain in catalogue.json. This separate authoritative
store contains paper-specific associations, not new mathematical identities.
Writers hold the catalogue source lock, including when recovering an intake.
"""
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from .catalogue import ROOT, SOURCE, identity, write_json

STORE = ROOT / 'atlas/literature_links.json'
VERSION = 'atlas-literature-links-1'
BASELINE = ROOT / 'atlas/literature_baseline.json'


def preview(kind, source=SOURCE, baseline=BASELINE):
    """Rebuild public annotations from compact records, without paper text."""
    if kind not in {'problems', 'mechanisms'}:
        raise ValueError('Unknown annotation kind')
    frozen = json.loads(Path(baseline).read_text())
    if frozen.get('schema_version') != 'atlas-literature-baseline-1':
        raise ValueError('Unsupported literature baseline')
    raw = Path(source).read_bytes()
    entries = {entry['id']: entry for entry in json.loads(raw)['entries']}
    # A newer paper review replaces that paper's frozen associations, including
    # explicit removals. Other papers' baseline evidence remains authoritative.
    reviewed = {key for key, receipt in load_links(path_for(source))['papers'].items()
                if receipt.get('review')}
    inventory_only = {key for key, receipt in load_links(path_for(source))['papers'].items()
                      if receipt.get('inventory_review_scope') == 'entries'}
    result = deepcopy(frozen[kind])
    result['assessed'] = [key for key in result['assessed'] if key in entries]
    result['links'] = {key: value for key, value in result['links'].items() if key in entries}
    for key in set(result['assessed']) | set(result['links']):
        if identity(entries[key]['specification'])['fingerprint'] != frozen['entry_fingerprints'][key]:
            raise ValueError('Assessed entry changed since baseline: ' + key)
        references = {ref['paper_id'] for ref in entries[key]['references']}
        for term_id, rows in list(result['links'].get(key, {}).items()):
            rows[:] = [row for row in rows if row['paperId'] not in reviewed
                       and (row['paperId'] in references or row['paperId'] not in inventory_only)]
            if any(row['paperId'] not in references for row in rows):
                raise ValueError('Baseline link lacks its catalogue paper reference')
            if not rows:
                del result['links'][key][term_id]
        if key in result['links'] and not result['links'][key]:
            del result['links'][key]
    result['currentCatalogueSha256'] = sha256(raw).hexdigest()
    links = path_for(source)
    result['literatureLinksSha256'] = sha256(links.read_bytes()).hexdigest() if links.exists() else None
    return merge_preview(result, kind, source)


def path_for(source=SOURCE):
    return Path(source).resolve().with_name('literature_links.json')


def load_links(path=STORE):
    path = Path(path)
    if not path.exists():
        return {'schema_version': VERSION, 'papers': {}}
    data = json.loads(path.read_text())
    if set(data) != {'schema_version', 'papers'} or data['schema_version'] != VERSION or not isinstance(data['papers'], dict):
        raise ValueError('Invalid literature-link store')
    return data


def bind_luna_receipt(receipt, baseline_entries, entries, paper, *, fingerprints=None):
    """Preserve Luna evidence, binding it only to the same canonical inventory.

    Associations for withdrawn/replaced inventories stay in detached_models.
    No new application claim is inferred from a Terra spectrum correction.
    """
    result = deepcopy(receipt) if receipt is not None else {
        'arxiv': paper['arxiv'], 'extractor': None, 'models': []}
    producer = (result.get('extractor') or {}).get('model')
    if producer not in (None, 'gpt-6-luna'):
        raise ValueError('Inventory review requires the original Luna annotation receipt')
    bindings = {e['id']: identity(e['specification'])['fingerprint'] for e in baseline_entries}
    bindings.update(result.get('model_fingerprints', {}))
    candidates = [(deepcopy(model), bindings.get(model['entry_id'])) for model in result['models']]
    candidates.extend((deepcopy(row['model']), row['fingerprint'])
                      for row in result.get('detached_models', []))
    fingerprints = fingerprints if fingerprints is not None else {
        identity(e['specification'])['fingerprint']: e for e in entries}
    active, detached, active_bindings = {}, [], {}
    for model, fingerprint in candidates:
        target = fingerprints.get(fingerprint)
        if target is None or not any(ref['paper_id'] == paper['id'] for ref in target['references']):
            item = {'fingerprint': fingerprint, 'model': model}
            if item not in detached:
                detached.append(item)
            continue
        model['entry_id'] = target['id']
        stored = active.setdefault(target['id'], {'entry_id': target['id'], 'problems': [], 'mechanisms': []})
        for kind in ('problems', 'mechanisms'):
            for link in model[kind]:
                if link not in stored[kind]:
                    stored[kind].append(link)
        active_bindings[target['id']] = fingerprint
    result.update(models=list(active.values()), detached_models=detached,
                  model_fingerprints=active_bindings, annotation_layer='luna', inventory_review_scope='entries')
    result.pop('review', None)
    return result


def merge_preview(payload, kind, source=SOURCE):
    """Extend the frozen public preview without altering historical experiments."""
    catalogue = json.loads(Path(source).read_text())
    entries = {e['id']: e for e in catalogue['entries']}
    allowed = {row['id'] for row in payload['problems' if kind == 'problems' else 'mechanisms']}
    assessed = set(payload['assessed'])
    for paper_id, receipt in load_links(path_for(source))['papers'].items():
        for model in receipt['models']:
            entry_id = model['entry_id']
            if entry_id not in entries:
                continue
            if paper_id not in {r['paper_id'] for r in entries[entry_id]['references']}:
                raise ValueError('Literature link lacks its catalogue paper reference')
            assessed.add(entry_id)
            for link in model[kind]:
                if link['term_id'] not in allowed:
                    continue
                term = payload['links'].setdefault(entry_id, {}).setdefault(link['term_id'], [])
                row = {'paperId': paper_id, 'rationale': link['rationale'],
                       'evidence': link['evidence'], 'needsReview': bool(link['reviewReasons']),
                       'reviewReasons': link['reviewReasons']}
                if row not in term:
                    term.append(row)
    payload['assessed'] = sorted(assessed)
    return payload
