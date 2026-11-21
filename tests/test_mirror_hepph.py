"""Offline retry-policy tests: no requests or real cooldowns."""
from datetime import datetime, timezone
from email.utils import format_datetime
import json
import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from bsm_atlas import corpus, papers
from scripts.mirror_hepph import ContinuousClient, retry_after


class MirrorRetryTests(unittest.TestCase):
    def test_temporary_address_failure_retries_same_url_with_backoff(self):
        client=ContinuousClient(self.directory);url=client.eprint_url+'2401.00001v1'
        with patch.object(client,'wait_until') as wait,patch.object(papers.ArxivClient,'get',side_effect=[
                OSError(errno.EADDRNOTAVAIL,'Cannot assign requested address'),b'source']) as get:
            self.assertEqual(client.get(url)[1],b'source')
        self.assertEqual(get.call_count,2);self.assertEqual(get.call_args_list[0],get.call_args_list[1])
        self.assertTrue(wait.called);self.assertEqual(client.interval,3.1)

    def test_oversized_archive_is_recorded_and_next_paper_is_downloaded(self):
        client=ContinuousClient(self.directory)
        records=[{'arxiv':'2401.00001','version':'v1'},{'arxiv':'2401.00002','version':'v1'}]
        with patch.object(papers.ArxivClient,'get',side_effect=[ValueError('arXiv response exceeds the download bound'),b'\\documentclass{article}']):
            counts=corpus.fetch(self.directory,client=client,records=records,log=lambda _:None)
        self.assertEqual(counts,{'too_large':1,'ok':1})

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_rate_limit_retries_same_url_after_retry_after_at_fixed_pacing(self):
        client = ContinuousClient(self.directory)
        waits = []
        with patch('scripts.mirror_hepph.time.time', return_value=1000), patch.object(
                client, 'wait_until', side_effect=lambda deadline, *args: waits.append(deadline)), patch.object(
                corpus.Client, 'get', side_effect=[
                    corpus.Blocked('HTTP 429', 429, {'Retry-After': '7200'}),
                    (200, b'source', {})]) as get:
            self.assertEqual(client.get('https://export.arxiv.org/e-print/2101.00001v1')[1], b'source')
        self.assertEqual(waits[0], 8200)
        self.assertEqual(get.call_args_list[0], get.call_args_list[1])
        self.assertEqual(client.interval, 3.1)
        self.assertEqual(client.rate_limits, 1)

    def test_cooldown_survives_restart(self):
        with patch('scripts.mirror_hepph.time.time', return_value=1000):
            original = ContinuousClient(self.directory, initial_cooldown=1800)
            restarted = ContinuousClient(self.directory)
        self.assertEqual(restarted.retry_at, original.retry_at)
        self.assertEqual(json.loads(restarted.state_path.read_text())['retry_at'], 2800)

    def test_access_denied_is_terminal(self):
        client = ContinuousClient(self.directory)
        with patch.object(corpus.Client, 'get', side_effect=corpus.Blocked('403', 403)) as get:
            with self.assertRaises(corpus.Blocked):
                client.get('https://export.arxiv.org/e-print/2101.00001v1')
        self.assertEqual(get.call_count, 1)
        self.assertEqual(json.loads(client.state_path.read_text())['state'], 'blocked')

    def test_transient_failures_retry_without_losing_the_paper(self):
        client = ContinuousClient(self.directory)
        with patch.object(client, 'wait_until'), patch.object(corpus.Client, 'get', side_effect=[
                URLError('network down'), (503, b'', {'Retry-After': '900'}),
                (200, b'full source', {})]) as get:
            self.assertEqual(client.get('https://export.arxiv.org/e-print/2101.00001v1')[1], b'full source')
        self.assertEqual(get.call_count, 3)

    def test_retry_after_http_date(self):
        date = format_datetime(datetime.fromtimestamp(4600, timezone.utc), usegmt=True)
        with patch('scripts.mirror_hepph.time.time', return_value=1000):
            self.assertEqual(retry_after({'Retry-After': date}), 3600)
        self.assertEqual(retry_after({'Retry-After': 'bad header'}), 0)

    def test_sources_use_actual_atlas_harvester_and_keep_source_bytes(self):
        client = ContinuousClient(self.directory)
        url = client.eprint_url + '2101.00001v1'
        with patch.object(papers.ArxivClient, 'get', return_value=b'original source') as get, patch.object(
                corpus.Client, 'get', side_effect=AssertionError('must use atlas source transport')):
            self.assertEqual(client.get(url), (200, b'original source', {}))
        get.assert_called_once_with('https://arxiv.org/e-print/2101.00001v1')

    def test_old_local_six_hour_policy_is_retired(self):
        (self.directory / 'transfer-state.json').write_text(json.dumps({
            'interval': 120, 'rate_limits': 8, 'retry_at': 9999999999}))
        client = ContinuousClient(self.directory)
        self.assertEqual(client.interval, 3.1)
        self.assertEqual(client.retry_at, 0)
        self.assertEqual(client.rate_limits, 8)

    def test_atlas_rate_limit_keeps_retry_after_and_does_not_escalate_lifetime_count(self):
        client = ContinuousClient(self.directory)
        client.rate_limits = 100
        cause = HTTPError('https://arxiv.org/e-print/2101.00001v1', 429, 'wait', {'Retry-After': '300'}, None)
        blocked = papers.RetrievalBlocked('429')
        blocked.__cause__ = cause
        with patch('scripts.mirror_hepph.time.time', return_value=1000), patch.object(
                client, 'wait_until') as wait, patch.object(papers.ArxivClient, 'get', side_effect=[
                    blocked, b'source']) as get:
            self.assertEqual(client.get(cause.url)[1], b'source')
        self.assertEqual(wait.call_args_list[0].args[0], 1300)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(client.interval, 3.1)

    def test_corpus_saves_actual_harvester_origin_and_skips_completed_downloads(self):
        client = ContinuousClient(self.directory)
        record = {'arxiv': '2101.00001', 'version': 'v1'}
        with patch.object(papers.ArxivClient, 'get', return_value=b'\\documentclass{article}') as get:
            self.assertEqual(corpus.fetch(self.directory, client=client, records=[record], log=lambda _: None), {'ok': 1})
            self.assertEqual(corpus.fetch(self.directory, client=client, records=[record], log=lambda _: None), {})
        get.assert_called_once_with(client.eprint_url + '2101.00001v1')
        meta = json.loads((corpus.paper_dir(self.directory, '2101.00001', 'v1') / 'meta.json').read_text())
        self.assertEqual(meta['url'], client.eprint_url + '2101.00001v1')


if __name__ == '__main__':
    unittest.main()
