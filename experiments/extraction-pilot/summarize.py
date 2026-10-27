#!/usr/bin/env python3
"""Freeze local pilot measurements, or check the portable report without model calls.

Default: validate results.json and its generated manuscript/report tables.
--import-local reads the registered private .harvest runs and refreshes the public,
source-text-free snapshot. --refresh-tables updates marked table blocks only.
No command changes the scientific catalogue or invokes an extraction worker.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bsm_atlas.catalogue import identity, normalize

RUNS = [
    ('terra-original', '5.6 Terra', 'gpt-5.6-terra', 'v1', 'newest-hepph-20261022', 'pilot-20', (2, .2, 12)),
    ('sol56-original', '5.6 Sol', 'gpt-5.6-sol', 'v1', 'sol56-comparison-20261022', 'run', (4, .4, 20)),
    ('sol6-original', '6 Sol', 'gpt-6-sol', 'v1', 'sol6-comparison-20261022', 'run', (2, .2, 10)),
    ('terra-revised', '5.6 Terra', 'gpt-5.6-terra', 'v2', 'terra-reprompt-20261023', 'run', (2, .2, 12)),
    ('luna-revised', '6 Luna', 'gpt-6-luna', 'v2', 'luna-comparison-20261023', 'run', (.1, .01, .5)),
    ('sol61-revised', '6.1 Sol', 'gpt-6.1-sol', 'v2', 'sol61-comparison-20261023', 'run', (2, .1, 10)),
]
CATEGORIES = ('matched', 'correct_skip', 'false_skip', 'scope_error', 'faulty_response', 'unresolved')
LABELS = {
    'accepted': 'matched', 'correct_skip': 'correct_skip', 'false_skip': 'false_skip',
    'missed_known_eligible_description': 'false_skip', 'rejected_scope': 'scope_error',
    'invalid_response': 'faulty_response', 'incomplete_proposal': 'faulty_response',
    'abstention': 'unresolved', 'unresolved': 'unresolved',
    'review_deferred': 'unresolved',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def sum_usage(records):
    total = Counter()
    for record in records:
        total.update(record['usage'])
    return dict(total)


def freeze():
    if next((ROOT / '.harvest').glob('**/compacted.json'), None):
        raise ValueError('Private payloads were intentionally removed. Verify the retained summary without --import-local; a new extraction needs fresh paper retrieval.')
    harvest = ROOT / '.harvest'
    selection = read(harvest / 'newest-hepph-20261022/selection.json')
    expected = read(harvest / 'sol56-comparison-20261022/reviewer-expected-spectra.json')
    write(HERE / 'expected-spectra.json', expected)
    additional = read(harvest / 'sol61-comparison-20261023/additional-source-spectra.json')
    write(HERE / 'additional-spectra.json', additional)
    result = {
        'schema_version': 'extraction-pilot-1', 'recorded_on': '2026-10-23',
        'catalogue_sha256': digest(ROOT / 'atlas/catalogue.json'),
        'selection': {key: selection[key] for key in ('query', 'retrieved_utc', 'feed_sha256')},
        'protocol': {'papers_per_run': 20, 'repeats_per_configuration': 1, 'workers': 2,
                     'first_invocation_limit': 1, 'remaining_invocation_limit': 19,
                     'reasoning': 'medium', 'cli_version': '0.163.0', 'authentication': 'ChatGPT',
                     'model_identifiers': 'Requested aliases; no immutable backend snapshots captured.',
                     'workflow_provenance': 'Extraction implementation was uncommitted; export-time code hashes below are not an immutable per-run code release.',
                     'review': 'Coordinating-assistant source audit; not blind independent expert labels.',
                     'automatic_retries': 0, 'catalogue_ingestion': False,
                     'prices_verified_on': '2026-10-23',
                     'cost_scope': 'Illustrative standard short-context API equivalent; excludes review and infrastructure; not subscription billing.'},
        'papers': [], 'prompt_versions': {}, 'runs': [],
        'workflow_hashes_at_export': {path: digest(ROOT / path) for path in (
            'bsm_atlas/harvest.py', 'bsm_atlas/papers.py', 'bsm_atlas/catalogue.py',
            'bsm_atlas/catalogue_identity.py', 'bsm_atlas/field_conventions.py')},
    }
    originals = None
    sol56_notes = None
    for key, label, model, version, directory, subdir, rates in RUNS:
        base = harvest / directory
        run = base / subdir
        info = read(run / 'run.json')
        report = read(base / 'pilot-report.json')
        if key == 'sol6-original':
            # Same sources as Sol 5.6; verify each matching inventory explicitly below.
            notes = sol56_notes
        else:
            notes = {item['paper']: item for item in report['source_review']}
            if key == 'sol56-original':
                sol56_notes = notes
        records = []
        for name in info['jobs']:
            job = run / 'jobs' / name
            cached = read(job / 'paper.json')
            assert digest(job / 'paper.txt') == cached['text_sha256']
            assert digest(job / 'prompt.txt') == cached['prompt_sha256']
            prefix = (job / 'prompt.txt').read_text().split('PAPER METADATA:\n', 1)[0]
            prefix_path = HERE / ('prompts/' + version + '.txt')
            if version not in result['prompt_versions']:
                prefix_path.parent.mkdir(parents=True, exist_ok=True)
                prefix_path.write_text(prefix, encoding='utf-8')
                result['prompt_versions'][version] = {
                    'prefix_file': 'prompts/' + version + '.txt',
                    'prefix_sha256': digest(prefix_path), 'context_sha256': info['context_sha256']}
            assert sha256(prefix.encode()).hexdigest() == result['prompt_versions'][version]['prefix_sha256']
            raw = read(job / 'result.json')
            state = read(job / 'status.json')
            attempts = list(job.glob('attempt-*/metrics.json'))
            assert len(attempts) == 1
            metric = read(attempts[0])
            assert metric['model'] == model and metric['reasoning'] == 'medium'
            note = dict(notes[name])
            if key == 'sol6-original' and name == '2610.29598v1':
                note['note'] = (
                    'The paper response fails because reason is empty. Both mathematical specifications '
                    'individually validate; unlike Sol 5.6, the vector has reality=complex. '
                    'The electromagnetic toy candidate is outside the SM-extension scope. '
                    'The MSSM/gravitino proposal still needs source/convention review of its '
                    'constrained higher-spin representation and is not salvaged as accepted.')
            category = LABELS[note['source_review']]
            matched = False
            if category == 'matched':
                assert raw['outcome'] == 'entries' and raw['entries']
                pool = [expected[name]] + [item['specification'] for item in additional.get(name, [])]
                allowed = {identity(normalize(s))['fingerprint'] for s in pool}
                matched = all(identity(normalize(json.loads(item['specification_json'])))['fingerprint'] in allowed for item in raw['entries'])
                assert matched
            records.append({
                'paper': name, 'worker_outcome': raw['outcome'], 'worker_state': state['state'],
                'validator_reason': state.get('reason') if state['state'] == 'invalid' else None,
                'audit_category': category, 'audit_detail': note['source_review'],
                'audit_note': note['note'], 'locator_caveat': note.get('locator_caveat'),
                'eligible_reference_match': matched, 'raw_proposals': len(raw['entries']),
                'matched_spectra': len(raw['entries']) if matched else 0,
                'worker_response_summary': {'outcome': raw['outcome'], 'entry_count': len(raw['entries']),
                    'canonical_sha256': sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()},
                'worker_response_canonical_sha256': sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                'prompt_sha256': cached['prompt_sha256'], 'result_sha256': digest(job / 'result.json'),
                'usage': metric['usage'], 'worker_seconds': metric['elapsed_seconds'],
            })
            from bsm_atlas.retention import seal
            records[-1]['bookkeeping_sha256'] = seal(records[-1])
            if originals is None:
                source = next(item for item in selection['records'] if item['arxiv'] == name)
                result['papers'].append({**cached['paper'], 'published': source['published'],
                                         'primary_category': source['primary_category'],
                                         'source_origin': cached['origin'], 'text_sha256': cached['text_sha256']})
            else:
                assert cached['paper'] == originals[name]['metadata']
                assert cached['text_sha256'] == originals[name]['text_sha256']
        if originals is None:
            originals = {p['arxiv']: {'metadata': {k: p[k] for k in ('id', 'arxiv', 'title', 'authors')},
                                       'text_sha256': p['text_sha256']} for p in result['papers']}
            schema = read(run / 'result.schema.json')
            write(HERE / 'response.schema.json', schema)
        assert read(run / 'result.schema.json') == schema
        usage = sum_usage(records)
        assert usage == report['usage']
        assert all(item['usage']['input_tokens'] <= 272000 for item in records)
        counts = {cat: sum(item['audit_category'] == cat for item in records) for cat in CATEGORIES}
        api = ((usage['input_tokens'] - usage['cached_input_tokens']) * rates[0]
               + usage['cached_input_tokens'] * rates[1] + usage['output_tokens'] * rates[2]) / 1e6
        executions = [read(path) for path in sorted(run.glob('execution-*.json'))]
        result['runs'].append({
            'id': key, 'label': label, 'model': model, 'prompt_version': version,
            'private_run_relative_path': directory + '/' + subdir,
            'context_sha256': info['context_sha256'], 'counts': counts,
            'raw_proposed_entries': sum(item['raw_proposals'] for item in records),
            'matched_spectra': sum(item['matched_spectra'] for item in records),
            'worker_retries': sum(item['worker_outcome'] == 'retry' for item in records),
            'review_deferred': sum(item['audit_detail'] == 'review_deferred' for item in records),
            'usage': usage, 'worker_seconds_sum': round(sum(item['worker_seconds'] for item in records), 3),
            'wall_seconds': round(sum(item['elapsed_seconds'] for item in executions), 3),
            'invocation_wall_seconds': [item['elapsed_seconds'] for item in executions],
            'rates_usd_per_million': dict(zip(('input', 'cached_input', 'output'), rates)),
            'rate_source': 'https://developers.openai.com/api/docs/models/' + model,
            'api_equivalent_usd': round(api, 8), 'records': records,
        })
    result['selection'].update({'pilot_rule': 'First 20 of the frozen newest-1000 hep-ph query, ordered by original submission date.',
                                'cross_listed_papers_included': True})
    result['reference_spectra_sha256'] = digest(HERE / 'expected-spectra.json')
    result['additional_spectra_sha256'] = digest(HERE / 'additional-spectra.json')
    result['response_schema_sha256'] = digest(HERE / 'response.schema.json')
    write(HERE / 'results.json', result)
    return result


def rows(data, latex=False, usage=False):
    output = []
    for run in data['runs']:
        if usage:
            u = run['usage']
            values = [run['label'], run['prompt_version'], f"{u['input_tokens']:,}",
                      f"{u['cached_input_tokens']:,}", f"{u['output_tokens']:,}",
                      f"{run['wall_seconds']:.1f}", f"{run['api_equivalent_usd']:.3f}"]
        else:
            values = [run['label'], run['prompt_version']] + [str(run['counts'][k]) for k in CATEGORIES]
        output.append((' & '.join(values) + r' \\') if latex else '| ' + ' | '.join(values) + ' |')
    if not latex:
        heading = ('| Model | Prompt | Input tokens | Cached input | Output tokens | Wall seconds | API equivalent USD |\n'
                   '|---|---|---:|---:|---:|---:|---:|') if usage else (
                   '| Model | Prompt | Matched responses | Correct skips | False skips | Scope errors | Faulty responses | Pending |\n'
                   '|---|---|---:|---:|---:|---:|---:|---:|')
        output.insert(0, heading)
    return '\n'.join(output)


def totals(data, latex=False):
    usage = sum_usage(data['runs'])
    calls = sum(len(run['records']) for run in data['runs'])
    cost = sum(run['api_equivalent_usd'] for run in data['runs'])
    seconds = sum(run['wall_seconds'] for run in data['runs'])
    if latex:
        values = {'PilotRuns': len(data['runs']), 'PilotModels': len({r['model'] for r in data['runs']}),
                  'PilotCalls': calls, 'PilotInputMillions': f"{usage['input_tokens']/1e6:.2f}",
                  'PilotOutputTokens': f"{usage['output_tokens']:,}", 'PilotAPIUSD': f'{cost:.2f}'}
        return '\n'.join('\\newcommand{\\' + key + '}{' + str(value) + '}' for key, value in values.items())
    return (f"The {len(data['runs'])} runs ({calls} calls) total {usage['input_tokens']:,} input and "
            f"{usage['output_tokens']:,} output tokens, {seconds:.1f} extraction-wall seconds, "
            f"and approximately USD {cost:.2f} at the frozen illustrative API rates.")


def marked(path, key, value, refresh):
    text = path.read_text()
    begin, end = ('% BEGIN ' + key, '% END ' + key) if path.suffix == '.tex' else ('<!-- BEGIN ' + key + ' -->', '<!-- END ' + key + ' -->')
    assert text.count(begin) == text.count(end) == 1, (path, key)
    start = text.index(begin) + len(begin)
    finish = text.index(end)
    separator = '\n' if path.suffix == '.tex' else '\n\n'
    expected = separator + value + separator
    if refresh:
        path.write_text(text[:start] + expected + text[finish:])
    elif text[start:finish] != expected:
        raise ValueError(str(path) + ' has stale ' + key + ' rows; run --refresh-tables')


def verify(data):
    assert data['schema_version'] == 'extraction-pilot-1'
    assert len(data['papers']) == 20 and len(data['runs']) == len(RUNS)
    assert digest(HERE / 'expected-spectra.json') == data['reference_spectra_sha256']
    assert digest(HERE / 'additional-spectra.json') == data['additional_spectra_sha256']
    assert digest(HERE / 'response.schema.json') == data['response_schema_sha256']
    paper_ids = [p['arxiv'] for p in data['papers']]
    assert len(set(paper_ids)) == 20
    for prompt in data['prompt_versions'].values():
        assert digest(HERE / prompt['prefix_file']) == prompt['prefix_sha256']
    for run in data['runs']:
        assert [r['paper'] for r in run['records']] == paper_ids
        assert sum(run['counts'].values()) == 20
        assert run['counts'] == {cat: sum(r['audit_category'] == cat for r in run['records']) for cat in CATEGORIES}
        assert run['usage'] == sum_usage(run['records'])
        assert run['raw_proposed_entries'] == sum(r['raw_proposals'] for r in run['records'])
        assert run['matched_spectra'] == sum(r['matched_spectra'] for r in run['records'])
        assert run['worker_retries'] == sum(r['worker_outcome'] == 'retry' for r in run['records'])
        assert run['review_deferred'] == sum(r['audit_detail'] == 'review_deferred' for r in run['records'])
        assert round(sum(r['worker_seconds'] for r in run['records']), 3) == run['worker_seconds_sum']
        assert round(sum(run['invocation_wall_seconds']), 3) == run['wall_seconds']
        rate, u = run['rates_usd_per_million'], run['usage']
        cost = ((u['input_tokens'] - u['cached_input_tokens']) * rate['input']
                + u['cached_input_tokens'] * rate['cached_input'] + u['output_tokens'] * rate['output']) / 1e6
        assert abs(cost - run['api_equivalent_usd']) < 1e-8
        for r in run['records']:
            assert r['eligible_reference_match'] == (r['audit_category'] == 'matched')
            assert r['matched_spectra'] == (r['raw_proposals'] if r['eligible_reference_match'] else 0)
            if 'worker_response_summary' in r:
                summary = r['worker_response_summary']
                assert r['raw_proposals'] == summary['entry_count']
                assert r['worker_outcome'] == summary['outcome']
                assert summary['canonical_sha256'] == r['worker_response_canonical_sha256']
                from bsm_atlas.retention import seal
                assert r['bookkeeping_sha256'] == seal({k:v for k,v in r.items() if k != 'bookkeeping_sha256'})
            else:
                assert r['raw_proposals'] == len(r['worker_response']['entries'])
                assert r['worker_outcome'] == r['worker_response']['outcome']
                assert sha256(json.dumps(r['worker_response'], sort_keys=True, ensure_ascii=False).encode()).hexdigest() == r['worker_response_canonical_sha256']
    for version in data['prompt_versions']:
        subset = [run for run in data['runs'] if run['prompt_version'] == version]
        assert len({run['context_sha256'] for run in subset}) == 1
        assert all([r['prompt_sha256'] for r in run['records']] == [r['prompt_sha256'] for r in subset[0]['records']] for run in subset)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-local', action='store_true')
    parser.add_argument('--refresh-tables', action='store_true')
    args = parser.parse_args()
    data = freeze() if args.import_local else read(HERE / 'results.json')
    verify(data)
    for filename in (HERE / 'README.md', ROOT / 'paper/main.tex'):
        for usage, key in ((False, 'PILOT RESULTS'), (True, 'PILOT USAGE')):
            marked(filename, key, rows(data, latex=filename.suffix == '.tex', usage=usage), args.refresh_tables)
        marked(filename, 'PILOT TOTALS', totals(data, latex=filename.suffix == '.tex'), args.refresh_tables)
    total = sum_usage(data['runs'])
    print(json.dumps({'papers': len(data['papers']), 'runs': len(data['runs']),
                      'calls': sum(len(r['records']) for r in data['runs']), 'usage': dict(total),
                      'api_equivalent_usd': round(sum(r['api_equivalent_usd'] for r in data['runs']), 6),
                      'wall_seconds_sum': round(sum(r['wall_seconds'] for r in data['runs']), 3),
                      'catalogue_writes': 0, 'tables': 'verified'}, indent=2))


if __name__ == '__main__':
    main()
