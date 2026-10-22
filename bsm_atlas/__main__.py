"""One command for catalogue intake, validation and export."""
import argparse
import json
from pathlib import Path
import sqlite3

from .catalogue import DATABASE, SOURCE, IncompleteContent, check, ingest, load, prepare


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='python3 -m bsm_atlas',
        description='Validate, prepare, reconcile and export precise gauge–matter specifications.')
    commands = parser.add_subparsers(dest='command', required=True)
    validate = commands.add_parser('validate', help='Validate the authoritative catalogue')
    validate.add_argument('--source', type=Path, default=SOURCE)
    add = commands.add_parser('add', help='Normalize and reconcile a candidate; dry-run unless --write is supplied')
    add.add_argument('candidate', type=Path, help='Entry object with specification and paper references')
    add.add_argument('--source', type=Path, default=SOURCE)
    add.add_argument('--write', action='store_true', help='Save the validated addition or merged references')
    preparation = commands.add_parser('prepare', help='Show a normalized specification without writing it')
    preparation.add_argument('candidate', type=Path, help='Numerical or symbolic specification JSON')
    preparation.add_argument('--database', type=Path, help='Also check for duplicates in a built SQLite export')
    preparation.add_argument('--values', type=json.loads, help='Specialize a charge family, e.g. \'{"z1":1,"z2":2}\'')
    preparation.add_argument('--require-normalized', action='store_true', help='Reject inputs needing normalization')
    lookup = commands.add_parser('lookup', help='Find exact matches and nearby entries in a built SQLite export')
    lookup.add_argument('candidate', type=Path, help='Numerical or symbolic specification JSON')
    lookup.add_argument('--database', type=Path, default=DATABASE)
    build = commands.add_parser('build', help='Generate the website data and downloads')
    build.add_argument('--check', action='store_true', help='Verify existing outputs without changing them')
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            data = load(args.source)
            print(f"Valid catalogue: {len(data['entries'])} entries, {len(data['papers'])} papers")
        elif args.command == 'add':
            candidate = json.loads(args.candidate.read_text(encoding='utf-8'))
            data, target = ingest(load(args.source), candidate)
            if args.write:
                temporary = args.source.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                temporary.replace(args.source)
            print(('Saved ' if args.write else 'Validated dry run: ') + target)
        elif args.command == 'build':
            from .build import main_data, write_outputs
            write_outputs(main_data(), check=args.check)
        else:
            candidate = json.loads(args.candidate.read_text(encoding='utf-8'))
            if args.command == 'prepare':
                result = prepare(candidate, args.database, args.values)
                if args.require_normalized and candidate != result['normalized_entry']:
                    raise IncompleteContent('Candidate needs normalization; check the normalized_entry against its source before ingestion')
            else:
                result = check(candidate, args.database)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError, AttributeError, IndexError, sqlite3.Error) as error:
        if args.command in {'prepare', 'lookup'}:
            print(json.dumps({
                'status': 'blocked_before_ingestion' if args.command == 'prepare' else 'unresolved_or_invalid_input',
                'reason': str(error),
                'action': 'Resolve the input or source data before ingestion; missing information is not a free parameter.'},
                ensure_ascii=False, indent=2))
            return 2
        parser.exit(2, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
