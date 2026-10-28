"""Small extractor provenance, independent of mathematical model identity."""
from collections import Counter
from pathlib import Path
import json

EFFORTS = {'low', 'medium', 'high', 'xhigh', 'max'}


def validate_extractor(value):
    if not isinstance(value, dict) or set(value) != {'provider', 'model', 'reasoning'}:
        raise ValueError('Extractor requires exactly provider, model and reasoning')
    if not isinstance(value['provider'], str) or value['provider'] not in {'openai', 'anthropic'}:
        raise ValueError('Unsupported extractor provider')
    if not isinstance(value['model'], str) or not value['model'].strip():
        raise ValueError('Extractor model must be a nonempty identifier')
    if value['reasoning'] is not None and (not isinstance(value['reasoning'], str) or value['reasoning'] not in EFFORTS):
        raise ValueError('Invalid extractor reasoning setting')
    return value


def job_extractor(job):
    """Only a measured model call establishes attribution; never infer from defaults."""
    metrics = sorted(Path(job).glob('attempt-*/metrics.json'))
    if not metrics:
        return None
    value = json.loads(metrics[-1].read_text())
    if value.get('usage') is None:
        return None
    model = value.get('model', '')
    provider = value.get('provider')
    if provider is None:
        if model.startswith('gpt-'):
            provider = 'openai'
        elif model.startswith('claude-'):
            provider = 'anthropic'
        else:
            return None  # Old test fixtures or genuinely unestablished provenance.
    return validate_extractor({'provider': provider, 'model': model,
                               'reasoning': value.get('reasoning')})


def sync_extractors(directory, source, write=False):
    """Backfill only actual ingested calls, never discarded comparison/pilot runs."""
    from .catalogue import load, source_lock, validate, write_json
    from .retention import compact_record
    from contextlib import nullcontext
    source = Path(source).resolve()
    established = {}
    for path in Path(directory).resolve().glob('**/jobs/*/compacted.json'):
        record = compact_record(path.parent)
        receipt = record.get('ingestion')
        if (record['state'] != 'ingested' or not receipt or
                Path(receipt['source']).resolve() != source or not record.get('paper')):
            continue
        extractor = job_extractor(path.parent)
        if extractor is None:
            continue
        key = record['paper']['arxiv']
        order = record['compacted_utc']
        if key not in established or order > established[key][0]:
            established[key] = (order, extractor)
    with source_lock(source) if write else nullcontext():
        data = load(source)
        changed = []
        for paper in data['papers']:
            if paper['arxiv'] in established and 'extractor' not in paper:
                paper['extractor'] = established[paper['arxiv']][1]
                changed.append(paper['arxiv'])
        validate(data)
        if write and changed:
            write_json(source, data)
    return {'dry_run': not write, 'backfilled': len(changed),
            'established_papers': len(established),
            'unattributed_papers': sum('extractor' not in p for p in data['papers']),
            'by_extractor': dict(Counter(p['extractor']['provider'] + '/' +
                p['extractor']['model'] + '/' + str(p['extractor']['reasoning'])
                for p in data['papers'] if 'extractor' in p))}
