#!/usr/bin/env python3
"""Recompute the manuscript census from the authoritative catalogue.

Run from any directory. This script does not modify the atlas or its exports.
Use --output to save the census and --check to compare manuscript count macros.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bsm_atlas.build import main_data


def census():
    raw = (ROOT / "atlas/catalogue.json").read_bytes()
    source = json.loads(raw)
    data = main_data(source)
    by_id = {entry["id"]: entry for entry in data["entries"]}
    vlq_ids = ["vlq-by-doublet", "vlq-tb-doublet", "vlq-xt-doublet"]
    scalar_ids = ["complex-singlet-portal", "vector-portal-abelian-higgs"]
    # These comparisons are the concrete claims made in the worked examples.
    assert len({by_id[key]["coreId"] for key in vlq_ids}) == 1
    assert len({by_id[key]["identity"]["fingerprint"] for key in vlq_ids}) == 3
    assert len({by_id[key]["coreId"] for key in scalar_ids}) == 1
    assert len({by_id[key]["fullAlgebraId"] for key in scalar_ids}) == 2
    sizes = Counter(len(core["entryIds"]) for core in data["cores"])
    schemas = Counter(entry["specification"]["schema_version"] for entry in data["entries"])
    counts = {
        **data["counts"],
        "numericalEntries": schemas["field-content-2"],
        "symbolicFamilies": schemas["field-content-3"],
        "paperLinks": sum(len(entry["references"]) for entry in source["entries"]),
        "singletonCores": sizes[1],
        "pairCores": sizes[2],
        "tripleCores": sizes[3],
        "entriesInSharedCores": sum(size * count for size, count in sizes.items() if size > 1),
    }
    return {
        "source": "atlas/catalogue.json",
        "source_sha256": sha256(raw).hexdigest(),
        "convention": data["version"],
        "counts": counts,
        "abelian_rank_histogram": dict(sorted(Counter(entry["abelianRank"] for entry in data["entries"]).items())),
        "core_size_histogram": dict(sorted(sizes.items())),
        "semisimple_algebras": [
            {"algebra": item["algebra"], "entries": len(item["entryIds"]),
             "cores": len(item["coreIds"]), "full_algebras": len(item["fullAlgebraIds"])}
            for item in data["semisimpleAlgebras"]
        ],
        "full_algebras": [
            {"algebra": item["algebra"], "entries": len(item["entryIds"])}
            for item in data["fullAlgebras"]
        ],
        "shared_cores": [
            {"entries": item["entryIds"], "names": [by_id[key]["name"] for key in item["entryIds"]]}
            for item in data["cores"] if len(item["entryIds"]) > 1
        ],
        "worked_examples": {
            "vector_like_doublets": {
                key: [
                    int(row["gauge_representations"]["hypercharge"]["charge"])
                    for row in by_id[key]["specification"]["matter"][-2:]
                ] for key in vlq_ids
            },
            "scalar_core_comparison": scalar_ids,
        },
    }


def check_manuscript(result):
    text = (ROOT / "paper/main.tex").read_text()
    mapping = {
        "AtlasEntries": "entries", "AtlasPapers": "papers",
        "AtlasLinkedPapers": "linkedPapers", "AtlasCores": "cores",
        "AtlasFullAlgebras": "fullAlgebras", "AtlasSemisimpleAlgebras": "semisimpleAlgebras",
        "AtlasNumerical": "numericalEntries", "AtlasFamilies": "symbolicFamilies",
        "AtlasPaperLinks": "paperLinks", "AtlasSingletonCores": "singletonCores",
        "AtlasPairCores": "pairCores", "AtlasTripleCores": "tripleCores",
        "AtlasSharedEntries": "entriesInSharedCores",
    }
    for macro, key in mapping.items():
        match = re.search(r"\\newcommand\{\\" + macro + r"\}\{(\d+)\}", text)
        if match is None or int(match.group(1)) != result["counts"][key]:
            raise ValueError(f"Manuscript macro {macro} does not match current source {key}")
    digest = re.search(r"digest begins \\texttt\{([0-9a-f]+)\}", text)
    if digest is None or digest.group(1) != result["source_sha256"][:12]:
        raise ValueError("Manuscript source digest does not match the current catalogue")
    assert sum(item["entries"] for item in result["semisimple_algebras"]) == result["counts"]["entries"]
    assert sum(item["cores"] for item in result["semisimple_algebras"]) == result["counts"]["cores"]
    return "Manuscript counts and worked-example identities agree with the current catalogue."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = census()
    content = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(content)
    if args.check:
        print(check_manuscript(result))
    elif not args.output:
        print(content, end="")
    if args.output:
        print(f"Saved census to {args.output}")


if __name__ == "__main__":
    main()
