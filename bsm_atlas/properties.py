"""Derived, versioned entry properties. Source specifications remain untouched.

Run ``python3 -m bsm_atlas.properties --output output/entry-properties.json``.
The build uses the same assessment, so new entries acquire results automatically.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from .anomalies import assess as assess_anomalies
from .catalogue import identity
from .parameter_counts import assess as assess_parameters


def json_safe_counts(value):
    """Preserve exact counts in browser JSON, even above Number.MAX_SAFE_INTEGER."""
    if type(value) is int and abs(value) > 2 ** 53 - 1:
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe_counts(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe_counts(item) for item in value]
    return value


def assess(spec, fingerprint=None):
    fingerprint = fingerprint or identity(spec)['fingerprint']
    anomalies = assess_anomalies(spec)
    parameters = assess_parameters(spec, fingerprint)
    if anomalies['perturbative']['status'] == 'nonzero':
        parameters['physical'] = {'status': 'anomalous_spectrum', 'value': None,
            'reason': 'The recorded spectrum has a nonzero perturbative anomaly. A physical-parameter count is not assigned without a specified cancellation mechanism.'}
    return {'fingerprint': fingerprint, 'anomalies': anomalies, 'parameters': json_safe_counts(parameters)}


def summary(entries):
    return {name: dict(sorted(Counter(extract(entry['properties']) for entry in entries).items()))
            for name, extract in (
                ('perturbative', lambda p: p['anomalies']['perturbative']['status']),
                ('global', lambda p: p['anomalies']['global']['status']),
                ('total_parameters', lambda p: p['parameters']['total']['status']),
                ('physical_parameters', lambda p: p['parameters']['physical']['status']))}


def assess_entry(entry):
    return {'id': entry['id'], 'properties': assess(entry['specification'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', type=Path, default=Path(__file__).resolve().parent.parent / 'atlas/catalogue.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int, default=1, help='Independent assessment processes; output order is deterministic.')
    args = parser.parse_args()
    raw = args.catalogue.read_bytes()
    source = json.loads(raw)
    if args.workers < 1 or args.workers > 8:
        parser.error('--workers must be between 1 and 8')
    inputs = [{'id': e['id'], 'specification': e['specification']} for e in source['entries']]
    if args.workers == 1:
        entries = list(map(assess_entry, inputs))
    else:
        import sys
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            entries = []
            for entry in executor.map(assess_entry, inputs, chunksize=1):
                entries.append(entry)
                if len(entries) % 100 == 0:
                    print(f'Assessed {len(entries)}/{len(inputs)} entries', file=sys.stderr, flush=True)
    result = {'schema_version': 'atlas-properties-1', 'source_sha256': sha256(raw).hexdigest(),
              'entry_count': len(entries), 'summary': summary(entries), 'entries': entries}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'entries'}, indent=2))


if __name__ == '__main__':
    main()
