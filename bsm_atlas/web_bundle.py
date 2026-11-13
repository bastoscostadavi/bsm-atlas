"""Content-addressed, bounded static records and prefix search indexes.

The public bootstrap contains catalogue memberships, not field tables, paper
metadata or evidence. The full exports remain useful local research artifacts.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
import re
import unicodedata

PAGE_SIZE = 20
SHARD_BYTES = 64 * 1024
EVIDENCE_BYTES = 32 * 1024
VERSION = 'atlas-static-1'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', str(text)).lower()
                   if unicodedata.category(c) != 'Mn')


def tokens(text):
    return set(re.findall(r'[^\W_]+', normalize(text), re.UNICODE))


def route_hash(value):
    result = 2166136261
    for byte in value.encode():
        result = ((result ^ byte) * 16777619) & 0xffffffff
    return f'{result:08x}'


def paper_order(paper):
    identifier = paper['arxiv'].split('v')[0]
    legacy = '/' in identifier
    suffix = identifier.split('/')[-1]
    year = int(suffix[:2]); month = int(suffix[2:4])
    year += 1900 if legacy and year >= 91 else 2100 if not legacy and year < 7 else 2000
    return year, month, identifier.split('/')[0] if legacy else '', int(suffix[5:] if not legacy else suffix[4:]), identifier


class Bundle:
    def __init__(self):
        self.files = {}
        self.oversized = []

    def blob(self, value):
        raw = encoded(value)
        name = 'data/blobs/' + sha256(raw).hexdigest() + '.json'
        self.files[name] = raw
        return name

    def shards(self, records):
        routes = {}

        def split(items, prefix=''):
            raw = encoded(items)
            if len(raw) <= SHARD_BYTES or len(items) <= 1 or len(prefix) == 32:
                routes[prefix] = self.blob(items)
                if len(raw) > SHARD_BYTES:
                    self.oversized.append({'bytes': len(raw), 'records': len(items)})
                return
            groups = defaultdict(dict)
            for key, value in items.items():
                groups[f'{int(route_hash(key), 16):032b}'[:len(prefix) + 1]][key] = value
            for key, group in sorted(groups.items()):
                split(group, key)

        split(records)
        return routes


def pages(rows):
    result, current, size = [], [], 2
    for row in rows:
        length = len(encoded(row)) + 1
        if current and (len(current) >= PAGE_SIZE or size + length > EVIDENCE_BYTES):
            result.append(current); current, size = [], 2
        current.append(row); size += length
    if current:
        result.append(current)
    return result


def make_bundle(data, annotations, *, source_sha256, downloads=None, worker_source=None):
    bundle = Bundle()
    papers = sorted(data['papers'], key=paper_order)
    paper_positions = {paper['id']: index for index, paper in enumerate(papers)}
    entries = data['entries']
    model_positions = {entry['id']: index for index, entry in enumerate(entries)}
    entry_summaries, bodies = [], {}
    for entry in entries:
        summary = {key: deepcopy(entry[key]) for key in (
            'id', 'name', 'algebraExpanded', 'algebraSignature', 'coreId',
            'semisimpleId', 'fullAlgebraId', 'abelianRank')}
        if entry.get('aliases'):
            summary['aliases'] = entry['aliases']
        summary['paperIds'] = sorted(entry['paperIds'], key=paper_positions.__getitem__)
        summary['referenceCount'] = len(entry['references'])
        entry_summaries.append(summary)
        bodies[entry['id']] = {key: entry[key] for key in ('specification', 'regime')}
        mapping = next((ref['parameter_names'] for ref in entry['references'] if ref.get('parameter_names')), None)
        if mapping:
            bodies[entry['id']]['referenceParameters'] = mapping

    groups = {}
    for key in ['cores', 'semisimpleAlgebras', 'fullAlgebras']:
        groups[key] = [{k: v for k, v in group.items() if k not in {
            'paperIds', 'canonical', 'regime'}} for group in data[key]]
    summary = {'schema_version': 'bsm-atlas-client-1', 'version': data['version'],
               'representationConvention': data['representationConvention'],
               'counts': data['counts'], 'templates': data['templates'],
               'entries': entry_summaries, 'papers': [], 'downloads': downloads or {}, **groups}
    routes = {'entries': bundle.shards(bodies),
              'cores': bundle.shards({group['id']: {'regime': group['regime']} for group in data['cores']}),
              'papers': bundle.shards({paper['id']: paper for paper in papers})}
    annotation_urls = {}
    for kind in ['problems', 'mechanisms']:
        original = annotations[kind]
        compact = {key: deepcopy(original[key]) for key in ('categories', kind, 'assessed')}
        compact.update(links={}, linkCounts={}, reviewCounts={}, pageCounts={}, paperCounts={})
        term_papers = defaultdict(set)
        evidence_records = {}
        for entry_id, terms in original['links'].items():
            compact['links'][entry_id] = {}
            for field in ['linkCounts', 'reviewCounts', 'pageCounts']:
                compact[field][entry_id] = {}
            for term, rows in terms.items():
                # Membership alone is enough for catalogue intersections. It is
                # never interpreted as evidence by the asynchronous renderer.
                compact['links'][entry_id][term] = [{}]
                compact['linkCounts'][entry_id][term] = len(rows)
                compact['reviewCounts'][entry_id][term] = sum(bool(row['needsReview']) for row in rows)
                term_papers[term].update(row['paperId'] for row in rows)
                ordered = sorted(rows, key=lambda row: (bool(row['needsReview']), paper_positions[row['paperId']]))
                chunks = pages(ordered)
                compact['pageCounts'][entry_id][term] = len(chunks)
                offset = 0
                for number, chunk in enumerate(chunks, 1):
                    key = '\n'.join([entry_id, term, str(number)])
                    evidence_records[key] = {'rows': chunk, 'page': number,
                                             'pages': len(chunks), 'total': len(rows), 'offset': offset}
                    offset += len(chunk)
        compact['paperCounts'] = {key: len(value) for key, value in term_papers.items()}
        annotation_urls[kind] = bundle.blob(compact)
        routes['evidence_' + kind] = bundle.shards(evidence_records)

    # Each query word is a prefix. Postings union matching word prefixes, then
    # intersect across query words. Model postings include linked bibliography
    # words without copying the bibliography into every model's search string.
    postings = defaultdict(lambda: {'p': set(), 'm': set()})
    for index, paper in enumerate(papers):
        for word in tokens(' '.join([paper['title'], paper['authors'], paper['arxiv']])):
            postings[word]['p'].add(index)
            postings[word]['m'].update(model_positions[entry] for entry in paper['entryIds'])
    for index, entry in enumerate(entries):
        text = ' '.join([entry['id'], entry['name'], entry['algebraExpanded'],
                         json.dumps(entry['specification'], ensure_ascii=False),
                         *[v for alias in entry.get('aliases', []) for v in alias.values()]])
        for word in tokens(text):
            postings[word]['m'].add(index)
    buckets = defaultdict(dict)
    for word, lists in sorted(postings.items()):
        buckets[word[:3]][word] = {key: sorted(value) for key, value in lists.items()}
    search, search_records = {}, {}
    for prefix, words in buckets.items():
        chunks, current, size = [], {}, 2
        for word, lists in words.items():
            length = len(encoded({word: lists}))
            if current and size + length > SHARD_BYTES:
                chunks.append(current); current, size = {}, 2
            current[word] = lists; size += length
        if current:
            chunks.append(current)
        search[prefix] = len(chunks)
        for number, chunk in enumerate(chunks):
            search_records[prefix + '\n' + str(number)] = chunk
    routes['search'] = bundle.shards(search_records)
    year_ranges = {}
    for index, paper in enumerate(papers):
        year = str(paper_order(paper)[0])
        if year not in year_ranges:
            year_ranges[year] = [index, index + 1]
        else:
            year_ranges[year][1] = index + 1
    order = bundle.blob({'ids': [paper['id'] for paper in papers], 'years': year_ranges})
    manifest = {'schema_version': VERSION, 'sourceSha256': source_sha256,
                'catalogue': bundle.blob(summary), 'annotations': annotation_urls,
                'records': {key: bundle.blob(value) for key, value in routes.items()}, 'search': bundle.blob(search), 'paperOrder': order,
                'counts': data['counts'], 'years': sorted(year_ranges, reverse=True),
                'pageSize': PAGE_SIZE, 'oversizedRecords': bundle.oversized}
    if worker_source:
        worker = 'data/worker-' + sha256(worker_source).hexdigest() + '.js'
        bundle.files[worker] = worker_source
        manifest['searchWorker'] = worker
    path = 'data/manifest-' + sha256(encoded(manifest)).hexdigest() + '.json'
    bundle.files[path] = encoded(manifest)
    bundle.files['atlas-bootstrap.js'] = ('window.ATLAS_MANIFEST_URL = ' + json.dumps(path) + ';\n').encode()
    return bundle.files
