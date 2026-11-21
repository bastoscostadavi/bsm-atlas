"""Extraction bookkeeping, separate from gauge/matter identity.

Self-reported confidence is ordinal, not a probability of correctness. Independent
mechanical flags and seeded random audits route papers to stronger-model checks.
"""
from hashlib import sha256

VERSION = 'extraction-quality-1'


def assessment(row, result=None):
    result = result or row
    if not isinstance(result,dict):result=row
    confidence = result.get('confidence')
    if confidence not in ('high', 'medium', 'low'):
        confidence = None
    reason = result.get('uncertainty_reason')
    if not isinstance(reason, str):
        reason = None
    flags = set()
    state = row.get('state')
    if state == 'invalid': flags.add('validation_failed')
    if state in ('retry', 'interrupted'): flags.add('worker_or_extraction_unresolved')
    if state == 'source_unavailable': flags.add('source_unavailable')
    coverage = result.get('coverage', row.get('coverage'))
    if coverage in ('partial_text', 'unusable'): flags.add('incomplete_source_coverage')
    if confidence in ('medium', 'low'): flags.add('self_reported_' + confidence)
    for model in row.get('annotations', []):
        for kind in ('problems', 'mechanisms'):
            for link in model.get(kind, []):
                for flag in link.get('reviewReasons', []): flags.add('evidence:' + flag)
    for model in result.get('entries', []):
        if not isinstance(model, dict): continue
        for kind in ('problems', 'mechanisms'):
            if any(link.get('status') == 'unclear' for link in model.get(kind, []) if isinstance(link,dict)):
                flags.add('unclear_association')
    return {'schema_version': VERSION, 'confidence': confidence,
            'confidence_status': 'reported' if confidence else 'not_reported',
            'uncertainty_reason': reason, 'automatic_flags': sorted(flags),
            'needs_followup': bool(flags),
            'source_repair_required': state == 'source_unavailable' or coverage == 'unusable'}


def audit_decision(identifier, row, *, fraction=0.02, seed='atlas-luna-terra-20261108'):
    """A fixed paper-level hash gives reproducible, arrival-order-independent audits."""
    quality = row.get('quality') or assessment(row)
    if quality['source_repair_required']:
        return 'source_repair'
    if quality['needs_followup']:
        return 'flagged'
    if row.get('state') != 'ingested':
        return None
    # Preserve coverage of confidently skipped papers AND extracted inventories.
    stratum = 'skip' if row.get('outcome') == 'skip' else 'entries'
    score = int.from_bytes(sha256((seed+'|'+stratum+'|'+identifier).encode()).digest()[:8], 'big') / 2**64
    if score < fraction:
        suffix = 'unreported' if quality['confidence'] is None else 'high_confidence'
        return 'random_' + stratum + '_' + suffix
    return None
