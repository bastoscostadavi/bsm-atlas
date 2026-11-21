"""Cooperative paid-call budget shared by first pass and Luna recovery."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import time

from .catalogue import ROOT

DIRECTORY = ROOT / '.harvest' / 'luna-call-slots'
LIMIT = 16


def take(directory=DIRECTORY, limit=LIMIT):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for number in range(limit):
        handle = (directory / f'{number:02d}.lock').open('a')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            continue
        return handle
    return None


def release(handle):
    fcntl.flock(handle, fcntl.LOCK_UN)
    handle.close()


@contextmanager
def first_pass_slot(directory=DIRECTORY):
    handle = take(directory)
    while handle is None:
        time.sleep(.2)
        handle = take(directory)
    try:
        yield
    finally:
        release(handle)
