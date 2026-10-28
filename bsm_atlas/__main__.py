"""One command for catalogue intake, validation and export."""
import argparse
from contextlib import nullcontext, redirect_stdout
import json
from pathlib import Path
import sqlite3
import sys

from .catalogue import (DATABASE, SOURCE, IncompleteContent, check, ingest, load,
                        prepare, source_lock, write_json)


def harvest_arguments(commands):
    from .harvest import DEFAULT_MODEL
    harvest = commands.add_parser('harvest', help='Extract paper-isolated specifications and write validated entries automatically')
    actions = harvest.add_subparsers(dest='action', required=True)
    selection = actions.add_parser('select', help='Rank unrecorded primary-hep-ph papers and pin arXiv versions; no model calls')
    selection.add_argument('--output-dir', type=Path, required=True)
    selection.add_argument('--count', type=int, default=1000)
    selection.add_argument('--ranking', choices=['citations', 'year-normalized'], default='citations')
    selection.add_argument('--source', type=Path, default=SOURCE, help='Catalogue used to exclude recorded works from either ranking')
    reservation = actions.add_parser('reserve', help='Reserve a disjoint primary-hep-ph batch without model calls')
    reservation.add_argument('--output-dir', type=Path, required=True)
    reservation.add_argument('--count', type=int, default=1000)
    reservation.add_argument('--provider', choices=['codex','claude'], default='claude')
    reservation.add_argument('--ranking', choices=['citations','year-normalized'], default='citations')
    reservation.add_argument('--population-cache', type=Path)
    reservation.add_argument('--source', type=Path, default=SOURCE)
    registration = actions.add_parser('register', help='Register an existing manifest so other providers cannot reserve its papers')
    registration.add_argument('manifest', type=Path)
    registration.add_argument('--provider', choices=['codex','claude'], default='codex')
    registration.add_argument('--source', type=Path, default=SOURCE)
    attribution = actions.add_parser('sync-extractors', help='Backfill measured extractor provenance from compact receipts; no model calls')
    attribution.add_argument('directory', type=Path)
    attribution.add_argument('--source', type=Path, default=SOURCE)
    attribution.add_argument('--write', action='store_true')
    launch = actions.add_parser('launch', help='Durably launch a reserved provider batch; dry-run unless --execute')
    launch.add_argument('manifest', type=Path)
    launch.add_argument('--run-dir', type=Path, required=True)
    launch.add_argument('--provider', choices=['codex','claude'], default='claude')
    launch.add_argument('--model', required=True, help='Explicit model identifier; no automatic model selection or fallback')
    launch.add_argument('--reasoning', choices=['low','medium','high','xhigh','max'], default='medium')
    launch.add_argument('--workers', type=int, default=1)
    launch.add_argument('--fetch-size', type=int, default=1)
    launch.add_argument('--timeout', type=float, default=900)
    launch.add_argument('--claude', default='claude')
    launch.add_argument('--codex', default='codex')
    launch.add_argument('--execute', action='store_true')
    launch.add_argument('--resume', action='store_true')
    preparation = actions.add_parser('prepare', help='Retrieve pinned papers and create isolated prompts; no model calls')
    preparation.add_argument('manifest', type=Path)
    preparation.add_argument('--run-dir', type=Path, required=True)
    preparation.add_argument('--source', type=Path, default=SOURCE)
    preparation.add_argument('--resume', action='store_true', help='Resume cached inputs; recorded papers are skipped unless --retry is explicit')
    preparation.add_argument('--retry', action='store_true', help='With --resume, explicitly retry old failed retrievals rather than skip recorded papers')
    preparation.add_argument('--limit', type=int, help='Prepare at most this many not-yet-cached papers')
    expansion = actions.add_parser('expand', help='Checkpointed retrieval, extraction and automatic validated ingestion')
    expansion.add_argument('manifest', type=Path)
    expansion.add_argument('--run-dir', type=Path, required=True)
    expansion.add_argument('--execute', action='store_true')
    expansion.add_argument('--resume', action='store_true')
    expansion.add_argument('--reconfigure', action='store_true', help='With --resume, explicitly change only worker/fetch controls')
    expansion.add_argument('--model', default=DEFAULT_MODEL)
    expansion.add_argument('--workers', type=int, default=2)
    expansion.add_argument('--codex', default='codex')
    expansion.add_argument('--provider', choices=['codex','claude'], default='codex')
    expansion.add_argument('--claude', default='claude', help='Claude Code executable when --provider=claude')
    expansion.add_argument('--reasoning', choices=['low', 'medium', 'high', 'xhigh', 'max'], default='medium')
    expansion.add_argument('--timeout', type=float, default=900)
    expansion.add_argument('--fetch-size', type=int, default=5)
    run = actions.add_parser('run', help='Preview extraction jobs; --execute launches workers')
    run.add_argument('directory', type=Path)
    run.add_argument('--execute', action='store_true')
    run.add_argument('--model', default=DEFAULT_MODEL)
    run.add_argument('--workers', type=int, default=2)
    run.add_argument('--codex', default='codex', help='Path to a current Codex CLI executable')
    run.add_argument('--provider', choices=['codex','claude'], default='codex')
    run.add_argument('--claude', default='claude')
    run.add_argument('--reasoning', choices=['none', 'low', 'medium', 'high', 'xhigh', 'max'], default='medium')
    run.add_argument('--timeout', type=float, default=900)
    run.add_argument('--limit', type=int, help='Maximum number of papers to launch in this invocation')
    run.add_argument('--retry', action='store_true', help='Explicitly rerun failed/invalid workers; may consume more usage')
    summary = actions.add_parser('status', help='Show paper states, elapsed time and reported token usage')
    summary.add_argument('directory', type=Path)
    cleanup = actions.add_parser('cleanup', help='Remove temporary payloads using compact resume receipts')
    cleanup.add_argument('directory', type=Path)
    cleanup.add_argument('--source', type=Path)
    cleanup.add_argument('--write', action='store_true')
    cleanup.add_argument('--discard-uningested', action='store_true', help='Explicitly retire old pilot/unimported terminal responses without ingestion')
    synchronization = actions.add_parser('sync-status', help='Backfill paper extraction markers from a saved run; never adds models')
    synchronization.add_argument('directory', type=Path)
    synchronization.add_argument('--source', type=Path, default=SOURCE)
    synchronization.add_argument('--manifest', type=Path, help='Original frozen manifest; supplies metadata for retrieval failures')
    synchronization.add_argument('--write', action='store_true')
    inspection = actions.add_parser('inspect', help='Optional read-only inspection of one extraction; no approval gate')
    inspection.add_argument('directory', type=Path)
    inspection.add_argument('job', help='Paper job identifier shown by status')
    ingestion = actions.add_parser('ingest', help='Import saved valid extractions without another model pass; dry-run unless --write')
    ingestion.add_argument('directory', type=Path)
    ingestion.add_argument('--source', type=Path, default=SOURCE)
    ingestion.add_argument('--write', action='store_true')
    ingestion.add_argument('--rebuild', action='store_true', help='Regenerate website/SQLite after writing the authoritative source')


