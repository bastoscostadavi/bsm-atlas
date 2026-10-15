"""Lossless publication layer; never reconstruct missing scientific assertions."""
import base64
import hashlib
import json
from pathlib import Path
import re
import sqlite3


def quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def serializable(value):
    if isinstance(value, bytes):
        return {"$binaryBase64": base64.b64encode(value).decode("ascii")}
    return value


def collect(con):
    tables = {}
    for name, ddl in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        columns = [dict(row) for row in con.execute("PRAGMA table_info(" + quote(name) + ")")]
        if any(re.fullmatch(r"password|access_token|api_key|private_key|credential", c["name"], re.I) for c in columns):
            raise ValueError("Refusing to publish a potentially sensitive column in " + name)
        tables[name] = {"columns": columns, "foreignKeys": [dict(row) for row in con.execute("PRAGMA foreign_key_list(" + quote(name) + ")")],
                        "sql": ddl, "rows": [{key: serializable(value) for key, value in dict(row).items()}
                                              for row in con.execute("SELECT * FROM " + quote(name))]}
    integrity = [row[0] for row in con.execute("PRAGMA integrity_check")]
    violations = [dict(row) for row in con.execute("PRAGMA foreign_key_check")]
    return {"formatVersion": 2, "userVersion": con.execute("PRAGMA user_version").fetchone()[0],
            "applicationId": con.execute("PRAGMA application_id").fetchone()[0], "tables": tables,
            "validation": {"integrityCheck": integrity, "foreignKeyViolations": violations,
                           "meaning": "SQLite integrity and references only; not independent physics validation"}}


def publish(con, document, database, directory, downloads=True):
    relational = collect(con)
    if relational["validation"]["integrityCheck"] != ["ok"] or relational["validation"]["foreignKeyViolations"]:
        raise ValueError("Refusing publication: database integrity or foreign-key checks failed")
    document["relational"] = relational
    document["exportVersion"] = 2
    document["reports"] = {}
    document["downloads"] = []
    latest_keys = {(m["i"], m["r"]) for m in document["modelData"]["models"]}
    document["modelData"]["coverage"] = {}
    for label in ["gauge_groups", "gauge_factors", "field_representations", "interactions", "symmetries", "breaking_steps", "vacua"]:
        records = [r for r in relational["tables"].get("theory_" + label, {}).get("rows", [])
                   if (r.get("model_id"), r.get("model_revision")) in latest_keys]
        document["modelData"]["coverage"][label] = {"models": len({r["model_id"] for r in records}), "rows": len(records)}
    names = set(document["schema"]["info"])
    additional = []
    for name, table in relational["tables"].items():
        document["schema"]["cols"][name] = " ".join(c["name"] for c in table["columns"])
        if name not in names:
            related = sorted({fk["table"] for fk in table["foreignKeys"]})
            document["schema"]["info"][name] = ["One stored database row", "Description not provided by the data dictionary", "No editorial example recorded", related]
            additional.append(name)
    if additional:
        document["schema"]["groups"].append(["Additional database tables", "Discovered directly from SQLite; no scientific interpretation inferred", additional])
    output = directory / "downloads"
    output.mkdir(exist_ok=True)

    def register(path, label):
        document["downloads"].append({"path": path.relative_to(directory).as_posix(), "label": label,
                                       "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    if downloads:
        backup_path = output / "atlas.sqlite"
        if backup_path.resolve() == database.resolve():
            raise ValueError("The published copy must not overwrite the source database")
        with sqlite3.connect(backup_path) as target:
            con.backup(target)
        sql = "\n".join(con.iterdump()) + f"\nPRAGMA user_version={relational['userVersion']};\nPRAGMA application_id={relational['applicationId']};\n"
        sql_path = output / "atlas.sql"
        sql_path.write_text(sql, encoding="utf-8")
        # Verify the SQL export can reconstruct the rows before registering it.
        with sqlite3.connect(":memory:") as restored:
            restored.row_factory = sqlite3.Row
            restored.executescript(sql)
            for name, table in relational["tables"].items():
                recovered = [{key: serializable(v) for key,v in dict(r).items()} for r in restored.execute("SELECT * FROM " + quote(name))]
                canonical = lambda records: sorted(json.dumps(r,sort_keys=True,ensure_ascii=False) for r in records)
                if canonical(recovered) != canonical(table["rows"]):
                    raise ValueError("SQL reconstruction row values differ for " + name)
        relational["validation"]["sqlReconstruction"] = "passed: every exported row value matches"
        register(backup_path, "SQLite database snapshot")
        register(sql_path, "Reproducible SQL export")
    provenance = database.parent / "source_snapshot.json"
    document.pop("sourceSnapshot", None)
    if provenance.is_file():
        document["sourceSnapshot"] = json.loads(provenance.read_text(encoding="utf-8"))
        path = output / provenance.name
        path.write_text(provenance.read_text(encoding="utf-8"), encoding="utf-8")
        register(path, "Source snapshot provenance")
    for name in ["ATLAS.md", "PAPERS.md", "SCHEMA.md", "REVIEW.md", "DATA_DICTIONARY.md", "DATABASE_DESIGN.md"]:
        source = database.parent / name
        if source.is_file():
            content = source.read_text(encoding="utf-8")
            path = output / name
            path.write_text(content, encoding="utf-8")
            document["reports"][name] = {"content": content, "path": "downloads/" + name}
            register(path, name)
    # JSON includes all original row values, IDs, schema constraints and reports.
    json_path = directory / "atlas-data.json"
    json_path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    register(json_path, "Complete exported atlas (JSON)")
    return relational
