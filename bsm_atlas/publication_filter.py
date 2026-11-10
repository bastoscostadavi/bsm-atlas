"""Publish Luna-origin inventories only after a conclusive Terra extraction."""
from copy import deepcopy

from .catalogue import identity
from .literature import bind_luna_receipt


def reviewed_luna_snapshot(data, links, registry):
    """Filter a publication copy; leave ingestion records and bibliography intact.

    Completed Terra corrections qualify even while awaiting Sol. Unresolved or
    unattempted Luna paper references do not qualify. Independent older support
    from other extractors/manual records remains eligible.
    """
    if registry.get('schema_version') != 'luna-terra-entry-review-1' or not isinstance(registry.get('papers'), dict):
        raise ValueError('A valid Terra review registry is required for publication')
    result, annotations = deepcopy(data), deepcopy(links)
    papers = {paper['id']: paper for paper in result['papers']}
    records = registry['papers']
    retained, removed_refs, removed_entries, affected = [], [], [], set()
    before_by_paper = {}
    approved_entries = set()
    for original, entry in zip(data['entries'], result['entries']):
        fingerprint = identity(entry['specification'])['fingerprint']
        references = []
        for ref in entry['references']:
            paper_id = ref['paper_id']
            before_by_paper.setdefault(paper_id, []).append(original)
            paper = papers[paper_id]
            record = records.get(paper_id)
            luna_origin = paper.get('extractor', {}).get('model') == 'gpt-6-luna' or record is not None
            approved = bool(record and record.get('applied')
                and record.get('state') in ('agreement', 'disagreement')
                and record.get('model') == 'gpt-6.1-terra'
                and record.get('paper', {}).get('arxiv') == paper['arxiv']
                and fingerprint in (record.get('terra') or {}).get('fingerprints', []))
            if approved:
                approved_entries.add(entry['id'])
            if not luna_origin or approved:
                references.append(ref)
            else:
                affected.add(paper_id)
                removed_refs.append({'entry_id': entry['id'], 'paper_id': paper_id})
        entry['references'] = references
        if references:
            retained.append(entry)
        else:
            removed_entries.append(entry['id'])
    result['entries'] = retained
    fingerprints = {identity(entry['specification'])['fingerprint']: entry for entry in retained}
    for paper_id in affected:
        annotations['papers'][paper_id] = bind_luna_receipt(annotations['papers'].get(paper_id),
            before_by_paper[paper_id], retained, papers[paper_id], fingerprints=fingerprints)
    report = {'policy': 'Luna-origin model references require a completed Terra inventory review; use Terra corrections',
              'before': {'entries': len(data['entries']), 'papers': len(data['papers'])},
              'after': {'entries': len(retained), 'papers': len(result['papers'])},
              'retained_terra_reviewed_entries': len(approved_entries),
              'retained_other_supported_entries': len(retained)-len(approved_entries),
              'removed_luna_only_entry_ids': sorted(removed_entries),
              'removed_unverified_luna_references': removed_refs,
              'affected_luna_papers': len(affected)}
    return result, annotations, report