def harvest_command(args):
    from . import harvest
    if args.action == 'register':
        from .allocations import register_manifest
        row = register_manifest(args.manifest, args.provider, args.source)
        return {'registered': len(row['arxiv_base_ids']), 'provider': row['provider'],
                'manifest': row['manifest'], 'model_calls': 0}
    if args.action == 'reserve':
        from .allocations import reserve_batch
        return reserve_batch(args.output_dir, args.count, provider=args.provider, ranking=args.ranking,
                             population_cache=args.population_cache, source=args.source)
    if args.action == 'sync-extractors':
        from .extractors import sync_extractors
        return sync_extractors(args.directory, args.source, args.write)
    if args.action == 'launch':
        from .launch import launch_expansion
        return launch_expansion(args.manifest, args.run_dir, model=args.model, provider=args.provider,
            executable=args.claude if args.provider == 'claude' else args.codex, reasoning=args.reasoning,
            workers=args.workers, fetch_size=args.fetch_size, timeout=args.timeout,
            execute=args.execute, resume=args.resume)
    if args.action == 'select':
        from .relevance import select_population
        selection = select_population(args.output_dir, args.count, source=args.source,
                                      ranking=args.ranking, primary_only=True)
        return {'papers': selection['count'], 'selection': str(args.output_dir / 'selection.json'),
                'manifest': str(args.output_dir / f'papers-{args.count}.json'),
                'citation_metric': selection['citation_metric'],
                'primary_category': selection['primary_category'],
                'population_records': selection['population_records'],
                'citation_range': [selection['candidates'][0]['citation_count'],
                                   selection['candidates'][-1]['citation_count']]}
    if args.action == 'prepare':
        return harvest.prepare_batch(args.manifest, args.run_dir, args.resume, args.source,
                                     limit=args.limit, retry=args.retry)
    if args.action == 'expand':
        from .expansion import expand_batch
        return expand_batch(args.manifest, args.run_dir, args.execute, args.resume, args.model,
                            args.workers, args.claude if args.provider == 'claude' else args.codex,
                            args.reasoning, args.timeout, args.fetch_size,
                            reconfigure=args.reconfigure, provider=args.provider)
    if args.action == 'run':
        if args.execute:
            from .retention import VERSION as RETENTION_VERSION
            write_json(args.directory / 'retention.json',
                       {'delete_payloads': True, 'schema_version': RETENTION_VERSION})
        return harvest.run_batch(args.directory, args.execute, args.model, args.workers,
                                 args.claude if args.provider == 'claude' else args.codex,
                                 args.reasoning, args.timeout, args.retry, args.limit, provider=args.provider)
    if args.action == 'status':
        return harvest.status(args.directory)
    if args.action == 'cleanup':
        from .retention import cleanup_run
        return cleanup_run(args.directory, source=args.source, write=args.write,
                           discard_uningested=args.discard_uningested)
    if args.action == 'sync-status':
        return harvest.record_extractions(args.directory, args.source, args.write, manifest_path=args.manifest)
    if args.action == 'inspect':
        return harvest.inspect_result(args.directory, args.job)
    return harvest.ingest_batch(args.directory, args.source, args.write, args.rebuild)


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
    harvest_arguments(commands)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            data = load(args.source)
            print(f"Valid catalogue: {len(data['entries'])} entries, {len(data['papers'])} papers")
        elif args.command == 'add':
            candidate = json.loads(args.candidate.read_text(encoding='utf-8'))
            source = args.source.resolve()
            with source_lock(source) if args.write else nullcontext():
                data, target = ingest(load(source), candidate)
                if args.write:
                    write_json(source, data)
            print(('Saved ' if args.write else 'Validated dry run: ') + target)
        elif args.command == 'harvest':
            with redirect_stdout(sys.stderr):
                result = harvest_command(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == 'build':
            from .build import main_data, write_outputs
            with source_lock() if not args.check else nullcontext():
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
