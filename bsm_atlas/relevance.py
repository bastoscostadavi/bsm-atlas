"""Year-normalized citation selection from the complete INSPIRE hep-ph population.

This is a sampling heuristic, not a time-independent measure of scientific merit.
Only metadata is retrieved here; extraction remains one call per selected paper.
"""
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode

from .catalogue import SOURCE as CATALOGUE, exclusive_lock, load
from .citations import (SOURCE, QUERY, MetadataClient, base_id, cached_response,
                        parse_atom, parse_hit, private_json, resolve_expanded_version,
                        timestamp)


def posting_year(identifier):
    identifier = base_id(identifier)
    prefix = identifier.split('/')[-1][:4]
    year, month = int(prefix[:2]), int(prefix[2:])
    if not 1 <= month <= 12:
        raise ValueError('Invalid arXiv posting month: ' + identifier)
    return 1900 + year if year >= 91 else 2000 + year


def population_record(hit):
    metadata = hit.get('metadata', {})
    record_id, citations = str(hit.get('id', '')), metadata.get('citation_count')
    if not record_id.isdigit() or type(citations) is not int or citations < 0:
        raise ValueError('Missing record identity or citation count in population')
    eprints = metadata.get('arxiv_eprints')
    if not isinstance(eprints, list) or not eprints:
        raise ValueError('Population record lacks arXiv identifiers: ' + record_id)
    # Some records repeat an identical eprint for an erratum, sometimes with
    # categories absent on the duplicate. This is one identifier, not two works.
    unique = {}
    for eprint in eprints:
        identifier = base_id(eprint['value'])
        categories = eprint.get('categories', [])
        if not isinstance(categories, list) or any(not isinstance(c, str) for c in categories):
            raise ValueError('Invalid arXiv categories in INSPIRE ' + record_id)
        unique.setdefault(identifier, set()).update(categories)
    eprints = [{'value': i, 'categories': sorted(categories)} for i, categories in unique.items()]
    identifiers = list(unique)
    if not any('hep-ph' in e.get('categories', []) for e in eprints):
        raise ValueError('Population record does not include hep-ph: ' + record_id)
    return {'inspire_record_id': record_id, 'citation_count': citations,
            'arxiv_ids': sorted(identifiers),
            'cohort_year': min(map(posting_year, identifiers)),
            'metadata': {'citation_count': citations, 'arxiv_eprints': eprints,
                         **({'titles': metadata['titles']} if 'titles' in metadata else {})}}


def page_data(body):
    hits = json.loads(body).get('hits', {})
    total = hits.get('total')
    if isinstance(total, dict):
        if total.get('relation', 'eq') != 'eq':
            raise ValueError('Exact population total unavailable')
        total = total.get('value')
    if type(total) is not int or total < 0 or not isinstance(hits.get('hits'), list):
        raise ValueError('Invalid INSPIRE population page')
    return total, hits['hits']


def cohort_statistics(records):
    years = defaultdict(lambda: {'papers': 0, 'citations': 0})
    for record in records:
        cohort = years[str(record['cohort_year'])]
        cohort['papers'] += 1
        cohort['citations'] += record['citation_count']
    return dict(sorted(years.items()))


def relevance(record, statistics):
    cohort = statistics[str(record['cohort_year'])]
    return (Fraction(record['citation_count'] * cohort['papers'], cohort['citations'])
            if cohort['citations'] else Fraction(0))


