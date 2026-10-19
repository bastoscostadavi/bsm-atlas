#!/usr/bin/env python3
"""Run the active catalogue's local and CI checks without fetching sources."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    python = [sys.executable, '-B']
    commands = [['node', '--check', str(p.relative_to(ROOT))]
                for p in sorted((ROOT / 'website').glob('*.js'))]
    commands += [
        python + ['website/build_field_catalogue.py', '--check'],
        python + ['-m', 'unittest', 'discover', '-s', 'website', '-p', 'test_*.py'],
        python + ['atlas/test_parameterized_entry.py'],
        ['node', 'website/check.mjs'],
        ['node', 'website/field-catalogue.test.mjs'],
        ['node', 'website/representation-diagrams.test.mjs'],
    ]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    for command in commands:
        print('> ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    print('All catalogue checks passed.')


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
