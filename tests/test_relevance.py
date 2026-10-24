"""Offline tests for full-population means and new-only cohort selection."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from bsm_atlas import relevance
from bsm_atlas.catalogue import write_json
from bsm_atlas.citations import QUERY


def hit(identifier, count, recid, date=None):
    return {'id': str(recid), 'metadata': {'citation_count': count,
        'earliest_date': date or '20' + identifier[:2] + '-01-01',
        'arxiv_eprints': [{'value': identifier, 'categories': ['hep-ph']}],
        'titles': [{'title': 'Test paper'}]}}


def metadata_client(records):
    def get(url):
        args = parse_qs(urlparse(url).query)
        query, page, size = args['q'][0], int(args.get('page', ['1'])[0]), int(args['size'][0])
        selected = records
        if ' and not earliest_date:*' in query:
            selected = [r for r in records if not r['metadata'].get('earliest_date')]
        elif ' and earliest_date:' in query:
            date = query.split(' and earliest_date:')[1]
            if date.startswith('<'):
                selected = [r for r in records if r['metadata']['earliest_date'][:4] < date[1:]]
            elif date.startswith('>'):
                selected = [r for r in records if r['metadata']['earliest_date'][:4] > date[1:]]
            else:
                selected = [r for r in records if r['metadata']['earliest_date'].startswith(date)]
        return json.dumps({'hits': {'total': len(selected),
            'hits': selected[(page-1)*size:page*size]}}).encode()
    client = Mock()
    client.get.side_effect = get
    return client


def arxiv_client():
    def get(url):
        identifiers = parse_qs(urlparse(url).query)['id_list'][0].split(',')
        return ('<feed xmlns="http://www.w3.org/2005/Atom">' + ''.join(
            '<entry><id>http://arxiv.org/abs/' + i + 'v2</id><title>Paper</title>'
            '<author><name>Author</name></author></entry>' for i in identifiers) + '</feed>').encode()
    result = Mock()
    result.get.side_effect = get
    return result


class RelevanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'catalogue.json'
        self.directory = self.root / 'selection'
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [{
            'id': 'known', 'arxiv': '2401.00001v1', 'title': 'Known', 'authors': 'A',
            'extraction_status': 'unresolved'}], 'entries': []})
        self.records = [hit('2401.00001', 40, 1), hit('2401.00002', 10, 2),
                        hit('2401.00003', 0, 3), hit('2501.00001', 2, 4),
                        hit('2501.00002', 0, 5)]

    def select(self, **kwargs):
        return relevance.select_year_normalized(self.directory, 2, source=self.source,
            client=kwargs.pop('client', metadata_client(self.records)),
            arxiv_client=kwargs.pop('arxiv_client', arxiv_client()),
            first_year=2024, last_year=2025, page_size=2, batch_size=2, **kwargs)

    def test_full_cohort_means_include_zero_and_recorded_works(self):
        selected = self.select()
        self.assertEqual(selected['population_records'], 5)
        self.assertEqual(selected['cohorts']['2024'], {'papers': 3, 'citations': 50})
        self.assertEqual([r['arxiv'] for r in selected['candidates']], ['2501.00001', '2401.00002'])
        self.assertEqual(selected['candidates'][1]['score'], {'numerator': 3, 'denominator': 5})
        self.assertEqual(selected['excluded_recorded_works_before_cutoff'], 1)
        papers = json.loads((self.directory / 'papers-2.json').read_text())['papers']
        self.assertEqual([p['arxiv'] for p in papers], ['2501.00001v2', '2401.00002v2'])

    def test_resume_makes_no_requests_and_source_change_is_rejected(self):
        original = self.select()
        no_network = Mock()
        no_network.get.side_effect = AssertionError('Unnecessary network request')
        self.assertEqual(self.select(client=no_network, arxiv_client=no_network), original)
        write_json(self.source, {'schema_version': 'bsm-atlas-1', 'papers': [], 'entries': []})
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            self.select(client=no_network, arxiv_client=no_network)

    def test_pinning_failure_retains_frozen_ranking(self):
        broken = Mock()
        broken.get.side_effect = OSError('Network unavailable')
        with self.assertRaises(OSError):
            self.select(arxiv_client=broken)
        self.assertTrue((self.directory / 'selection.json').exists())
        self.assertFalse((self.directory / 'papers-2.json').exists())
        no_inspire = Mock()
        no_inspire.get.side_effect = AssertionError('Repeated population fetch')
        self.select(client=no_inspire)

    def test_cohort_comes_from_arxiv_not_earliest_publication_date(self):
        record = relevance.population_record(hit('2501.00001', 2, 1, '1985'))
        self.assertEqual(record['cohort_year'], 2025)
        self.assertEqual(relevance.posting_year('hep-ph/9912345v2'), 1999)
        self.assertEqual(relevance.posting_year('hep-th/0001001'), 2000)
        with self.assertRaisesRegex(ValueError, 'month'):
            relevance.posting_year('2513.00001')

    def test_zero_mean_and_exact_rational_scores(self):
        records = [relevance.population_record(hit('2501.00001', 0, 1))]
        self.assertEqual(relevance.relevance(records[0], relevance.cohort_statistics(records)), Fraction(0))
        record = deepcopy(records[0])
        record['citation_count'] = 1
        self.assertEqual(relevance.relevance(record, {'2025': {'papers': 3, 'citations': 7}}), Fraction(3, 7))

    def test_repeated_identical_eprint_is_one_work_not_an_alias(self):
        raw = hit('2501.00001', 113, 1272707)
        raw['metadata']['arxiv_eprints'].append({'value': '2501.00001'})
        record = relevance.population_record(raw)
        self.assertEqual(record['arxiv_ids'], ['2501.00001'])
        self.assertEqual(len(record['metadata']['arxiv_eprints']), 1)
        self.assertEqual(relevance.cohort_statistics([record])['2025'], {'papers': 1, 'citations': 113})

    def test_decorated_duplicate_requires_same_record_corroboration(self):
        raw = hit('2003.11751', 16, 1788446)
        raw['metadata']['arxiv_eprints'].append({'value': '2003.11751 [hep-ph]'})
        self.assertEqual(relevance.population_record(raw)['arxiv_ids'], ['2003.11751'])
        raw['metadata']['arxiv_eprints'][1]['value'] = '2003.11751 (hep-ph)'
        self.assertEqual(relevance.population_record(raw)['arxiv_ids'], ['2003.11751'])
        for invalid in ['2003.11752 [hep-ph]', '2003.11751 [hep-th]', '2003.11751 arbitrary text']:
            raw['metadata']['arxiv_eprints'][1]['value'] = invalid
            with self.assertRaises(ValueError):
                relevance.population_record(raw)

    def test_submission_token_does_not_define_a_posting_cohort(self):
        raw = hit('2011.04941', 2, 1829284)
        raw['metadata']['arxiv_eprints'].insert(0, {'value': 'submit/3418798', 'categories': ['hep-ph']})
        self.assertEqual(relevance.population_record(raw)['arxiv_ids'], ['2011.04941'])
        raw['metadata']['arxiv_eprints'].pop()
        with self.assertRaisesRegex(ValueError, 'No published'):
            relevance.population_record(raw)

    def test_punctuation_or_version_decoration_requires_a_bare_counterpart(self):
        raw = hit('2103.13104', 10, 1853253)
        raw['metadata']['arxiv_eprints'].append({})
        for value in ['2103.13104.', '2103.13104(v.6)']:
            raw['metadata']['arxiv_eprints'][1]['value'] = value
            self.assertEqual(relevance.population_record(raw)['arxiv_ids'], ['2103.13104'])
        raw['metadata']['arxiv_eprints'][1]['value'] = '2103.13105.'
        with self.assertRaises(ValueError):
            relevance.population_record(raw)

    def test_missing_counts_and_duplicate_works_stop_before_selection(self):
        bad = deepcopy(self.records[0])
        bad['metadata'].pop('citation_count')
        with self.assertRaisesRegex(ValueError, 'citation count'):
            relevance.population_record(bad)
        self.records.append(hit('2501.00001', 2, 6))
        with self.assertRaisesRegex(ValueError, 'Duplicate INSPIRE work'):
            self.select()
        self.assertFalse((self.directory / 'selection.json').exists())

    def test_metadata_errors_are_collected_without_incomplete_cohort_ranking(self):
        bad = hit('2501.00006', 1, 6)
        bad['metadata']['arxiv_eprints'][0]['value'] = '2501.00006 invalid'
        self.records.append(bad)
        no_arxiv = Mock()
        with self.assertRaisesRegex(ValueError, 'Metadata needs correction'):
            self.select(arxiv_client=no_arxiv)
        no_arxiv.get.assert_not_called()
        self.assertEqual(len(json.loads((self.directory / 'metadata-issues.json').read_text())), 1)
        self.assertFalse((self.directory / 'selection.json').exists())


if __name__ == '__main__':
    unittest.main()
