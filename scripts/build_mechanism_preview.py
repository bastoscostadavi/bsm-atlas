#!/usr/bin/env python3
"""Export public mechanism associations from compact catalogue records."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsm_atlas.literature import preview


def payload():
    return preview('mechanisms')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = payload()
    content = 'window.ATLAS_MECHANISMS = ' + json.dumps(result, ensure_ascii=False, separators=(',', ':')) + ';\n'
    target = ROOT / 'website/mechanism-data.js'
    if args.check:
        if target.read_text() != content:
            raise ValueError('Stale website mechanism preview; run scripts/build_mechanism_preview.py')
    else:
        target.write_text(content)
    print(f"Mechanism preview: {len(result['mechanisms'])} mechanisms, {sum(len(x) for x in result['links'].values())} model–mechanism links; {len(result['assessed'])} assessed entries.")


if __name__ == '__main__':
    main()
