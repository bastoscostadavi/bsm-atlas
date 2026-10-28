"""One arXiv request at a time, even with two independent worker providers."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from bsm_atlas.request_gate import arxiv_slot


class RequestGateTests(unittest.TestCase):
    def test_serializes_two_process_clients_and_paces_following_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'requests.lock'
            events=[];started=threading.Event()
            def first():
                with arxiv_slot(path,interval=0):
                    events.append('first-enter');started.set();time.sleep(.03)
                    events.append('first-exit')
            def second():
                started.wait()
                with arxiv_slot(path,interval=0):events.append('second-enter')
            with ThreadPoolExecutor(max_workers=2) as pool:
                a,b=pool.submit(first),pool.submit(second);a.result();b.result()
            self.assertEqual(events,['first-enter','first-exit','second-enter'])
            with patch('bsm_atlas.request_gate.time.sleep') as sleep:
                with arxiv_slot(path,interval=3.1):pass
                self.assertGreater(sleep.call_args.args[0],3)

    def test_refuses_symlink_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'target';target.write_text('')
            link=Path(directory)/'link';link.symlink_to(target)
            with self.assertRaises(OSError):
                with arxiv_slot(link):pass
