"""Private, resumable citation-ranked selection; never modifies atlas data.

INSPIRE citation_count includes self citations. Selection covers every year and
cross-listing in hep-ph, without making a claim about BSM relevance.
"""
import base64
import gzip
import io
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from .catalogue import exclusive_lock, write_json
from .papers import ATOM, arxiv_id

QUERY = 'arxiv_eprints.categories:hep-ph'
SOURCE = 'https://inspirehep.net/api/literature'
FIELDS = 'citation_count,arxiv_eprints,titles'
MAX_RESPONSE = 8_000_000
BASE_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v[1-9]\d*)?\Z')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def base_id(value):
    if not isinstance(value, str) or not BASE_ID.fullmatch(value):
        raise ValueError('Invalid arXiv identifier in metadata: ' + repr(value))
    return re.sub(r'v[1-9]\d*$', '', value)


def safe_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or
            parsed.port not in (None, 443) or parsed.fragment or
            (parsed.hostname, parsed.path.rstrip('/')) not in {
                ('inspirehep.net', '/api/literature'),
                ('export.arxiv.org', '/api/query')}):
        raise ValueError('Unexpected metadata URL: ' + url)
    return url


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        if urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            raise ValueError('Metadata redirect changed the service')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class MetadataClient:
    """Serial bounded requests; arXiv-safe by default, no automatic retries."""
    def __init__(self, minimum_interval=3.1):
        if not isinstance(minimum_interval, (int, float)) or not isfinite(minimum_interval) or minimum_interval < 0:
            raise ValueError('Invalid metadata request interval')
        self.minimum_interval = minimum_interval
        self.last_request = time.monotonic()
        self.opener = build_opener(SafeRedirect())

    def get(self, url):
        safe_url(url)
        time.sleep(max(0, self.minimum_interval - (time.monotonic() - self.last_request)))
        try:
            request = Request(url, headers={'User-Agent':
                'bsm-atlas/1 (+https://github.com/bastoscostadavi/bsm-atlas)',
                'Accept': 'application/json, application/atom+xml'})
            with self.opener.open(request, timeout=45) as response:
                safe_url(response.geturl())
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise ValueError('Metadata response exceeds size bound')
                return body
        except HTTPError as error:
            if error.code in (403, 429):
                raise ValueError('Metadata service returned HTTP ' + str(error.code) +
                    '; stop and resume later after the service permits requests. '
                    'Retry-After: ' + str(error.headers.get('Retry-After', 'unspecified'))) from error
            raise
        finally:
            self.last_request = time.monotonic()


def parse_hit(hit, resolve=None):
    """Parse one unambiguous INSPIRE record; absent counts are never zero."""
    if not isinstance(hit, dict) or not isinstance(hit.get('metadata'), dict):
        raise ValueError('Missing INSPIRE metadata')
    metadata = hit['metadata']
    record_id = str(hit.get('id', ''))
    if not record_id.isdigit():
        raise ValueError('Invalid INSPIRE record id')
    count = metadata.get('citation_count')
    if type(count) is not int or count < 0:
        raise ValueError('Missing or invalid citation_count for INSPIRE ' + record_id)
    eprints = metadata.get('arxiv_eprints')
    if (not isinstance(eprints, list) or not eprints or
            any(not isinstance(item, dict) for item in eprints)):
        raise ValueError('Missing or ambiguous arXiv metadata for INSPIRE ' + record_id)
    identifiers = [base_id(item.get('value')) for item in eprints]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate arXiv metadata for INSPIRE ' + record_id)
    resolution = None
    if len(eprints) > 1:
        if resolve is None:
            raise ValueError('Missing or ambiguous arXiv metadata for INSPIRE ' + record_id)
        resolution = resolve(record_id, identifiers)
        identifier = resolution['representative']
        if identifier not in identifiers:
            raise ValueError('Resolution refers to a different arXiv work')
    else:
        identifier = identifiers[0]
    selected = eprints[identifiers.index(identifier)]
    categories = selected.get('categories')
    if (not isinstance(categories, list) or not categories or
            any(not isinstance(item, str) or not item.strip() for item in categories) or
            len(set(categories)) != len(categories) or 'hep-ph' not in categories):
        raise ValueError('Missing or invalid hep-ph categories for ' + identifier)
    titles = metadata.get('titles')
    if not isinstance(titles, list) or not titles or not isinstance(titles[0], dict):
        raise ValueError('Missing title for ' + identifier)
    title = titles[0].get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('Missing title for ' + identifier)
    result = {'arxiv': identifier, 'citation_count': count,
            'inspire_record_id': record_id, 'categories': sorted(categories),
            'title': ' '.join(title.split())}
    if resolution is not None:
        result['alternate_arxiv_ids'] = sorted(set(identifiers) - {identifier})
        result['identity_resolution'] = resolution
    return result


