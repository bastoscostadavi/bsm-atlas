#!/usr/bin/env python3
"""Restore a pinned catalogue or prepare and publish an immutable data release."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.snapshot import prepare, restore, verify, upload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['restore', 'verify', 'prepare', 'upload'])
    parser.add_argument('--output', type=Path, default=ROOT / '.build/data-release')
    parser.add_argument('--freeze', action='store_true', help='Freeze live inputs with committed code, then build and check the copy')
    parser.add_argument('--upload', action='store_true', help='Publish the prepared release and update atlas/snapshot.json')
    parser.add_argument('--target', help='Existing Git commit associated with this source snapshot')
    args = parser.parse_args()
    if args.action == 'restore':
        restore()
    elif args.action == 'verify':
        result = verify(); print('Pinned source snapshot verified:', result['tag'])
    elif args.action == 'prepare':
        result = prepare(output=args.output, freeze=args.freeze, target=args.target)
        print('Prepared:', args.output / 'snapshot.json', result['counts'])
        if args.upload:
            upload(args.output)
    else:
        result = upload(args.output); print('Published data snapshot:', result['tag'])


if __name__ == '__main__':
    main()
