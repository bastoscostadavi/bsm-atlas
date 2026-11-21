"""Start with verified cached arXiv metadata, then index and fetch all hep-ph.

Run from the repository root: python3 -u scripts/mirror_hepph.py
Source requests use the atlas harvester's ArxivClient and 3.1-second pacing.
Temporary failures retry after a pause; completed sources are skipped on resume.
"""
import argparse
import base64
import errno
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bsm_atlas import corpus, papers
from bsm_atlas.corpus_queue import PriorityReader


def retry_after(headers):
    value = (headers or {}).get('Retry-After', '')
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, parsedate_to_datetime(value).timestamp() - time.time())
        except (ValueError, TypeError, OverflowError):
            return 0


class ContinuousClient(corpus.Client):
    """Use the production harvester for sources, with automatic retry support."""

    MIN_INTERVAL = 3.1
    eprint_url = 'https://arxiv.org/e-print/'
    RETRY_POLICY = 'retry-after-or-60-seconds-v1'

    def __init__(self, directory, initial_cooldown=0):
        super().__init__(interval=self.MIN_INTERVAL, timeout=60)
        self.harvester = papers.ArxivClient()
        self.directory = Path(directory)
        self.state_path = self.directory / 'transfer-state.json'
        saved = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.rate_limits = saved.get('rate_limits', 0)
        # Retire the old lifetime-count exponential policy. Its locally chosen
        # six-hour deadline is not carried into the harvester-based runner.
        saved_deadline = saved.get('retry_at', 0) if saved.get('retry_policy') == self.RETRY_POLICY else 0
        self.retry_at = max(saved_deadline,
                            time.time() + initial_cooldown if initial_cooldown else 0)
        self.report('starting', retry_at=self.retry_at)

    def report(self, state, **details):
        corpus._write_atomic(self.state_path, json.dumps({
            'state': state, 'pid': os.getpid(), 'interval': self.interval,
            'rate_limits': self.rate_limits,
            'transport': 'atlas ArxivClient', 'retry_policy': self.RETRY_POLICY,
            'retry_at': self.retry_at,
            'updated': datetime.now(timezone.utc).isoformat(), **details}).encode())

    def wait_until(self, deadline, reason, url):
        self.report('cooldown', reason=reason, url=url, retry_at=deadline,
                    next_request=datetime.fromtimestamp(deadline, timezone.utc).isoformat())
        print('Cooldown: %s; next request after %s' % (
            reason, datetime.fromtimestamp(deadline, timezone.utc).isoformat()), flush=True)
        while time.time() < deadline:
            if (self.directory / 'STOP').exists():
                raise KeyboardInterrupt('Corpus STOP file present')
            time.sleep(min(30, deadline - time.time()))

    def get(self, url, limit=corpus.MAX_DOWNLOAD):
        failures = 0
        while True:
            if (self.directory / 'STOP').exists():
                raise KeyboardInterrupt('Corpus STOP file present')
            if self.retry_at > time.time():
                self.wait_until(self.retry_at, 'scheduled backoff', url)
            self.report('requesting', url=url)
            try:
                if url.startswith(self.eprint_url):
                    try:
                        body = self.harvester.get(url)
                        status, headers = 200, {}
                    except papers.RetrievalBlocked as error:
                        cause = error.__cause__
                        if not isinstance(cause, HTTPError):
                            raise
                        raise corpus.Blocked(str(error), cause.code, cause.headers) from error
                    except HTTPError as error:
                        if error.code not in {404, 410}:
                            raise
                        status, body, headers = error.code, b'', error.headers
                    except ValueError as error:
                        if str(error) != 'arXiv response exceeds the download bound':
                            raise
                        # corpus.fetch_one records a bounded source failure and
                        # moves on; one large archive must not stop the mirror.
                        raise OverflowError(str(error)) from error
                else:
                    status, body, headers = super().get(url, limit)
                if status < 500:
                    self.retry_at = 0
                    self.report('active', last_url=url, last_http_status=status)
                    return status, body, headers
                reason = 'HTTP %d' % status
            except corpus.Blocked as error:
                if error.code != 429:
                    self.report('blocked', reason=str(error))
                    raise
                self.rate_limits += 1
                delay = max(self.MIN_INTERVAL, retry_after(error.headers) or 60)
                self.retry_at = time.time() + delay
                # Save before waiting so a process restart cannot shorten the cooldown.
                self.wait_until(self.retry_at, str(error), url)
                continue
            except HTTPError as error:
                if error.code < 500:
                    self.report('failed', reason=str(error))
                    raise
                reason, headers = str(error), error.headers
            except (URLError, TimeoutError, ConnectionError) as error:
                reason, headers = str(error), {}
            except OSError as error:
                if error.errno != errno.EADDRNOTAVAIL:
                    raise
                reason, headers = str(error), {}
            failures += 1
            delay = max(retry_after(headers), min(1800, 60 * 2 ** min(failures - 1, 5)))
            self.retry_at = time.time() + delay
            self.wait_until(self.retry_at, reason, url)


