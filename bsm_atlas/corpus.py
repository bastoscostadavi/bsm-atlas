"""Local, gitignored mirror of primary-hep-ph TeX sources from arXiv.

Two resumable steps, both through the shared paced arXiv gate:

  index  OAI-PMH (arXivRaw) listing of the physics:hep-ph set, filtered to
         papers whose *primary* (first) category is hep-ph, with the latest
         version of each.
  fetch  One /e-print/ request per indexed paper version. Only text members
         of the source archive are kept (TeX, the paper's own styles/classes and
         any other plain-text file a document may \\input); figures, binaries,
         bibliography files and standard journal classes/packages are dropped. Archives are read in memory; nothing is
         extracted by tarfile, executed or compiled.

Layout under ``corpus/hep-ph`` (gitignored):

  index.jsonl                     one line per paper: arxiv, version, title, categories
  papers/<yymm>/<id>v<n>/source/  kept text files, archive paths preserved
  papers/<yymm>/<id>v<n>/meta.json
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .request_gate import arxiv_slot

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / 'corpus' / 'hep-ph'
OAI_URL = 'https://oaipmh.arxiv.org/oai'
EPRINT_URL = 'https://export.arxiv.org/e-print/'
ARXIV_HOSTS = {'arxiv.org', 'www.arxiv.org', 'export.arxiv.org', 'oaipmh.arxiv.org'}
USER_AGENT = 'bsm-atlas-corpus/1 (+https://github.com/bastoscostadavi/bsm-atlas)'
OAI = '{http://www.openarchives.org/OAI/2.0/}'
RAW = '{http://arxiv.org/OAI/arXivRaw/}'

MAX_DOWNLOAD = 300_000_000      # whole e-print response
MAX_MEMBER = 20_000_000         # one kept text file
MAX_KEPT = 100_000_000          # all kept text of one paper
MAX_MEMBERS = 20_000
CORPUS_VERSION = 1

BASE_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})\Z')
VERSION = re.compile(r'v[1-9]\d*\Z')
DROP = {'.pdf', '.eps', '.epsi', '.epsf', '.ps', '.png', '.jpg', '.jpeg', '.gif',
        '.bmp', '.tif', '.tiff', '.webp', '.svg', '.fig', '.xfig', '.dvi', '.ttf',
        '.otf', '.pfb', '.woff', '.zip', '.gz', '.tgz', '.bz2', '.xz', '.tar',
        '.mp4', '.mp3', '.avi', '.mov', '.root', '.log', '.o', '.so', '.exe',
        # Bibliography: references are not needed for gauge/matter content.
        '.bbl', '.bib', '.bst', '.blg'}
# Widely redistributed journal classes and generic packages: identical across
# thousands of papers and carry no paper-specific notation. Matched by
# case-insensitive basename; author-written .sty/.cls files are kept.
STANDARD = {name.lower() for name in '''
    revtex4.cls revtex4-1.cls revtex4-2.cls aps.rtx aps10pt.rtx aps11pt.rtx aps12pt.rtx
    aps4-1.rtx aps10pt4-1.rtx aps11pt4-1.rtx aps12pt4-1.rtx revsymb.sty revsymb4-1.sty
    aip4-1.rtx aps4-2.rtx aps10pt4-2.rtx aps11pt4-2.rtx aps12pt4-2.rtx revsymb4-2.sty
    jhep.cls jhep3.cls jheppub.sty jcappub.sty jcap.cls elsarticle.cls elsart.cls
    elsart1p.cls elsart3p.cls elsart5p.cls svjour.cls svjour3.cls svepj.clo svglov3.clo
    epj.cls iopart.cls iopart10.clo iopart12.clo ptptex.cls ptp-text.sty appolb.cls
    ws-ijmpa.cls ws-mpla.cls ws-procs9x6.cls ws-procs961x669.cls aipproc.cls pos.cls
    jpconf.cls jpconf11.clo moriond.sty moriond.cls lineno.sty
    axodraw.sty axodraw2.sty feynmf.sty feynmp.sty epsfig.sty epsf.sty epsf.tex
    psfig.sty psfig.tex graphicx.sty graphics.sty color.sty xcolor.sty hyperref.sty
    amsmath.sty amssymb.sty amsfonts.sty amsthm.sty bm.sty slashed.sty cite.sty
    natbib.sty dcolumn.sty multirow.sty subfigure.sty subfig.sty float.sty
    geometry.sty url.sty caption.sty times.sty fancyhdr.sty wrapfig.sty cancel.sty
    '''.split()}


class Blocked(RuntimeError):
    """arXiv refused access or rate-limited us; stop instead of hammering it."""

    def __init__(self, message, code=None, headers=None):
        super().__init__(message)
        self.code = code
        self.headers = headers or {}


# ----------------------------------------------------------------- transport

class Client:
    """Serial HTTPS client sharing the machine-wide 3 s arXiv pacing lock."""

    def __init__(self, opener=urlopen, interval=3.1, lock=None, timeout=120):
        self.opener, self.interval, self.lock, self.timeout = opener, interval, lock, timeout

    def get(self, url, limit=MAX_DOWNLOAD):
        request = Request(url, headers={'User-Agent': USER_AGENT})
        try:
            with arxiv_slot(self.lock, interval=self.interval), \
                    self.opener(request, timeout=self.timeout) as response:
                returned = urlparse(response.geturl())
                if returned.scheme != 'https' or returned.hostname not in ARXIV_HOSTS:
                    raise ValueError('Unexpected redirect away from arXiv: ' + response.geturl())
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise OverflowError('response exceeds ' + str(limit) + ' bytes')
                return response.status if hasattr(response, 'status') else 200, body, response.headers
        except HTTPError as error:
            if error.code in {401, 403, 429}:
                raise Blocked('arXiv returned HTTP %d for %s' % (error.code, url),
                              error.code, error.headers) from error
            if error.code == 503:
                # OAI-PMH flow control: honour Retry-After, then the caller retries.
                return 503, b'', error.headers
            if error.code in {404, 410}:
                return error.code, b'', error.headers
            raise


@contextmanager
def single_writer(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / '.lock', 'a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another corpus process is already running in ' + str(directory))
        yield


def _write_atomic(path, data):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    os.replace(temporary, path)


# --------------------------------------------------------------------- index

def _record(element):
    header = element.find(OAI + 'header')
    if header is None or header.get('status') == 'deleted':
        return None
    raw = element.find(OAI + 'metadata/' + RAW + 'arXivRaw')
    if raw is None:
        return None
    base = (raw.findtext(RAW + 'id') or '').strip()
    categories = (raw.findtext(RAW + 'categories') or '').split()
    versions = [v.get('version', '') for v in raw.findall(RAW + 'version')]
    versions = [v for v in versions if VERSION.fullmatch(v)]
    if not BASE_ID.fullmatch(base) or not categories or not versions:
        return None
    return {'arxiv': base,
            'version': max(versions, key=lambda v: int(v[1:])),
            'primary': categories[0],
            'categories': categories,
            'title': ' '.join((raw.findtext(RAW + 'title') or '').split())}


def month_windows(first=(1991, 8), today=None):
    """Inclusive (from, until) datestamp windows, one per calendar month."""
    today = today or datetime.now(timezone.utc).date()
    year, month = first
    windows = []
    while (year, month) <= (today.year, today.month):
        following = (year + month // 12, month % 12 + 1)
        last = (datetime(*following, 1) - datetime(year, month, 1)).days
        windows.append(('%04d-%02d-01' % (year, month), '%04d-%02d-%02d' % (year, month, last)))
        year, month = following
    return windows


def build_index(directory=CORPUS, client=None, oai_url=OAI_URL, log=print, windows=None):
    """Harvest the complete primary-hep-ph OAI set; resumable.

    OAI-PMH datestamps record metadata changes, *not* original submissions.
    In particular, arXiv assigns pre-2005 works one shared earliest datestamp.
    The default therefore follows arXiv's recommended initial-harvest request:
    list the set without a datestamp range and follow its resumption tokens.

    ``windows`` remains an explicit test/diagnostic hook for bounded listing.
    It must not be used for a complete historical index.
    """
    client = client or Client(timeout=300)
    directory = Path(directory)
    full_set = windows is None
    windows = [None] if full_set else windows
    with single_writer(directory):
        partial, state = directory / 'index.partial.jsonl', directory / 'index.state.json'
        saved = json.loads(state.read_text()) if state.exists() else None
        if saved is None and partial.exists():
            partial.unlink()
        partial.touch()
        position, token = (saved['window'], saved.get('token')) if saved else (0, None)
        failures, pages, total = 0, 0, 0
        while position < len(windows):
            window = windows[position]
            start, until = window if window is not None else (None, None)
            label = 'complete primary-hep-ph set' if window is None else start[:7]
            query = ({'verb': 'ListRecords', 'resumptionToken': token} if token else
                     {'verb': 'ListRecords', 'metadataPrefix': 'arXivRaw', 'set': 'physics:hep-ph'})
            if not token and window is not None:
                query.update({'from': start, 'until': until})
            url = oai_url + '?' + urlencode(query)
            try:
                status, body, headers = client.get(url, limit=200_000_000)
                failures = 0
            except (URLError, TimeoutError, ConnectionError) as error:
                failures += 1
                if failures >= 5:
                    raise RuntimeError('OAI-PMH did not respond after 5 attempts (%s); rerun to resume' % error)
                wait = 60 * failures
                log('no response for %s (%s); retry %d/4 in %d s' % (label, error, failures, wait))
                time.sleep(wait)
                continue
            if status == 503:
                wait = int((headers or {}).get('Retry-After', 30) or 30)
                log('OAI flow control: waiting %d s' % wait)
                time.sleep(min(max(wait, 1), 600))
                continue
            if status != 200:
                raise RuntimeError('OAI-PMH returned HTTP %d for %s' % (status, url))
            root = ET.fromstring(body)
            error = root.find(OAI + 'error')
            if error is not None:
                if error.get('code') == 'badResumptionToken':
                    log('resumptionToken expired; restarting ' + label)
                    token = None
                    continue
                if error.get('code') != 'noRecordsMatch':
                    raise RuntimeError('OAI-PMH error %s: %s' % (error.get('code'), error.text))
            listing = root.find(OAI + 'ListRecords')
            records = [] if listing is None else [r for r in map(_record, listing.findall(OAI + 'record')) if r]
            with open(partial, 'a', encoding='utf-8') as handle:
                for record in records:
                    handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            pages += 1
            total += len(records)
            element = None if listing is None else listing.find(OAI + 'resumptionToken')
            token = ((element.text or '').strip() if element is not None else '') or None
            log('%s: %d records%s (%d so far, segment %d/%d)' % (
                label, len(records), ' (more pages)' if token else '', total, position + 1, len(windows)))
            if not token:
                position += 1
            _write_atomic(state, json.dumps({'window': position, 'token': token}).encode())
        # Deduplicate (a record can reappear across pages) and keep primary hep-ph only.
        latest = {}
        with open(partial, encoding='utf-8') as handle:
            for line in handle:
                record = json.loads(line)
                if record['primary'] != 'hep-ph':
                    continue
                known = latest.get(record['arxiv'])
                if not known or int(record['version'][1:]) >= int(known['version'][1:]):
                    latest[record['arxiv']] = record
        lines = [json.dumps({k: r[k] for k in ('arxiv', 'version', 'title', 'categories')},
                            ensure_ascii=False) for r in sorted(latest.values(), key=lambda r: _sort_key(r['arxiv']))]
        if not lines:
            partial.unlink()
            state.unlink(missing_ok=True)
            raise RuntimeError('OAI-PMH listing returned no primary hep-ph papers; check --oai-url and the set name')
        _write_atomic(directory / 'index.jsonl', ('\n'.join(lines) + '\n').encode('utf-8'))
        partial.unlink()
        state.unlink(missing_ok=True)
        log('index.jsonl: %d primary hep-ph papers' % len(lines))
        return len(lines)


def _sort_key(base):
    if '/' in base:
        archive, number = base.split('/')
        yymm = number[:4]
    else:
        yymm, number = base.split('.')
    year = int(yymm[:2])
    return (1900 + year if year >= 91 else 2000 + year, int(yymm[2:]), base)


def read_index(directory=CORPUS):
    path = Path(directory) / 'index.jsonl'
    if not path.exists():
        raise FileNotFoundError('No index yet; run `python3 -m bsm_atlas corpus index` first')
    with open(path, encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


# --------------------------------------------------------------------- fetch

def paper_dir(directory, base, version):
    if not BASE_ID.fullmatch(base) or not VERSION.fullmatch(version):
        raise ValueError('Invalid arXiv identifier: ' + base + version)
    yymm = base.split('/')[1][:4] if '/' in base else base.split('.')[0]
    return Path(directory) / 'papers' / yymm / (base.replace('/', '_') + version)


def _safe_member(name):
    """Map an archive member name to safe relative path parts, or None."""
    # Tar headers can decode invalid filename bytes as lone surrogates.
    # Reject those names before UTF-8 length checks or filesystem writes.
    if not name or '\x00' in name or any(0xD800 <= ord(c) <= 0xDFFF for c in name):
        return None
    path = PurePosixPath(name.replace('\\', '/'))
    parts = [p for p in path.parts if p not in {'', '.'}]
    if path.is_absolute() or not parts or any(p == '..' or p.startswith('~') for p in parts):
        return None
    if any(len(p.encode()) > 200 or any(ord(c) < 32 for c in p) for p in parts):
        return None
    return parts


def _is_text(body):
    if b'\x00' in body[:65536]:
        return False
    return not body.startswith((b'%PDF', b'\x89PNG', b'\xff\xd8', b'GIF8', b'PK\x03\x04', b'\x1f\x8b'))


def extract_text_members(content):
    """Return (kind, {relative path: bytes}, dropped) from one e-print payload."""
    if content.startswith(b'%PDF'):
        return 'pdf_only', {}, []
    try:
        archive = tarfile.open(fileobj=io.BytesIO(content), mode='r:*')
    except tarfile.ReadError:
        body = content
        if content.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as handle:
                body = handle.read(MAX_MEMBER + 1)
            if len(body) > MAX_MEMBER:
                raise OverflowError('single-file source exceeds bound')
        if body.startswith(b'%PDF'):
            return 'pdf_only', {}, []
        if not _is_text(body):
            return 'no_text', {}, ['<single file>']
        return 'single', {'main.tex': body}, []
    kept, dropped, total = {}, [], 0
    with archive:
        for count, member in enumerate(archive, 1):
            if count > MAX_MEMBERS:
                raise OverflowError('archive has too many members')
            if not member.isfile():
                continue
            parts = _safe_member(member.name)
            suffix = PurePosixPath(member.name).suffix.lower()
            if (parts is None or suffix in DROP or parts[-1].lower() in STANDARD
                    or member.size > MAX_MEMBER):
                dropped.append(member.name)
                continue
            with archive.extractfile(member) as handle:
                body = handle.read(MAX_MEMBER + 1)
            if len(body) > MAX_MEMBER or not _is_text(body):
                dropped.append(member.name)
                continue
            key = '/'.join(parts)
            if key.lower() in {k.lower() for k in kept}:
                dropped.append(member.name)   # case-insensitive clash on macOS
                continue
            total += len(body)
            if total > MAX_KEPT:
                raise OverflowError('kept text exceeds bound')
            kept[key] = body
    return ('archive' if kept else 'no_text'), kept, dropped


def _save(target, base, version, kind, files, dropped, url, size):
    staging = target.with_name(target.name + '.partial')
    shutil.rmtree(staging, ignore_errors=True)
    source = staging / 'source'
    source.mkdir(parents=True)
    root = source.resolve()
    listing = []
    for key, body in sorted(files.items()):
        path = source.joinpath(*key.split('/'))
        if root not in path.resolve().parents:
            dropped.append(key)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        listing.append({'path': key, 'bytes': len(body), 'sha256': sha256(body).hexdigest()})
    meta = {'arxiv': base, 'version': version, 'status': 'ok' if listing else kind,
            'kind': kind, 'url': url, 'download_bytes': size, 'files': listing,
            'dropped': sorted(dropped)[:500], 'dropped_count': len(dropped),
            'corpus_version': CORPUS_VERSION,
            'retrieved': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (staging / 'meta.json').write_text(json.dumps(meta, indent=1, ensure_ascii=True) + '\n')
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    return meta['status']


def _failure(target, base, version, status, detail):
    target.mkdir(parents=True, exist_ok=True)
    (target / 'meta.json').write_text(json.dumps({
        'arxiv': base, 'version': version, 'status': status, 'detail': detail,
        'corpus_version': CORPUS_VERSION,
        'retrieved': datetime.now(timezone.utc).isoformat(timespec='seconds')}, indent=1) + '\n')
    return status


def fetch_one(directory, record, client):
    base, version = record['arxiv'], record['version']
    target = paper_dir(directory, base, version)
    url = getattr(client, 'eprint_url', EPRINT_URL) + base + version
    try:
        status, body, _ = client.get(url)
    except OverflowError as error:
        return _failure(target, base, version, 'too_large', str(error))
    if status in {404, 410}:
        return _failure(target, base, version, 'missing', 'HTTP %d' % status)
    if status != 200:
        raise RuntimeError('e-print returned HTTP %d for %s' % (status, url))
    try:
        kind, files, dropped = extract_text_members(body)
    except (OverflowError, tarfile.TarError, EOFError, OSError, gzip.BadGzipFile) as error:
        return _failure(target, base, version, 'unreadable', type(error).__name__ + ': ' + str(error))
    return _save(target, base, version, kind, files, dropped, url, len(body))


def done(directory, record, retry_failed=False):
    meta = paper_dir(directory, record['arxiv'], record['version']) / 'meta.json'
    if not meta.exists():
        return False
    if not retry_failed:
        return True
    return json.loads(meta.read_text()).get('status') in {'ok', 'pdf_only', 'no_text'}


def fetch(directory=CORPUS, client=None, limit=None, retry_failed=False, log=print, records=None,
          priority_records=None):
    client = client or Client()
    directory = Path(directory)
    with single_writer(directory):
        pending = [r for r in (read_index(directory) if records is None else records)
                   if not done(directory, r, retry_failed)]
        if limit is not None:
            pending = pending[:limit]
        interval = getattr(client, 'interval', 3.1)
        log('%d papers to fetch (minimum %.1f h at %.1f s/request, excluding cooldowns)' % (
            len(pending), len(pending) * interval / 3600, interval))
        counts, failures, started = {}, 0, time.monotonic()
        number, position, priority_stamp, priority_pending = 0, 0, None, []
        while position < len(pending) or priority_records is not None:
            if priority_records is not None:
                preferred = priority_records()
                stamp = tuple((r['arxiv'], r['version']) for r in preferred)
                if stamp != priority_stamp:
                    priority_pending = [r for r in reversed(preferred) if not done(directory, r, retry_failed)]
                    priority_stamp = stamp
            if priority_pending:
                record = priority_pending.pop()
            elif position < len(pending):
                record = pending[position]
                position += 1
            else:
                break
            # Priority work may already have fulfilled this chronological item.
            if done(directory, record, retry_failed):
                continue
            number += 1
            try:
                status = fetch_one(directory, record, client)
                failures = 0
            except Blocked:
                log('Stopped: arXiv refused or rate-limited the request. Wait before resuming.')
                raise
            except (URLError, TimeoutError, ConnectionError) as error:
                failures += 1
                status = 'network_error'
                log('network error on %s%s: %s' % (record['arxiv'], record['version'], error))
                if failures >= 5:
                    raise RuntimeError('Five consecutive network failures; stopping. Rerun to resume.')
                time.sleep(30 * failures)
                continue
            counts[status] = counts.get(status, 0) + 1
            if number <= 5 or number % 100 == 0 or number == len(pending):
                rate = (time.monotonic() - started) / number
                log('%d/%d  %s  ETA %.1f h' % (number, len(pending), json.dumps(counts),
                                               (len(pending) - number) * rate / 3600))
        return counts


def status(directory=CORPUS):
    directory = Path(directory)
    complete_index = (directory / 'index.jsonl').exists()
    if complete_index:
        records = read_index(directory)
    elif (directory / 'bootstrap-index.jsonl').exists():
        records = [json.loads(line) for line in (directory / 'bootstrap-index.jsonl').read_text().splitlines()
                   if line.strip()]
    else:
        records = read_index(directory)
    counts, files, size = {'not_fetched': 0}, 0, 0
    for record in records:
        meta = paper_dir(directory, record['arxiv'], record['version']) / 'meta.json'
        if not meta.exists():
            counts['not_fetched'] += 1
            continue
        data = json.loads(meta.read_text())
        counts[data['status']] = counts.get(data['status'], 0) + 1
        files += len(data.get('files', []))
        size += sum(f['bytes'] for f in data.get('files', []))
    summary = {'indexed': len(records), 'complete_index': complete_index,
               'statuses': counts, 'files': files, 'text_bytes': size}
    if (directory / 'transfer-state.json').exists():
        summary['transfer'] = json.loads((directory / 'transfer-state.json').read_text())
    return summary


def main(args):
    directory = Path(args.dir)
    log = lambda message: print(message, flush=True)
    if (args.action != 'index' and not (directory / 'index.jsonl').exists()
            and not (args.action == 'status' and (directory / 'bootstrap-index.jsonl').exists())):
        print('No index yet; run `python3 -m bsm_atlas corpus index` first', file=sys.stderr)
        return 2
    if args.action == 'index':
        build_index(directory, oai_url=args.oai_url, log=log)
    elif args.action == 'fetch':
        try:
            fetch(directory, limit=args.limit, retry_failed=args.retry_failed, log=log)
        except Blocked as error:
            print(str(error), file=sys.stderr)
            return 2
    elif args.action == 'status':
        print(json.dumps(status(directory), indent=1))
    return 0
