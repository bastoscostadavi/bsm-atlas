"""Synthetic export integration test. Test records are never published."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from export_atlas import export


class ExportTest(unittest.TestCase):
    def test_lossless_read_only_publication(self):
        directory = Path(__file__).resolve().parent
        document = json.loads((directory / "data.js").read_text(encoding="utf-8").removeprefix("window.ATLAS_DATA = ").strip().removesuffix(";"))
        with tempfile.TemporaryDirectory(prefix="atlas-export-test-") as tmp:
            root = Path(tmp)
            database = root / "atlas.sqlite"
            output = root / "site"
            output.mkdir()
            con = sqlite3.connect(database)
            primary = {"papers":"paper_id", "paper_versions":"paper_version_id", "paper_profiles":"paper_version_id", "paper_theory_links":"link_id", "theory_regimes":"regime_id", "theory_fields":"field_id", "theory_gauge_groups":"group_id", "theory_gauge_factors":"factor_id"}
            for name, columns in document["schema"]["cols"].items():
                if name in {"paper_assertions", "evidence_refs", "paper_assertion_evidence", "paper_summary_revisions"}:
                    continue  # Explicit test schemas below; independent of publication coverage.
                fields=[]
                for column in columns.split():
                    kind="INTEGER" if column in ["revision","model_revision","baseline_model_revision","allowed_by_symmetry","included_in_specification","set_to_zero_by_assumption"] else "TEXT"
                    fields.append(column+" "+kind+(" PRIMARY KEY" if primary.get(name)==column else ""))
                if name=="theory_specifications": fields.append("PRIMARY KEY(model_id,revision)")
                con.execute("CREATE TABLE "+name+" ("+",".join(fields)+")")
            con.executescript("""
                CREATE TABLE paper_assertions(assertion_id TEXT PRIMARY KEY,paper_version_id TEXT,statement TEXT,value_status TEXT,basis TEXT,review_status TEXT,FOREIGN KEY(paper_version_id) REFERENCES paper_versions(paper_version_id));
                CREATE TABLE evidence_refs(evidence_id TEXT PRIMARY KEY,locator TEXT,pdf_page INTEGER);
                CREATE TABLE paper_assertion_evidence(assertion_id TEXT,evidence_id TEXT,FOREIGN KEY(assertion_id) REFERENCES paper_assertions(assertion_id),FOREIGN KEY(evidence_id) REFERENCES evidence_refs(evidence_id));
                CREATE TABLE paper_summary_revisions(summary_id TEXT PRIMARY KEY,paper_version_id TEXT,summary_text TEXT,review_status TEXT,FOREIGN KEY(paper_version_id) REFERENCES paper_versions(paper_version_id));
            """)
            def insert(table, **values):
                con.execute("INSERT INTO "+table+" ("+",".join(values)+") VALUES ("+",".join("?" for _ in values)+")",list(values.values()))
            insert("papers",paper_id="P01",arxiv_id="1234.56789",source_kind="model")
            insert("paper_versions",paper_version_id="P01v2",paper_id="P01",version_label="v2")
            insert("paper_profiles",paper_version_id="P01v2",verified_title="TEST ONLY",author_abstract="SOURCE ABSTRACT",inspected_scope="Eq. 1",review_status=None)
            for revision in [1,2]: insert("theory_specifications",model_id="synthetic",revision=revision,display_name="TEST ONLY",completeness_status="partial_structural_specification")
            insert("theory_regimes",regime_id="R2",model_id="synthetic",model_revision=2,description_kind="TEST DESCRIPTION")
            insert("theory_gauge_groups",group_id="G2",model_id="synthetic",model_revision=2,regime_id="R2",group_label="TEST GROUP")
            insert("theory_fields",field_id="F2",model_id="synthetic",model_revision=2,regime_id="R2",field_label="TEST FIELD")
            insert("theory_interactions",interaction_id="X2",model_id="synthetic",model_revision=2,regime_id="R2",operator_label="TEST OPERATOR",allowed_by_symmetry=0,included_in_specification=None,set_to_zero_by_assumption=1)
            insert("paper_theory_links",link_id="L2",paper_version_id="P01v2",model_id="synthetic",model_revision=2,role="test_role",reconciliation_status="provisional")
            insert("paper_assertions",assertion_id="A1",paper_version_id="P01v2",statement="TEST CLAIM",value_status="unspecified",basis="source_stated",review_status="unchecked")
            insert("evidence_refs",evidence_id="E1",locator="Eq. (1)",pdf_page=4)
            insert("paper_assertion_evidence",assertion_id="A1",evidence_id="E1")
            insert("paper_summary_revisions",summary_id="S1",paper_version_id="P01v2",summary_text="AGENT SUMMARY",review_status="unchecked")
            con.execute("PRAGMA user_version=7")
            con.executescript((directory / "queries.sql").read_text(encoding="utf-8"))
            con.commit();con.close()
            source_hash=hashlib.sha256(database.read_bytes()).hexdigest()
            (root / "REVIEW.md").write_text("Test-only review; not a physics validation.",encoding="utf-8")
            destination=output / "data.js"
            destination.write_text("window.ATLAS_DATA = "+json.dumps(document)+";",encoding="utf-8")
            export(database,destination)
            result=json.loads(destination.read_text(encoding="utf-8").removeprefix("window.ATLAS_DATA = ").strip().removesuffix(";"))
            tables=result["relational"]["tables"]
            self.assertEqual(source_hash,hashlib.sha256(database.read_bytes()).hexdigest())
            self.assertEqual(len(tables["theory_specifications"]["rows"]),2)
            self.assertEqual(result["modelData"]["models"][0]["r"],2)
            self.assertEqual(result["modelData"]["coverage"]["interactions"],{"models":1,"rows":1})
            self.assertEqual(result["modelData"]["models"][0]["x"][0][5:],[0,None,1])
            interaction=tables["theory_interactions"]["rows"][0]
            self.assertEqual(interaction["regime_id"],"R2");self.assertIsNone(interaction["included_in_specification"])
            self.assertEqual(tables["paper_assertions"]["foreignKeys"][0]["table"],"paper_versions")
            self.assertEqual(result["relational"]["userVersion"],7)
            self.assertEqual(result["relational"]["validation"]["foreignKeyViolations"],[])
            self.assertEqual(result["reports"]["REVIEW.md"]["content"],"Test-only review; not a physics validation.")
            for artifact in result["downloads"]:
                self.assertEqual(artifact["sha256"],hashlib.sha256((output / artifact["path"]).read_bytes()).hexdigest())
            with sqlite3.connect(output / "downloads" / "atlas.sqlite") as copy:
                self.assertEqual(copy.execute("SELECT count(*) FROM theory_specifications").fetchone()[0],2)
            with sqlite3.connect(":memory:") as restored:
                restored.executescript((output / "downloads" / "atlas.sql").read_text(encoding="utf-8"))
                self.assertEqual(restored.execute("SELECT review_status FROM paper_profiles").fetchone()[0],None)
                self.assertEqual(restored.execute("PRAGMA user_version").fetchone()[0],7)


if __name__=="__main__":
    unittest.main()
