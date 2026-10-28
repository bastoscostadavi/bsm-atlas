"""One paced arXiv connection across cooperating processes on this machine."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import tempfile
import time


@contextmanager
def arxiv_slot(path=None, interval=3.1):
    path = Path(path) if path else Path(tempfile.gettempdir()) / f'bsm-atlas-arxiv-{os.getuid()}.lock'
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(descriptor, 'r+') as handle:
        if os.fstat(handle.fileno()).st_uid != os.getuid():
            raise ValueError('arXiv coordination lock has a different owner')
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            content = handle.read(100)
            previous = float(content) if content else 0
            delay = max(0, min(interval, interval - (time.time() - previous)))
            if delay:
                time.sleep(delay)
            yield
        finally:
            handle.seek(0)
            handle.truncate()
            handle.write(str(time.time()))
            handle.flush()
            fcntl.flock(handle, fcntl.LOCK_UN)