def parse_page(content, resolve=None, minimum_count=None):
    data = json.loads(content)
    hits = data.get('hits', {})
    total = hits.get('total')
    if isinstance(total, dict):
        if total.get('relation', 'eq') != 'eq':
            raise ValueError('INSPIRE did not provide an exact total')
        total = total.get('value')
    if type(total) is not int or total < 0 or not isinstance(hits.get('hits'), list):
        raise ValueError('Invalid INSPIRE search page')
    records = []
    for hit in hits['hits']:
        count = hit.get('metadata', {}).get('citation_count')
        if type(count) is not int or count < 0:
            raise ValueError('Missing or invalid citation_count')
        if minimum_count is not None and count < minimum_count:
            # A later record cannot affect selection or the cutoff tie. Do not
            # resolve unrelated aliases or request their arXiv metadata.
            records.append({'citation_count': count, '_below_cutoff': True})
            break
        records.append(parse_hit(hit, resolve))
    return total, records


def resolve_expanded_version(content, identifiers):
    """Resolve explicit expanded versions or a primary paper with an addendum.

    No chronological guess, title similarity or citation split is sufficient.
    Other merged-record relationships require separate metadata review.
    """
    parsed = parse_atom(content, identifiers)
    entries = ET.fromstring(content).findall(ATOM + 'entry')
    namespace = '{http://arxiv.org/schemas/atom}'
    details = {}
    for entry in entries:
        identifier = base_id(entry.findtext(ATOM + 'id').split('/abs/')[-1])
        details[identifier] = {
            'doi': entry.findtext(namespace + 'doi', '').strip().lower(),
            'authors': parsed[identifier]['authors'],
            'title': parsed[identifier]['title'].casefold(),
            'summary': ' '.join(entry.findtext(ATOM + 'summary', '').split())}
    if len(identifiers) != 2:
        raise ValueError('Ambiguous merged INSPIRE work: more than two arXiv IDs')
    expanded = []
    for identifier, detail in details.items():
        other = next(value for value in identifiers if value != identifier)
        marker = 'expanded version of ' + other
        if (marker in detail['summary'].lower() and detail['doi'] and
                detail['doi'] == details[other]['doi'] and
                detail['authors'] == details[other]['authors']):
            expanded.append(identifier)
    if len(expanded) != 1:
        originals = []
        for identifier, detail in details.items():
            other = next(value for value in identifiers if value != identifier)
            related = details[other]
            if (detail['doi'] and related['doi'] and detail['doi'] != related['doi'] and
                    detail['authors'] == related['authors'] and
                    any(related['title'] == prefix + detail['title']
                        for prefix in ('addendum to: ', 'erratum to: '))):
                originals.append(identifier)
        if len(originals) == 1:
            representative = originals[0]
            related = next(value for value in identifiers if value != representative)
            return {'representative': representative, 'kind': 'primary_paper_with_addendum_or_erratum',
                'doi': details[representative]['doi'], 'related_doi': details[related]['doi'],
                'evidence': 'The related arXiv title explicitly identifies an addendum/erratum '
                    'to the exact original title, with identical authors and distinct DOIs. '
                    'The original represents the grouped INSPIRE record for citation sampling; '
                    'the two arXiv papers are not asserted to be identical.'}
        raise ValueError('Ambiguous merged INSPIRE work; explicit expanded-version/DOI/authors evidence required')
    representative = expanded[0]
    return {'representative': representative, 'kind': 'expanded_version_same_doi_and_authors',
            'doi': details[representative]['doi'],
            'evidence': 'arXiv abstract explicitly identifies the alternate as an earlier version; '
                        'both arXiv records have the same DOI and authors'}


