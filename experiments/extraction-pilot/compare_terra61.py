#!/usr/bin/env python3
"""Compare frozen Terra replay with the original Sol run; no model calls/intake.

Writes only the research result snapshot. Does not alter the original six runs,
their audited labels, frozen references, or the scientific catalogue.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from bsm_atlas.catalogue import identity, normalize, write_json
from bsm_atlas.harvest import checked_job, extracted_entries


def read(path):
    return json.loads(path.read_text())


def fingerprint(spec):
    return identity(normalize(spec))['fingerprint']


def compare():
    snapshot = HERE / 'terra61-results.json'
    if snapshot.exists() and read(snapshot)['records'][0].get('worker_response_summary'):
        from bsm_atlas.retention import seal
        data = read(snapshot)
        for row in data['records']:
            assert row['bookkeeping_sha256'] == seal({k:v for k,v in row.items() if k != 'bookkeeping_sha256'})
        assert dict(Counter(row['audit_category'] for row in data['records'])) == data['categories']
        print(json.dumps({k:v for k,v in data.items() if k not in {'records','protocol'}}, indent=2))
        return data
    frozen = read(HERE / 'results.json')
    sol = next(run for run in frozen['runs'] if run['id'] == 'sol61-revised')
    expected = read(HERE / 'expected-spectra.json')
    additional = read(HERE / 'additional-spectra.json')
    base = ROOT / '.harvest/terra61-comparison-20261026'
    run = base / 'run'
    info = read(run / 'run.json')
    assert read(base / 'pilot-status.json')['phase'] == 'complete'
    assert len(info['jobs']) == 20
    assert read(run / 'result.schema.json') == read(HERE / 'response.schema.json')
    baseline = {record['paper']: record for record in sol['records']}
    records = []
    for name in info['jobs']:
        job = run / 'jobs' / name
        meta = checked_job(job)
        previous = checked_job(ROOT / '.harvest/sol61-comparison-20261023/run/jobs' / name)
        assert meta == previous
        assert meta['prompt_sha256'] == baseline[name]['prompt_sha256']
        attempts = list(job.glob('attempt-*/metrics.json'))
        assert len(attempts) == 1
        metric = read(attempts[0])
        assert metric['model'] == 'gpt-6.1-terra' and metric['reasoning'] == 'medium'
        assert metric['usage'] is not None
        raw, state = read(job / 'result.json'), read(job / 'status.json')
        pool = ([expected[name]] if name in expected else [])
        pool += [entry['specification'] for entry in additional.get(name, [])]
        known = {fingerprint(spec) for spec in pool}
        actual, error = set(), None
        try:
            entries = extracted_entries(meta['paper'], raw)
            actual = {fingerprint(entry['specification']) for entry in entries}
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        if error:
            category = 'faulty_response'
        elif raw['outcome'] == 'retry':
            category = 'unresolved'
        elif raw['outcome'] == 'skip':
            if known:
                category = 'false_skip'
            elif baseline[name]['audit_category'] == 'correct_skip':
                category = 'correct_skip'
            else:
                category = 'unresolved'
        elif actual and actual <= known:
            category = 'matched'
        elif baseline[name]['audit_category'] == 'unresolved':
            category = 'unresolved'
        else:
            category = 'requires_source_review'
        records.append({
            'paper': name, 'audit_category': category,
            'baseline_audit_category': baseline[name]['audit_category'],
            'worker_state': state['state'], 'worker_response': raw,
            'validation_error': error,
            'reference_fingerprints': sorted(known), 'extracted_fingerprints': sorted(actual),
            'recovered_reference_fingerprints': sorted(known & actual),
            'missing_reference_fingerprints': sorted(known - actual),
            'prompt_sha256': meta['prompt_sha256'], 'text_sha256': meta['text_sha256'],
            'result_sha256': sha256((job / 'result.json').read_bytes()).hexdigest(),
            'usage': metric['usage'], 'worker_seconds': metric['elapsed_seconds']})
    usage = Counter()
    for row in records:
        usage.update(row['usage'])
    assert all(row['usage']['input_tokens'] <= 272000 for row in records)
    assert usage.get('cache_write_input_tokens', 0) == 0
    execution = read(run / 'execution-01.json')
    recovered = sum(len(row['recovered_reference_fingerprints']) for row in records)
    result = {
        'schema_version': 'matched-pilot-comparison-1', 'recorded_on': '2026-10-26',
        'model': 'gpt-6.1-terra', 'reasoning': 'medium', 'papers': 20, 'attempts': 20,
        'same_papers_and_full_prompts_as_sol': True,
        'protocol': read(base / 'protocol.json'),
        'categories': dict(Counter(row['audit_category'] for row in records)),
        'raw_proposals': sum(len(row['worker_response']['entries']) for row in records),
        'matched_spectra': sum(len(row['extracted_fingerprints']) for row in records if row['audit_category'] == 'matched'),
        'known_reference_spectra': sum(len(row['reference_fingerprints']) for row in records),
        'recovered_reference_spectra': recovered,
        'usage': dict(usage), 'wall_seconds': execution['elapsed_seconds'],
        'rates_usd_per_million': {'input': 1, 'cached_input': .05, 'output': 5},
        'rate_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-terra',
        'prices_verified_on': '2026-10-26',
        'api_equivalent_usd': ((usage['input_tokens']-usage['cached_input_tokens']) +
                               .05*usage['cached_input_tokens'] + 5*usage['output_tokens'])/1e6,
        'billing_note': 'Illustrative standard API equivalent, not subscription charges. Cached tokens '
                        'are a subset of input; reasoning is not added to output again. No cache writes.',
        'sol_baseline': {key: sol[key] for key in ('model', 'counts', 'matched_spectra', 'usage', 'wall_seconds', 'api_equivalent_usd')},
        'limitations': 'One run per model, 20 recent papers dominated by ineligible papers; no equivalence '
                       'claim or arXiv-wide accuracy estimate. Original higher-spin source adjudication '
                       'is unresolved. Extra modular EFT reference was constructed post hoc in the '
                       'previous Sol study, not an independent held-out label. Source locators are '
                       'not certified by fingerprint equality. Replay uses the frozen v2 prompts '
                       'with the current runner/validator; workflow hashes and CLI version are retained. '
                       'Concurrent production harvesting may affect latency. No model results ingested.',
        'records': records}
    write_json(HERE / 'terra61-results.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in {'records', 'protocol'}}, indent=2))
    return result


if __name__ == '__main__':
    compare()
