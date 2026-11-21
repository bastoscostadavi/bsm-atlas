"""Small samples of independent published inventories for offline unit tests."""
from copy import deepcopy
import json

from bsm_atlas.catalogue import ROOT


def catalogue_sample(*identifiers):
    data = json.loads((ROOT / "atlas/catalogue.json").read_text())
    wanted = set(identifiers)
    entries = [deepcopy(entry) for entry in data["entries"] if entry["id"] in wanted]
    if {entry["id"] for entry in entries} != wanted:
        raise ValueError("Missing published test inventory")
    for entry in entries:
        entry["references"] = entry["references"][:1]
    paper_ids = {reference["paper_id"] for entry in entries for reference in entry["references"]}
    return {"schema_version": data["schema_version"],
            "papers": [paper for paper in data["papers"] if paper["id"] in paper_ids],
            "entries": entries}