def private_json(path, data):
    write_json(path, data)
    Path(path).chmod(0o600)


def cached_response(directory, name, url, client):
    """Keep original response bytes, URL, timestamp and checksum for resume."""
    safe_url(url)
    path = directory / name
    if path.exists():
        if path.stat().st_size > 12_000_000:
            raise ValueError('Cached response exceeds size bound')
        saved = json.loads(path.read_text())
        body = base64.b64decode(saved['body_base64'], validate=True)
        encoding = saved.get('body_encoding', 'identity')
        if encoding == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                body = compressed.read(MAX_RESPONSE + 1)
        elif encoding != 'identity':
            raise ValueError('Unsupported metadata cache encoding')
        if saved['url'] != url or sha256(body).hexdigest() != saved['sha256']:
            raise ValueError('Cached metadata URL/hash mismatch: ' + str(path))
    else:
        body = client.get(url)
        if not isinstance(body, bytes) or len(body) > MAX_RESPONSE:
            raise ValueError('Invalid or oversized metadata response')
        private_json(path, {'url': url, 'retrieved_at': timestamp(),
            'sha256': sha256(body).hexdigest(),
            'body_encoding': 'gzip',
            'body_base64': base64.b64encode(gzip.compress(body, mtime=0)).decode('ascii')})
    if len(body) > MAX_RESPONSE:
        raise ValueError('Cached response exceeds size bound')
    return body


def parse_atom(content, expected):
    root = ET.fromstring(content)
    found = {}
    for entry in root.findall(ATOM + 'entry'):
        value = entry.findtext(ATOM + 'id', '')
        parsed = urlparse(value)
        if parsed.hostname not in {'arxiv.org', 'export.arxiv.org'} or not parsed.path.startswith('/abs/'):
            raise ValueError('Unexpected arXiv Atom identifier')
        pinned = arxiv_id(parsed.path[len('/abs/'):])
        base = base_id(pinned)
        title = ' '.join(entry.findtext(ATOM + 'title', '').split())
        authors = ', '.join(' '.join(author.findtext(ATOM + 'name', '').split())
                            for author in entry.findall(ATOM + 'author'))
        if base in found or base not in expected or not title or not authors:
            raise ValueError('Duplicate, unexpected or incomplete arXiv metadata: ' + base)
        found[base] = {'arxiv': pinned, 'title': title, 'authors': authors}
    if set(found) != set(expected):
        raise ValueError('arXiv version pinning incomplete; selection retained for resume; missing: ' +
                         ', '.join(sorted(set(expected) - set(found))))
    return found