def select_year_normalized(directory, count=1000, *, source=CATALOGUE, client=None,
                           arxiv_client=None, first_year=1991, last_year=None,
                           page_size=1000, batch_size=100):
    """Freeze full-population means, rank, exclude recorded works, pin versions.

    INSPIRE date partitions are used only to fit its 10,000-result window. Cohort
    years come from arXiv identifiers, not publication/INSPIRE earliest dates.
    Each INSPIRE work counts once, including zero-citation works. Multiple eprints
    of a work use their earliest posting year, and are resolved before selection.
    Metadata pages and the frozen input catalogue digest support explicit resume.
    """
    last_year = last_year or datetime.now(timezone.utc).year
    if (type(count) is not int or not 1 <= count <= 100000 or
            not 1 <= page_size <= 1000 or not 1 <= batch_size <= 200 or
            not 1991 <= first_year <= last_year <= 2090):
        raise ValueError('Invalid year-normalized selection settings')
    directory, source = Path(directory), Path(source).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive_lock(directory / 'selection.lock'):
        # INSPIRE permits 15 requests / 5 seconds. Remain below that limit;
        # arXiv requests retain the separate conservative 3.1-second interval.
        client, arxiv_client = client or MetadataClient(0.5), arxiv_client or MetadataClient()
        source_bytes = source.read_bytes()
        known = {base_id(p['arxiv']) for p in load(source)['papers']}
        request = {'ranking': 'citations / mean citations in first-posting-year cohort',
                   'query': QUERY, 'count': count, 'source': str(source),
                   'source_sha256': sha256(source_bytes).hexdigest(),
                   'first_year': first_year, 'last_year': last_year,
                   'page_size': page_size, 'batch_size': batch_size}
        config = directory / 'selection-request.json'
        if config.exists() and json.loads(config.read_text()) != request:
            raise ValueError('Selection inputs changed; use a new directory')
        if not config.exists():
            private_json(config, request)

        def checkpoint(phase, **values):
            private_json(directory / 'selection-status.json', {
                'phase': phase, 'updated_utc': timestamp(), **values})

        selection_path = directory / 'selection.json'
        if selection_path.exists():
            selection = json.loads(selection_path.read_text())
        else:
            records, seen, work_ids = [], set(), set()
            fields = 'citation_count,arxiv_eprints,titles,earliest_date'

            def retrieve(query, tag, split_year=None):
                def get(page):
                    url = SOURCE + '?' + urlencode({'q': query, 'sort': 'mostcited',
                        'fields': fields, 'size': page_size, 'page': page})
                    return page_data(cached_response(directory,
                        f'cohort-{tag}-{page:04}.json', url, client))
                total, hits = get(1)
                if total > 10000:
                    if split_year is None:
                        raise ValueError('Metadata partition exceeds INSPIRE result window: ' + tag)
                    found = sum(retrieve(QUERY + f' and earliest_date:{split_year}-{month:02}',
                                         f'{split_year}-{month:02}') for month in range(1, 13))
                    if found != total:
                        raise ValueError('Monthly metadata partitions do not cover year ' + str(split_year))
                    return total
                pages = max(1, (total + page_size - 1) // page_size)
                for page in range(1, pages + 1):
                    if page > 1:
                        observed, hits = get(page)
                        if observed != total:
                            raise ValueError('Metadata partition changed during retrieval: ' + tag)
                    expected = min(page_size, total - (page - 1) * page_size)
                    if len(hits) != expected:
                        raise ValueError('Incomplete metadata page in ' + tag)
                    for hit in hits:
                        record = population_record(hit)
                        if record['inspire_record_id'] in seen or work_ids.intersection(record['arxiv_ids']):
                            raise ValueError('Duplicate INSPIRE work across population partitions')
                        seen.add(record['inspire_record_id'])
                        work_ids.update(record['arxiv_ids'])
                        records.append(record)
                    checkpoint('metadata', partition=tag, page=page, records=len(records))
                return total

            root_url = SOURCE + '?' + urlencode({'q': QUERY, 'fields': fields, 'size': 1})
            population_total, _ = page_data(cached_response(directory, 'population-total.json', root_url, client))
            retrieve(QUERY + f' and earliest_date:<{first_year}', 'before')
            for year in range(first_year, last_year + 1):
                retrieve(QUERY + ' and earliest_date:' + str(year), str(year), year)
            retrieve(QUERY + f' and earliest_date:>{last_year}', 'after')
            retrieve(QUERY + ' and not earliest_date:*', 'undated')
            if len(records) != population_total:
                raise ValueError('Date partitions do not cover the complete hep-ph population')
            statistics = cohort_statistics(records)
            ordered = sorted(records, key=lambda r: (-relevance(r, statistics), r['arxiv_ids'][0]))
            candidates, excluded = [], 0
            for record in ordered:
                if known.intersection(record['arxiv_ids']):
                    excluded += 1
                    continue

                def resolve(record_id, identifiers):
                    url = 'https://export.arxiv.org/api/query?' + urlencode({
                        'id_list': ','.join(identifiers), 'start': 0, 'max_results': len(identifiers)})
                    return resolve_expanded_version(cached_response(directory,
                        'arxiv-resolution-' + record_id + '.json', url, arxiv_client), identifiers)

                item = parse_hit({'id': record['inspire_record_id'], 'metadata': record['metadata']}, resolve)
                score = relevance(record, statistics)
                item.update(cohort_year=record['cohort_year'],
                            score={'numerator': score.numerator, 'denominator': score.denominator})
                candidates.append(item)
                if len(candidates) == count:
                    break
            if len(candidates) != count:
                raise ValueError('Fewer new papers than requested')
            selection = {'schema_version': 'bsm-year-normalized-selection-1',
                'source': SOURCE, 'query': QUERY, 'retrieved_at': timestamp(),
                'citation_metric': request['ranking'], 'self_citations_included': True,
                'population_records': len(records), 'cohorts': statistics,
                'excluded_recorded_works_before_cutoff': excluded,
                'tie_break': 'lowest arxiv base identifier ascending',
                'count': count, 'candidates': candidates, 'catalogue_sha256': request['source_sha256'],
                'limitations': 'Within-year age differences, recent small citation counts and field mixtures remain. '
                    'This is an age/era-adjusted sampling heuristic, not intrinsic scientific relevance.'}
            private_json(selection_path, selection)
        candidates = selection['candidates']
        if len(candidates) != count or len({r['arxiv'] for r in candidates}) != count:
            raise ValueError('Frozen selection identities/count changed')
        checkpoint('pinning_versions', selected=count)
        pinned = {}
        for start in range(0, count, batch_size):
            identifiers = [r['arxiv'] for r in candidates[start:start + batch_size]]
            url = 'https://export.arxiv.org/api/query?' + urlencode({
                'id_list': ','.join(identifiers), 'start': 0, 'max_results': len(identifiers)})
            pinned.update(parse_atom(cached_response(directory,
                f'arxiv-batch-{start:05}.json', url, arxiv_client), identifiers))
        manifest = directory / f'papers-{count}.json'
        private_json(manifest, {'papers': [pinned[r['arxiv']] for r in candidates]})
        checkpoint('selection_complete', selected=count, manifest=str(manifest))
        return selection
