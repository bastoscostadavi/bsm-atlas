"""Offline tests for the gitignored hep-ph TeX corpus mirror."""
from datetime import date
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from bsm_atlas import corpus

OAI_PAGE = '''<?xml version="1.0"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>
{records}
{token}
</ListRecords></OAI-PMH>'''
RECORD = '''<record><header><identifier>oai:arXiv.org:{id}</identifier></header><metadata>
<arXivRaw xmlns="http://arxiv.org/OAI/arXivRaw/"><id>{id}</id>{versions}
<title>Paper {id}</title><categories>{cats}</categories></arXivRaw></metadata></record>'''


def record(base, cats, versions=('v1',)):
    return RECORD.format(id=base, cats=cats, versions=''.join(
        '<version version="%s"><date>x</date></version>' % v for v in versions))


def tarball(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, body in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


class FakeClient:
    def __init__(self, responses):
        self.responses, self.urls = responses, []

    def get(self, url, limit=None):
        self.urls.append(url)
        response = self.responses(url) if callable(self.responses) else self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.dir = Path(self.temporary.name) / 'hep-ph'

    def tearDown(self):
        self.temporary.cleanup()

    def test_index_keeps_primary_hepph_latest_version_across_pages(self):
        first = OAI_PAGE.format(records=record('2101.00001', 'hep-ph hep-th', ('v1', 'v2')) +
                                record('2101.00002', 'hep-th hep-ph') +
                                '<record><header status="deleted"><identifier>x</identifier></header></record>',
                                token='<resumptionToken cursor="0" completeListSize="3">tok</resumptionToken>')
        second = OAI_PAGE.format(records=record('hep-ph/9901001', 'hep-ph', ('v1', 'v10', 'v2')),
                                 token='<resumptionToken/>')

        def respond(url):
            query = parse_qs(urlparse(url).query)
            return 200, (second if 'resumptionToken' in query else first).encode(), {}
        client = FakeClient(respond)
        window = [('2021-01-01', '2021-01-31')]
        self.assertEqual(corpus.build_index(self.dir, client, log=lambda m: None, windows=window), 2)
        index = corpus.read_index(self.dir)
        self.assertEqual([(r['arxiv'], r['version']) for r in index],
                         [('hep-ph/9901001', 'v10'), ('2101.00001', 'v2')])
        self.assertIn('set=physics%3Ahep-ph', client.urls[0])
        self.assertIn('from=2021-01-01', client.urls[0])
        self.assertIn('until=2021-01-31', client.urls[0])
        self.assertFalse((self.dir / 'index.state.json').exists())

    def test_default_index_traverses_the_complete_set_without_date_filters(self):
        page = OAI_PAGE.format(records=record('2101.00001', 'hep-ph'), token='')
        client = FakeClient(lambda url: (200, page.encode(), {}))
        self.assertEqual(corpus.build_index(self.dir, client, log=lambda m: None), 1)
        query = parse_qs(urlparse(client.urls[0]).query)
        self.assertEqual(query['set'], ['physics:hep-ph'])
        self.assertNotIn('from', query)
        self.assertNotIn('until', query)

    def test_month_windows_partition_calendar(self):
        windows = corpus.month_windows((1991, 8), date(1992, 3, 5))
        self.assertEqual(windows[0], ('1991-08-01', '1991-08-31'))
        self.assertEqual(windows[6], ('1992-02-01', '1992-02-29'))
        self.assertEqual(windows[-1], ('1992-03-01', '1992-03-31'))
        self.assertEqual(len(windows), 8)

    def test_index_resumes_after_interruption_and_skips_empty_months(self):
        empty = ('<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
                 '<error code="noRecordsMatch"/></OAI-PMH>')
        pages = {'2021-01-01': OAI_PAGE.format(records=record('2101.00001', 'hep-ph'), token=''),
                 '2021-02-01': empty,
                 '2021-03-01': OAI_PAGE.format(records=record('2103.00001', 'hep-ph'), token='')}
        interrupted = []

        def respond(url):
            start = parse_qs(urlparse(url).query)['from'][0]
            if start == '2021-03-01' and not interrupted:
                interrupted.append(url)
                raise KeyboardInterrupt
            return 200, pages[start].encode(), {}
        windows = [('2021-01-01', '2021-01-31'), ('2021-02-01', '2021-02-28'),
                   ('2021-03-01', '2021-03-31')]
        client = FakeClient(respond)
        with self.assertRaises(KeyboardInterrupt):
            corpus.build_index(self.dir, client, log=lambda m: None, windows=windows)
        self.assertEqual(json.loads((self.dir / 'index.state.json').read_text())['window'], 2)
        client.urls.clear()
        self.assertEqual(corpus.build_index(self.dir, client, log=lambda m: None, windows=windows), 2)
        self.assertEqual(len(client.urls), 1)  # only March was requested again

    def test_empty_listing_is_an_error_not_an_empty_index(self):
        empty = ('<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
                 '<error code="noRecordsMatch"/></OAI-PMH>').encode()
        client = FakeClient(lambda url: (200, empty, {}))
        with self.assertRaises(RuntimeError):
            corpus.build_index(self.dir, client, log=lambda m: None,
                               windows=[('2021-01-01', '2021-01-31')])
        self.assertFalse((self.dir / 'index.jsonl').exists())

    def test_fetch_keeps_text_drops_binaries_and_unsafe_paths(self):
        payload = tarball({'main.tex': b'\\documentclass{article}\\input{sec/a}',
                           'sec/a.tex': b'caf\xe9',  # latin-1 kept byte-exact
                           'macros.sty': b'\\def\\x{}', 'refs.bbl': b'\\bibitem{a}',
                           'refs.bib': b'@article{a}', 'JHEP.cls': b'%class', 'sub/axodraw.sty': b'%',
                           'fig.pdf': b'%PDF-1.4', 'fig.eps': b'%!PS', 'plot.png': b'\x89PNG..',
                           'data.bin': b'a\x00b', '../evil.tex': b'x', '/abs.tex': b'x'})
        (self.dir).mkdir(parents=True)
        (self.dir / 'index.jsonl').write_text(json.dumps({'arxiv': '2101.00001', 'version': 'v2'}) + '\n' +
                                              json.dumps({'arxiv': 'hep-ph/9901001', 'version': 'v1'}) + '\n')
        client = FakeClient({corpus.EPRINT_URL + '2101.00001v2': (200, payload, {}),
                             corpus.EPRINT_URL + 'hep-ph/9901001v1': (200, gzip.compress(b'\\bye text'), {})})
        counts = corpus.fetch(self.dir, client, log=lambda m: None)
        self.assertEqual(counts, {'ok': 2})
        target = self.dir / 'papers' / '2101' / '2101.00001v2'
        kept = sorted(str(p.relative_to(target / 'source')) for p in (target / 'source').rglob('*') if p.is_file())
        self.assertEqual(kept, ['macros.sty', 'main.tex', 'sec/a.tex'])
        self.assertEqual((target / 'source' / 'sec' / 'a.tex').read_bytes(), b'caf\xe9')
        self.assertEqual(json.loads((target / 'meta.json').read_text())['dropped_count'], 10)
        self.assertFalse((Path(self.temporary.name) / 'evil.tex').exists())
        single = self.dir / 'papers' / '9901' / 'hep-ph_9901001v1' / 'source' / 'main.tex'
        self.assertEqual(single.read_bytes(), b'\\bye text')
        # Resume makes no further requests.
        before = len(client.urls)
        self.assertEqual(corpus.fetch(self.dir, client, log=lambda m: None), {})
        self.assertEqual(len(client.urls), before)

    def test_malformed_archive_filename_does_not_stop_valid_sources_or_resume(self):
        malformed = 'figures/invalid_\udcff.tex'
        payload = tarball({malformed: b'unsafe filename',
                           'main.tex': b'\\documentclass{article}',
                           'caf\u00e9.tex': b'valid unicode'})
        records = [{'arxiv': '2101.00001', 'version': 'v1'},
                   {'arxiv': '2101.00002', 'version': 'v1'}]
        client = FakeClient({corpus.EPRINT_URL + '2101.00001v1': (200, payload, {}),
                             corpus.EPRINT_URL + '2101.00002v1': (200, b'next source', {})})
        self.assertEqual(corpus.fetch(self.dir, client, records=records, log=lambda _: None), {'ok': 2})
        target = corpus.paper_dir(self.dir, '2101.00001', 'v1')
        meta = json.loads((target / 'meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['dropped'], [malformed])
        self.assertEqual(meta['dropped_count'], 1)
        self.assertEqual(sorted(f['path'] for f in meta['files']), ['caf\u00e9.tex', 'main.tex'])
        self.assertEqual((target / 'source' / 'caf\u00e9.tex').read_bytes(), b'valid unicode')
        self.assertEqual(corpus.fetch(self.dir, client, records=records, log=lambda _: None), {})
        self.assertEqual(len(client.urls), 2)

    def test_safe_member_rejects_surrogates_before_utf8_length_checks(self):
        for codepoint in (0xD800, 0xDC80, 0xDCFF, 0xDFFF):
            self.assertIsNone(corpus._safe_member('dir/' + chr(codepoint) + '.tex'))
        self.assertEqual(corpus._safe_member('dir/caf\u00e9.tex'),
                         ['dir', 'caf\u00e9.tex'])

    def test_pdf_only_missing_and_blocked(self):
        self.dir.mkdir(parents=True)
        (self.dir / 'index.jsonl').write_text(''.join(json.dumps({'arxiv': a, 'version': 'v1'}) + '\n'
                                                      for a in ('2101.00001', '2101.00002', '2101.00003')))
        client = FakeClient({corpus.EPRINT_URL + '2101.00001v1': (200, b'%PDF-1.5 ...', {}),
                             corpus.EPRINT_URL + '2101.00002v1': (404, b'', {}),
                             corpus.EPRINT_URL + '2101.00003v1': corpus.Blocked('429')})
        with self.assertRaises(corpus.Blocked):
            corpus.fetch(self.dir, client, log=lambda m: None)
        summary = corpus.status(self.dir)
        self.assertEqual(summary['statuses'], {'not_fetched': 1, 'pdf_only': 1, 'missing': 1})

    def test_rejects_malformed_identifiers(self):
        with self.assertRaises(ValueError):
            corpus.paper_dir(self.dir, '../2101.00001', 'v1')

    def test_bootstrap_status_cannot_claim_a_complete_index(self):
        self.dir.mkdir(parents=True)
        (self.dir / 'bootstrap-index.jsonl').write_text(
            json.dumps({'arxiv': '2101.00001', 'version': 'v1'}) + '\n')
        summary = corpus.status(self.dir)
        self.assertFalse(summary['complete_index'])
        self.assertEqual(summary['indexed'], 1)
        self.assertEqual(summary['statuses'], {'not_fetched': 1})


if __name__ == '__main__':
    unittest.main()