def select_most_cited(directory, count=1000, *, inspire_client=None,
                      arxiv_client=None, page_size=250, batch_size=100,
                      max_pages=1000):
    """Freeze citation selection, then pin versions. Resume in the same directory.

    Returns selection.json content. papers-{count}.json is created only when all
    selected papers have exact versions, titles and authors from arXiv.
    Changing request parameters within a resumed directory is rejected.
    """
    for name, value, maximum in [('count', count, 100000), ('page_size', page_size, 1000),
                                  ('batch_size', batch_size, 200), ('max_pages', max_pages, 10000)]:
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError('Invalid ' + name)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    parameters = {'query': QUERY, 'sort': 'mostcited', 'count': count,
                  'page_size': page_size, 'batch_size': batch_size}
    with exclusive_lock(directory / 'selection.lock'):
        arxiv_client = arxiv_client or MetadataClient()

        def resolve(record_id, identifiers):
            url = 'https://export.arxiv.org/api/query?' + urlencode({
                'id_list': ','.join(identifiers), 'start': 0, 'max_results': len(identifiers)})
            name = 'arxiv-resolution-' + record_id + '.json'
            body = cached_response(directory, name, url, arxiv_client)
            resolution = resolve_expanded_version(body, identifiers)
            resolution['source_file'] = name
            return resolution
        config = directory / 'selection-request.json'
        if config.exists():
            if json.loads(config.read_text()) != parameters:
                raise ValueError('Resume parameters differ from frozen selection request')
        else:
            private_json(config, parameters)
        selection_path = directory / 'selection.json'
        if selection_path.exists():
            selection = json.loads(selection_path.read_text())
        else:
            records, seen_ids, seen_records = [], set(), set()
            previous, total_expected = None, None
            inspire_client = inspire_client or MetadataClient()
            for page in range(1, max_pages + 1):
                cutoff = records[count - 1]['citation_count'] if len(records) >= count else None
                url = SOURCE + '?' + urlencode({'q': QUERY, 'sort': 'mostcited',
                    'fields': FIELDS, 'size': page_size, 'page': page})
                total, items = parse_page(cached_response(directory,
                    'inspire-page-' + str(page).zfill(4) + '.json', url, inspire_client), resolve, cutoff)
                if total_expected is not None and total != total_expected:
                    raise ValueError('INSPIRE total changed during selection; start a new snapshot')
                total_expected = total
                if not items or len(items) > page_size:
                    raise ValueError('Empty or oversized INSPIRE page before selection completed')
                crossed_cutoff = False
                for item in items:
                    if item.get('_below_cutoff'):
                        crossed_cutoff = True
                        break
                    work_ids = {item['arxiv'], *item.get('alternate_arxiv_ids', [])}
                    if seen_ids.intersection(work_ids) or item['inspire_record_id'] in seen_records:
                        raise ValueError('Duplicate underlying arXiv paper or INSPIRE record')
                    if previous is not None and item['citation_count'] > previous:
                        raise ValueError('INSPIRE results are not in citation-descending order')
                    previous = item['citation_count']
                    seen_ids.update(work_ids)
                    seen_records.add(item['inspire_record_id'])
                    records.append(item)
                records.sort(key=lambda item: (-item['citation_count'], item['arxiv']))
                if len(records) > total:
                    raise ValueError('INSPIRE returned more records than its total')
                exhausted = len(records) == total
                if len(records) >= count and (exhausted or crossed_cutoff or
                        records[-1]['citation_count'] < records[count - 1]['citation_count']):
                    break
                if exhausted:
                    raise ValueError('Fewer distinct hep-ph arXiv papers than requested')
            else:
                raise ValueError('Page bound reached before resolving cutoff ties')
            selection = {'schema_version': 'bsm-citation-selection-1',
                'source': SOURCE, 'query': QUERY, 'sort': 'mostcited',
                'citation_metric': 'citation_count including self citations',
                'retrieved_at': timestamp(), 'count': count,
                'tie_break': 'arxiv base identifier ascending',
                'records_examined': len(records), 'candidates': records[:count]}
            private_json(selection_path, selection)
        candidates = selection['candidates']
        if len(candidates) != count or len({item['arxiv'] for item in candidates}) != count:
            raise ValueError('Frozen selection count/identity mismatch')
        arxiv_client = arxiv_client or MetadataClient()
        pinned = {}
        for start in range(0, count, batch_size):
            identifiers = [item['arxiv'] for item in candidates[start:start + batch_size]]
            url = 'https://export.arxiv.org/api/query?' + urlencode({
                'id_list': ','.join(identifiers), 'start': 0, 'max_results': len(identifiers)})
            body = cached_response(directory, 'arxiv-batch-' + str(start).zfill(5) + '.json',
                                   url, arxiv_client)
            pinned.update(parse_atom(body, identifiers))
        manifest = {'papers': [pinned[item['arxiv']] for item in candidates]}
        private_json(directory / ('papers-' + str(count) + '.json'), manifest)
        return selection
