#!/usr/bin/env python3
"""Generate the public corpus inventory from the authoritative seed, not the DB.

The planned extraction scope is NOT a completed extraction or a paper summary.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def build(seed):
    text = seed.read_text(encoding="utf-8")
    versions = {}
    for line in text.splitlines():
        match = re.match(r"\| (P\d{2}) \| \[([^]]+)\].*?\| (model|review|classification|tool) \|", line)
        if match:
            versions[match[1]] = (match[2], match[3])
    papers = []
    sections = re.split(r"(?m)^### (P\d{2}) — (.+)\n", text)[1:]
    for index in range(0, len(sections), 3):
        paper_id, title, body = sections[index:index + 3]
        if paper_id not in versions:
            raise ValueError("Missing pinned manifest version: " + paper_id)
        metadata = re.search(r"\*\*(.+?)\s+\((\d{4})\)\. \[", body)
        if not metadata:
            raise ValueError("Missing seed bibliographic line: " + paper_id)
        scope = re.sub(r"(?s)^\s*\*\*.*?\*\*\s*\n\s*\*[^\n]+\*\s*\n", "", body).strip()
        # Strip emphasis only; preserve the seed's wording and any links.
        scope = scope.split("\n## ")[0].replace("**", "")
        papers.append({"id": paper_id, "title": title, "authors": metadata[1],
                       "year": int(metadata[2]), "arxivVersion": versions[paper_id][0],
                       "kind": versions[paper_id][1], "plannedScope": scope})
    expected = {f"P{i:02}" for i in range(1, 51)}
    if {p["id"] for p in papers} != expected or len(papers) != 50:
        raise ValueError("Expected exactly the 50 seed papers, P01–P50")
    return {"source": "BSM_ATLAS_SEED.md", "sourceSha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
            "meaning": "Seed bibliography and planned scope; not extraction/review results", "papers": papers}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=Path(__file__).resolve().parent.parent / "BSM_ATLAS_SEED.md")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("manifest.js"))
    parser.add_argument("--check", action="store_true", help="Validate the generated file without changing it")
    args = parser.parse_args()
    document = build(args.seed)
    encoded = "window.ATLAS_MANIFEST = " + json.dumps(document, ensure_ascii=False, separators=(",", ":")) + ";\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != encoded:
            raise SystemExit("Manifest is stale. Run python3 website/build_manifest.py from the repository root.")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    print(f"Generated {len(document['papers'])} seed entries; no extraction status inferred.")
