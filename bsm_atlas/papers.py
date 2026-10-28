"""Version-pinned arXiv metadata and bounded full text; no PDF/TeX execution."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
import tarfile
import time
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ARXIV = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})v[1-9]\d*\Z')
MAX_TEXT = 1_500_000
MAX_DOWNLOAD = 20_000_000
MAX_RAW_TEXT = 50_000_000
ATOM = '{http://www.w3.org/2005/Atom}'


class RetrievalBlocked(RuntimeError):
    """An access/rate-limit response stops the fetcher, not a paper exclusion."""


class SourceUnavailable(ValueError):
    def __init__(self, message, network_failure=False):
        super().__init__(message)
        self.network_failure = network_failure


def arxiv_id(value):
    if not isinstance(value, str) or not ARXIV.fullmatch(value):
        raise ValueError('Use a pinned arXiv identifier, e.g. 1905.13729v1')
    return value


def job_id(value):
    return arxiv_id(value).replace('/', '-')


def full_text(value):
    if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_TEXT:
        raise ValueError('Full text exceeds the supported context bound; do not truncate it')
    if len(value.strip()) < 100:
        raise ValueError('Missing or insufficient full text; an abstract is not a paper')
    return value


class ArxivClient:
    """One connection at a time, at least 3 seconds between requests, no retries."""
    def __init__(self):
        self.last_request = time.monotonic()

    def get(self, url):
        time.sleep(max(0, 3.1 - (time.monotonic() - self.last_request)))
        try:
            request = Request(url, headers={'User-Agent':
                              'bsm-atlas/1 (+https://github.com/bastoscostadavi/bsm-atlas)'})
            from .request_gate import arxiv_slot
            with arxiv_slot(), urlopen(request, timeout=30) as response:
                requested, returned = urlparse(url), urlparse(response.geturl())
                if returned.scheme != 'https' or returned.hostname not in {'arxiv.org', 'www.arxiv.org', 'export.arxiv.org'}:
                    raise ValueError('Unexpected redirect away from arXiv')
                for kind in ('e-print', 'html'):
                    if requested.path.startswith('/' + kind + '/'):
                        identifier = requested.path[len(kind) + 2:]
                        if returned.path.rstrip('/') not in {
                                '/' + form + '/' + identifier for form in ('e-print', 'src', 'html')}:
                            raise ValueError('Full-text redirect changed the requested paper/version')
                body = response.read(MAX_DOWNLOAD + 1)
                if len(body) > MAX_DOWNLOAD:
                    raise ValueError('arXiv response exceeds the download bound')
                return body
        except HTTPError as error:
            if error.code in {401, 403, 429}:
                raise RetrievalBlocked('arXiv returned HTTP ' + str(error.code) +
                                       '; retrieval stopped. Resolve access or wait before explicitly resuming.') from error
            raise
        finally:
            self.last_request = time.monotonic()


def metadata(content, identifier):
    root = ET.fromstring(content)
    entries = root.findall(ATOM + 'entry')
    if len(entries) != 1:
        raise ValueError('arXiv did not return exactly one requested paper')
    entry = entries[0]
    returned = entry.findtext(ATOM + 'id', '').split('/abs/')[-1]
    if returned != arxiv_id(identifier):
        raise ValueError('arXiv returned a different paper/version: ' + returned)
    title = ' '.join(entry.findtext(ATOM + 'title', '').split())
    authors = ', '.join(' '.join(author.findtext(ATOM + 'name', '').split())
                        for author in entry.findall(ATOM + 'author'))
    if not title or not authors:
        raise ValueError('Missing arXiv title or authors')
    return {'id': 'arxiv-' + job_id(identifier).replace('.', '-'),
            'arxiv': identifier, 'title': title, 'authors': authors}


def tex_text(content):
    """Clean one bounded source dependency graph, without compiling TeX."""
    from .tex_source import clean_tex
    return full_text(clean_tex(content))


class PaperHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.article, self.hidden = [], False, 0
        self.references = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.references:
            if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
                self.references.append(tag)
            return
        if (attrs.get('role') == 'doc-bibliography' or
                {'ltx_bibliography', 'ltx_biblist'}.intersection(attrs.get('class', '').split())):
            self.references = [tag]
            return
        if tag == 'article':
            self.article = True
        if tag in {'script', 'style', 'math'}:
            if tag == 'math' and self.article and not self.hidden:
                self.parts.append(' ' + attrs.get('alttext', '') + ' ')
            self.hidden += 1
        if self.article and not self.hidden:
            if tag in {'p', 'div', 'section', 'tr', 'h1', 'h2', 'h3', 'br'}:
                self.parts.append('\n')
            elif tag in {'td', 'th'}:
                self.parts.append('\t')

    def handle_endtag(self, tag):
        if self.references:
            if tag in self.references:
                index = len(self.references) - 1 - self.references[::-1].index(tag)
                del self.references[index:]
            return
        if tag in {'script', 'style', 'math'}:
            self.hidden = max(0, self.hidden - 1)
        if tag == 'article':
            self.article = False

    def handle_data(self, data):
        if self.article and not self.hidden and not self.references:
            self.parts.append(data)


def save_source_cache(directory, raw, cleaned, origin, report):
    if directory is None:
        return
    from .catalogue import write_json
    directory = Path(directory)
    (directory / 'source.raw.txt').write_text(raw, encoding='utf-8')
    write_json(directory / 'source.json', {
        'origin': origin, 'raw_sha256': sha256(raw.encode()).hexdigest(),
        'cleaned_sha256': sha256(cleaned.encode()).hexdigest(),
        'raw_characters': len(raw), 'cleaned_characters': len(cleaned), 'preparation': report})


def fetch_paper(item, base, client, cache_directory=None):
    identifier = arxiv_id(item['arxiv'])
    if all(item.get(key) for key in ('title', 'authors')):
        paper = {key: item[key] for key in ('arxiv', 'title', 'authors')}
        paper['id'] = 'arxiv-' + job_id(identifier).replace('.', '-')
    else:
        paper = metadata(client.get('https://export.arxiv.org/api/query?' +
                                    urlencode({'id_list': identifier})), identifier)
    if 'id' in item:
        paper['id'] = item['id']
    if 'text' in item:
        path = (base / item['text']).resolve()
        if not path.is_file():
            raise ValueError('Local paper text must be a regular file')
        if path.stat().st_size > MAX_RAW_TEXT:
            raise ValueError('Local source exceeds the raw-text safety bound')
        body = path.read_text(encoding='utf-8')
        if 'SOURCE FILE:' in body or any(marker in body for marker in ('\\documentclass', '\\documentstyle', '\\begin{document}', '\\bye')):
            from .tex_source import prepare_cached_tex
            cleaned, raw, report = prepare_cached_tex(body)
        else:
            cleaned, raw, report = body, body, {'format': 'local_transcript', 'cleaner_version': None}
        save_source_cache(cache_directory, raw, cleaned, str(path), report)
        return paper, full_text(cleaned), str(path)
    errors, network_failure = [], False
    for kind in ('e-print', 'html'):
        url = 'https://arxiv.org/' + kind + '/' + identifier
        try:
            body = client.get(url)
            if kind == 'e-print':
                from .tex_source import prepare_tex
                cleaned, raw, report = prepare_tex(body)
                save_source_cache(cache_directory, raw, cleaned, url, report)
                text = full_text(cleaned)
            else:
                parser = PaperHTML()
                parser.feed(body.decode('utf-8'))
                raw = body.decode('utf-8')
                text = full_text(''.join(parser.parts))
                save_source_cache(cache_directory, raw, text, url, {'format': 'arxiv_html', 'cleaner_version': None})
            return paper, text, url
        except (OSError, ValueError, tarfile.TarError, EOFError) as error:
            errors.append(str(error))
            network_failure = network_failure or (isinstance(error, URLError) and not isinstance(error, HTTPError))
            network_failure = network_failure or isinstance(error, (TimeoutError, ConnectionError))
            network_failure = network_failure or (isinstance(error, HTTPError) and error.code >= 500)
    raise SourceUnavailable('Full text unavailable; supply a local version-matched text file. ' + '; '.join(errors), network_failure)
