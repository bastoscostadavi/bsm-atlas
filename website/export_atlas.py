#!/usr/bin/env python3
"""Refresh the static model snapshot from a read-only SQLite atlas.

Usage: python3 export_atlas.py /data/bsm-atlas/atlas/atlas.sqlite
The existing data.js supplies the conceptual schema descriptions.
"""
import argparse
import datetime
import json
from pathlib import Path
import sqlite3


def export(database, destination):
    prefix = "window.ATLAS_DATA = "
    previous = destination.read_text(encoding="utf-8").strip()
    if not previous.startswith(prefix):
        raise ValueError("Expected an existing data.js snapshot")
    document = json.loads(previous[len(prefix):].removesuffix(";"))
    con = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    def rows(table, key):
        return [dict(r) for r in con.execute(
            'SELECT * FROM "' + table + '" WHERE model_id=? AND model_revision=?', key)]

    def pack(records, columns):
        return [[r.get(c) if r.get(c) is not None else "" for c in columns] for r in records]

    field_sets = {
        "rg": ("theory_regimes", ["description_kind", "spacetime_dimension", "eft_truncation", "validity_assumptions", "geometry_boundary_notes"]),
        "p": ("theory_parameters", ["symbol", "definition", "normalization_convention", "restriction", "value_status"]),
        "y": ("theory_symmetries", ["symmetry_label", "internal_or_spacetime", "global_or_gauged", "imposed_or_accidental", "breaking_status", "anomaly_statement"]),
        "a": ("theory_assumptions", ["statement", "assumption_kind", "status"]),
        "v": ("theory_vacua", ["vacuum_label", "phase_assumptions", "parameter_assumptions", "status"]),
        "k": ("theory_breaking_steps", ["step_order", "order_parameter", "from_symmetry", "residual_symmetry", "assumed_or_established"]),
    }
    models = []
    for base in con.execute("""SELECT * FROM theory_specifications ts
                             WHERE revision=(SELECT max(revision) FROM theory_specifications newer WHERE newer.model_id=ts.model_id)
                             ORDER BY coalesce(display_name,model_id),revision"""):
        base = dict(base)
        key = (base["model_id"], base["revision"])
        m = {"i": key[0], "r": key[1], "n": base["display_name"], "s": base["completeness_status"],
             "c": base.get("covered_sectors") or "", "o": base.get("scope_note") or "",
             "b": base.get("baseline_label") or "", "bs": base.get("baseline_status") or ""}
        for prop, (table, columns) in field_sets.items():
            m[prop] = pack(rows(table, key), columns)
        group_rows = [dict(r) for r in con.execute("""
            SELECT g.*, group_concat(f.factor_label, ' × ') AS factors
            FROM theory_gauge_groups g
            LEFT JOIN theory_gauge_factors f ON f.group_id=g.group_id
            WHERE g.model_id=? AND g.model_revision=? GROUP BY g.group_id ORDER BY g.group_id
        """, key)]
        m["g"] = pack(group_rows, ["group_label", "global_form_status", "global_form_expression", "normalization_note", "factors"])
        field_rows = [dict(r) for r in con.execute("""
            SELECT f.*, r.representation_label, r.exact_charge,
                   coalesce(gf.factor_label,gg.group_label) AS factor_label
            FROM theory_fields f LEFT JOIN theory_field_representations r ON r.field_id=f.field_id
            LEFT JOIN theory_gauge_factors gf ON gf.factor_id=r.factor_id
            LEFT JOIN theory_gauge_groups gg ON gg.group_id=r.group_id
            WHERE f.model_id=? AND f.model_revision=? ORDER BY f.field_id,r.representation_id
        """, key)]
        m["f"] = pack(field_rows, ["field_label", "field_kind", "spin", "chirality", "multiplicity", "representation_label", "exact_charge", "factor_label", "field_reality_condition", "inherited_baseline_label"])
        # Preserve SQL NULL for the three logical flags; NULL is not false.
        interaction_cols = ["operator_label", "interaction_kind", "expression", "coefficient_restriction", "assumptions", "allowed_by_symmetry", "included_in_specification", "set_to_zero_by_assumption"]
        m["x"] = [[r.get(c) if index >= 5 else r.get(c) or "" for index,c in enumerate(interaction_cols)] for r in rows("theory_interactions", key)]
        actions = [dict(r) for r in con.execute("""
            SELECT s.symmetry_label, f.field_label, a.transformation_rule, a.exact_charge,a.conditions
            FROM theory_symmetry_actions a JOIN theory_symmetries s ON s.symmetry_id=a.symmetry_id
            JOIN theory_fields f ON f.field_id=a.field_id WHERE a.model_id=? AND a.model_revision=?
        """, key)]
        m["ya"] = pack(actions,["symmetry_label","field_label","transformation_rule","exact_charge","conditions"])
        sources = [dict(r) for r in con.execute("""
            SELECT p.paper_id,p.arxiv_id,pp.verified_title,l.role,l.source_model_label,
                   l.contribution_summary,l.reconciliation_status
            FROM paper_theory_links l LEFT JOIN paper_versions v ON v.paper_version_id=l.paper_version_id
            LEFT JOIN papers p ON p.paper_id=v.paper_id LEFT JOIN paper_profiles pp ON pp.paper_version_id=l.paper_version_id
            WHERE l.model_id=? AND l.model_revision=? ORDER BY p.paper_id
        """, key)]
        m["z"] = pack(sources,["paper_id","arxiv_id","verified_title","role","source_model_label","contribution_summary","reconciliation_status"])
        models.append(m)
    document["modelData"]["models"] = models
    for name in document["schema"]["info"]:
        safe = name.replace('"', '""')
        columns = con.execute('PRAGMA table_info("' + safe + '")').fetchall()
        if columns:
            document["schema"]["cols"][name] = " ".join(c["name"] for c in columns)
    document["snapshot"] = datetime.date.today().isoformat()
    document["paperCount"] = con.execute("SELECT count(*) FROM papers").fetchone()[0]
    con.close()
    destination.write_text(prefix + json.dumps(document, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Exported {len(models)} model records to {destination}")
    print("Review the website snapshot labels before publishing the refreshed data.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("data.js"))
    args = parser.parse_args()
    export(args.database, args.output)
