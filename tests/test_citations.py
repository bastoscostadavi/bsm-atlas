"""Offline citation selection, cutoff ties, strict parsing and resumability."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch
from urllib.error import HTTPError

from bsm_atlas import citations


def hit(identifier, count, record):
    return {'id': str(record), 'metadata': {'citation_count': count,
        'arxiv_eprints': [{'value': identifier, 'categories': ['hep-ph', 'hep-th']}],
        'titles': [{'title': 'Test paper ' + identifier}]}}


def page(items, total):
    return json.dumps({'hits': {'total': total, 'hits': items}}).encode()


def atom(ids):
    return ('<feed xmlns="http://www.w3.org/2005/Atom">' + ''.join(
        '<entry><id>http://arxiv.org/abs/' + value + 'v2</id><title>Paper</title>'
        '<author><name>A. Author</name></author></entry>' for value in ids) + '</feed>').encode()


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'selection'

    def test_cutoff_ties_and_resumption(self):
        inspire = Mock()
        inspire.get.side_effect = [page([hit('2001.00003', 10, 1), hit('2001.00004', 8, 2)], 4),
                                   page([hit('2001.00001', 8, 3), hit('2001.00002', 7, 4)], 4)]
        arxiv = Mock()
        arxiv.get.return_value = atom(['2001.00003', '2001.00001'])
        result = citations.select_most_cited(self.directory, 2, page_size=2,
                                            inspire_client=inspire, arxiv_client=arxiv, primary_only=False)
        self.assertEqual([item['arxiv'] for item in result['candidates']],
                         ['2001.00003', '2001.00001'])
        manifest = json.loads((self.directory / 'papers-2.json').read_text())
        self.assertEqual(manifest['papers'][1]['arxiv'], '2001.00001v2')
        self.assertEqual(set(manifest['papers'][0]), {'arxiv', 'title', 'authors'})
        no_network = Mock()
        no_network.get.side_effect = AssertionError('Unexpected network')
        self.assertEqual(result, citations.select_most_cited(self.directory, 2, page_size=2,
            inspire_client=no_network, arxiv_client=no_network, primary_only=False))
        no_network.get.assert_not_called()
        self.assertIn('body_base64', json.loads((self.directory / 'inspire-page-0001.json').read_text()))

    def test_failed_pinning_preserves_selection(self):
        inspire, arxiv = Mock(), Mock()
        inspire.get.return_value = page([hit('hep-ph/9901234', 0, 1)], 1)
        arxiv.get.side_effect = OSError('service unavailable')
        with self.assertRaises(OSError):
            citations.select_most_cited(self.directory, 1, inspire_client=inspire, arxiv_client=arxiv, primary_only=False)
        self.assertTrue((self.directory / 'selection.json').exists())
        self.assertFalse((self.directory / 'papers-1.json').exists())
        arxiv.get.side_effect = None
        arxiv.get.return_value = atom(['hep-ph/9901234'])
        citations.select_most_cited(self.directory, 1, inspire_client=inspire, arxiv_client=arxiv, primary_only=False)
        self.assertEqual(inspire.get.call_count, 1)

    def test_bad_counts_and_ambiguous_metadata(self):
        good = hit('2001.00001v3', 0, 1)
        self.assertEqual(citations.parse_hit(good)['arxiv'], '2001.00001')
        for value in [None, True, -1, 2.5, '10']:
            bad = deepcopy(good)
            bad['metadata']['citation_count'] = value
            with self.assertRaisesRegex(ValueError, 'citation_count'):
                citations.parse_hit(bad)
        for key in ['citation_count', 'arxiv_eprints', 'titles']:
            bad = deepcopy(good)
            del bad['metadata'][key]
            with self.assertRaises(ValueError):
                citations.parse_hit(bad)
        bad = deepcopy(good)
        bad['metadata']['arxiv_eprints'] *= 2
        with self.assertRaises(ValueError):
            citations.parse_hit(bad)

    def test_expanded_version_resolution_requires_evidence(self):
        identifiers = ['hep-ph/9405296', 'hep-ph/9408296']
        raw = atom(identifiers).decode().replace(
            '<feed xmlns=', '<feed xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns=')
        raw = raw.replace('</entry>', '<arxiv:doi>10.123/identical</arxiv:doi></entry>')
        raw = raw.replace('hep-ph/9408296v2</id>', 'hep-ph/9408296v2</id>'
            '<summary>This paper is an expanded version of hep-ph/9405296, for publication.</summary>')
        resolution = citations.resolve_expanded_version(raw.encode(), identifiers)
        self.assertEqual(resolution['representative'], 'hep-ph/9408296')
        item = hit(identifiers[0], 641, 375639)
        item['metadata']['arxiv_eprints'].append({'value': identifiers[1], 'categories': ['hep-ph']})
        selected = citations.parse_hit(item, lambda record, ids: resolution)
        self.assertEqual(selected['arxiv'], identifiers[1])
        self.assertEqual(selected['alternate_arxiv_ids'], [identifiers[0]])
        self.assertEqual(selected['citation_count'], 641)
        with self.assertRaisesRegex(ValueError, 'explicit expanded-version'):
            citations.resolve_expanded_version(raw.replace('expanded version of', 'related to').encode(), identifiers)
        with self.assertRaises(ValueError):
            citations.resolve_expanded_version(raw.replace('10.123/identical', '', 1).encode(), identifiers)

    def test_duplicate_records_fail(self):
        client = Mock()
        client.get.return_value = page([hit('2001.00001', 3, 1), hit('2001.00001v2', 2, 2)], 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            citations.select_most_cited(self.directory, 1, inspire_client=client, primary_only=False)

    def test_duplicate_deposits_require_doi_journal_and_compatible_authors(self):
        ids = ['hep-ph/9801361', 'hep-ph/9711308']
        def entry(identifier, date, authors, journal):
            return ('<entry><id>http://arxiv.org/abs/' + identifier + 'v1</id>'
                '<title>Improved determination</title><published>' + date + '</published>' +
                ''.join('<author><name>' + name + '</name></author>' for name in authors) +
                '<arxiv:doi>10.1016/S0370-2693(97)01512-8</arxiv:doi>'
                '<arxiv:journal_ref>' + journal + '</arxiv:journal_ref></entry>')
        body = ('<feed xmlns="http://www.w3.org/2005/Atom" '
                'xmlns:arxiv="http://arxiv.org/schemas/atom">' +
                entry(ids[0], '1998-01-20T14:46:51Z', ['Michel Davier', 'Andreas Hoecker'],
                      'Phys.Lett.B419:419-431,1998') +
                entry(ids[1], '1997-11-12T19:04:56Z', ['M. Davier', 'A. Hoecker'],
                      'Phys.Lett. B419 (1998) 419-431') + '</feed>')
        result = citations.resolve_expanded_version(body.encode(), ids)
        self.assertEqual(result['representative'], ids[0])
        self.assertEqual(result['kind'], 'duplicate_deposits_same_doi_journal_and_authors')
        self.assertEqual(result, citations.resolve_expanded_version(body.encode(), list(reversed(ids))))
        for changed in [body.replace('M. Davier', 'N. Davier'),
                        body.replace('M. Davier', 'Michael Davier'),
                        body.replace('419-431</arxiv', '419-432</arxiv'),
                        body.replace('>Improved determination</title>', '>Erratum</title>', 1),
                        body.replace('10.1016/S0370-2693(97)01512-8', '', 1)]:
            with self.assertRaises(ValueError):
                citations.resolve_expanded_version(changed.encode(), ids)

    def test_explicit_addendum_selects_original_without_claiming_paper_identity(self):
        identifiers = ['1703.04471', '2003.08511']
        raw = atom(identifiers).decode().replace('<feed xmlns=',
            '<feed xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns=')
        raw = raw.replace('<title>Paper</title>', '<title>Original title</title>', 1)
        raw = raw.replace('<title>Paper</title>', '<title>Addendum to: Original title</title>', 1)
        raw = raw.replace('</entry>', '<arxiv:doi>10.123/original</arxiv:doi></entry>', 1)
        raw = raw.replace('</entry></feed>', '<arxiv:doi>10.123/addendum</arxiv:doi></entry></feed>')
        result = citations.resolve_expanded_version(raw.encode(), identifiers)
        self.assertEqual(result['representative'], identifiers[0])
        self.assertEqual(result['kind'], 'primary_paper_with_addendum_or_erratum')
        self.assertIn('not asserted to be identical', result['evidence'])
        for changed in [raw.replace('Addendum to: Original title', 'Related title'),
                        raw.replace('10.123/addendum', '10.123/original'),
                        raw.replace('<name>A. Author</name>', '<name>B. Author</name>', 1)]:
            with self.assertRaises(ValueError):
                citations.resolve_expanded_version(changed.encode(), identifiers)

    def test_unsorted_fail(self):
        client = Mock()
        client.get.return_value = page([hit('2001.00001', 2, 1), hit('2001.00002', 3, 2)], 2)
        with self.assertRaisesRegex(ValueError, 'citation-descending'):
            citations.select_most_cited(self.directory, 1, inspire_client=client, primary_only=False)

    def test_erratum_with_journal_suffix_requires_explicit_original_identifier(self):
        ids = ['hep-ph/0205210', '1301.1079']
        raw = atom(ids).decode().replace('<feed xmlns=',
            '<feed xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns=')
        raw = raw.replace('<title>Paper</title>',
            '<title>Order-v^4 corrections to S-wave quarkonium decay</title>', 1)
        raw = raw.replace('<title>Paper</title>',
            '<title>Erratum: Order-v^4 corrections to S-wave quarkonium decay '
            '[Phys. Rev. D 66, 094011 (2002)]</title>'
            '<summary>We correct errors in arXiv:hep-ph/0205210.</summary>', 1)
        raw = raw.replace('</entry>', '<arxiv:doi>10.1103/PhysRevD.66.094011</arxiv:doi></entry>', 1)
        raw = raw.replace('</entry></feed>',
            '<arxiv:doi>10.1103/PhysRevD.87.039902</arxiv:doi></entry></feed>')
        result = citations.resolve_expanded_version(raw.encode(), ids)
        self.assertEqual(result['representative'], ids[0])
        self.assertEqual(result['kind'], 'primary_paper_with_addendum_or_erratum')
        for changed in [raw.replace('arXiv:hep-ph/0205210', 'another paper'),
                        raw.replace('arXiv:hep-ph/0205210', 'arXiv:hep-ph/02052100'),
                        raw.replace('Erratum: Order-v^4', 'Erratum: Other-v^4')]:
            with self.assertRaises(ValueError):
                citations.resolve_expanded_version(changed.encode(), ids)

    def test_citation_helper_defaults_to_primary_and_new_only(self):
        from bsm_atlas import relevance
        marker = object()
        source = self.directory / 'catalogue.json'
        with patch.object(relevance, 'select_population', return_value=marker) as select:
            self.assertIs(citations.select_most_cited(self.directory, 2, source=source), marker)
            select.assert_called_once_with(self.directory, 2, ranking='citations', primary_only=True,
                source=source, client=None, arxiv_client=None, page_size=250, batch_size=100)

    def test_incomplete_atom_fails(self):
        for content in [atom([]), atom(['2001.00001', '2001.00001']), atom(['2001.00002'])]:
            with self.assertRaises(ValueError):
                citations.parse_atom(content, ['2001.00001'])

    def test_primary_category_must_be_explicit_not_category_order(self):
        body = atom(['2001.00001']).decode().replace('<feed xmlns=',
            '<feed xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns=')
        body = body.replace('</entry>', '<category term="hep-ph"/>'
            '<arxiv:primary_category term="hep-th"/></entry>')
        parsed = citations.parse_atom(body.encode(), ['2001.00001'], include_primary=True)
        self.assertEqual(parsed['2001.00001']['primary_category'], 'hep-th')
        for invalid in [body.replace('<arxiv:primary_category term="hep-th"/>', ''),
                        body.replace('term="hep-th"', 'term=""'),
                        body.replace('</entry>', '<arxiv:primary_category term="hep-ph"/></entry>')]:
            with self.assertRaisesRegex(ValueError, 'primary category'):
                citations.parse_atom(invalid.encode(), ['2001.00001'], include_primary=True)

    def test_lower_ranked_alias_does_not_require_resolution(self):
        lower = hit('2001.00002', 3, 2)
        lower['metadata']['arxiv_eprints'].append({'value': '2001.00003', 'categories': ['hep-ph']})
        resolve = Mock(side_effect=AssertionError('Unrelated alias was resolved'))
        total, records = citations.parse_page(page([hit('2001.00001', 5, 1), lower], 2),
                                              resolve, minimum_count=5)
        self.assertEqual(total, 2)
        self.assertTrue(records[-1]['_below_cutoff'])
        resolve.assert_not_called()

    def test_service_block_stops_without_retry(self):
        for status in [403, 429]:
            client = citations.MetadataClient()
            client.opener = Mock()
            client.opener.open.side_effect = HTTPError(citations.SOURCE, status, 'blocked',
                                                       {'Retry-After': '60'}, None)
            with patch.object(citations.time, 'sleep'):
                with self.assertRaisesRegex(ValueError, 'stop and resume later'):
                    client.get(citations.SOURCE)
            self.assertEqual(client.opener.open.call_count, 1)

    def test_url_allowlist(self):
        for url in ['http://inspirehep.net/api/literature', 'https://evil.test/api/literature',
                    'https://inspirehep.net:444/api/literature',
                    'https://user@inspirehep.net/api/literature', 'https://inspirehep.net/other']:
            with self.assertRaises(ValueError):
                citations.safe_url(url)

    def test_request_intervals_are_service_specific_and_validated(self):
        self.assertEqual(citations.MetadataClient().minimum_interval, 3.1)
        self.assertEqual(citations.MetadataClient(0.5).minimum_interval, 0.5)
        for invalid in [-1, float('inf'), float('nan'), 'fast']:
            with self.assertRaises(ValueError):
                citations.MetadataClient(invalid)

    def test_cache_tampering_fails(self):
        self.directory.mkdir()
        client = Mock()
        client.get.return_value = b'original'
        url = citations.SOURCE
        citations.cached_response(self.directory, 'cache.json', url, client)
        path = self.directory / 'cache.json'
        saved = json.loads(path.read_text())
        saved['sha256'] = 'bad'
        from bsm_atlas.catalogue import write_json
        write_json(path, saved)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            citations.cached_response(self.directory, 'cache.json', url, client)


if __name__ == '__main__':
    unittest.main()