def cached_records():
    atom = '{http://www.w3.org/2005/Atom}'
    arxiv = '{http://arxiv.org/schemas/atom}'
    records = {}
    for path in sorted((ROOT / '.harvest').glob('*/arxiv-primary-*.json')):
        saved = json.loads(path.read_text())
        body = base64.b64decode(saved['body_base64'], validate=True)
        if saved.get('body_encoding') == 'gzip':
            body = gzip.decompress(body)
        if sha256(body).hexdigest() != saved['sha256']:
            raise ValueError('Cached metadata hash mismatch: ' + str(path))
        for entry in ET.fromstring(body).findall(atom + 'entry'):
            primary = entry.find(arxiv + 'primary_category')
            if primary is None or primary.get('term') != 'hep-ph':
                continue
            identifier = entry.findtext(atom + 'id', '').split('/abs/')[-1]
            base, separator, number = identifier.rpartition('v')
            version = 'v' + number
            if not separator or not corpus.BASE_ID.fullmatch(base) or not corpus.VERSION.fullmatch(version):
                raise ValueError('Invalid cached arXiv identifier: ' + identifier)
            if base not in records or int(number) > int(records[base]['version'][1:]):
                records[base] = {
                    'arxiv': base, 'version': version,
                    'title': ' '.join(entry.findtext(atom + 'title', '').split()),
                    'categories': [node.get('term') for node in entry.findall(atom + 'category')],
                    'metadata_cache': str(path.relative_to(ROOT))}
    return sorted(records.values(), key=lambda row: corpus._sort_key(row['arxiv']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cooldown', type=float, default=0,
                        help='Initial cooldown in seconds (saved across restarts)')
    args = parser.parse_args()
    if args.cooldown < 0:
        parser.error('--cooldown must be nonnegative')
    directory = corpus.CORPUS
    directory.mkdir(parents=True, exist_ok=True)
    # This run lock spans all phases; fetch/index also take their own writer lock.
    with corpus.single_writer(directory / 'mirror-run'):
        client = ContinuousClient(directory, initial_cooldown=args.cooldown)
        state = directory / 'mirror-state.json'
        def phase(name, **details):
            corpus._write_atomic(state, json.dumps({'phase': name, **details}).encode())
            print(name, details, flush=True)
        seeds = cached_records()
        corpus._write_atomic(directory / 'bootstrap-index.jsonl',
                             ''.join(json.dumps(row) + '\n' for row in seeds).encode())
        phase('downloading_cached_batch', indexed=len(seeds))
        priority = PriorityReader(directory)
        corpus.fetch(directory, client=client, records=seeds, priority_records=priority,
                     log=lambda message: print(message, flush=True))
        if not (directory / 'index.jsonl').exists():
            phase('indexing_complete_hep_ph_set')
            corpus.build_index(directory, client=client, log=lambda message: print(message, flush=True))
        phase('downloading_complete_index')
        corpus.fetch(directory, client=client, priority_records=priority,
                     log=lambda message: print(message, flush=True))
        phase('finished', summary=corpus.status(directory))
        client.report('finished')


if __name__ == '__main__':
    main()
