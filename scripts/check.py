#!/usr/bin/env python3
"""Run catalogue validation, export consistency and interface checks."""
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
        python + ['-m', 'bsm_atlas', 'build', '--check'],
        python + ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
        ['node', 'tests/check_assets.mjs'],
        ['node', 'tests/field-catalogue.test.mjs'],
        ['node', 'tests/problem-explorer.test.mjs'],
        ['node', 'tests/representation-diagrams.test.mjs'],
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
