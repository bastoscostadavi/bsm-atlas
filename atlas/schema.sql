-- Generated SQLite is a queryable projection of atlas/catalogue.json.
-- Exact specifications are authoritative; the three grouping tables are caches.
PRAGMA foreign_keys=ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;
CREATE TABLE papers (paper_id TEXT PRIMARY KEY, arxiv TEXT NOT NULL UNIQUE, title TEXT NOT NULL, authors TEXT NOT NULL) STRICT;
CREATE TABLE semisimple_algebras (semisimple_id TEXT PRIMARY KEY, algebra TEXT NOT NULL, canonical_json TEXT NOT NULL CHECK(json_valid(canonical_json))) STRICT;
CREATE TABLE full_gauge_algebras (full_algebra_id TEXT PRIMARY KEY, algebra TEXT NOT NULL,
  semisimple_id TEXT NOT NULL REFERENCES semisimple_algebras, abelian_rank INTEGER NOT NULL CHECK(abelian_rank>=0),
  canonical_json TEXT NOT NULL CHECK(json_valid(canonical_json))) STRICT;
CREATE TABLE nonabelian_cores (core_id TEXT PRIMARY KEY, algebra TEXT NOT NULL,
  semisimple_id TEXT NOT NULL REFERENCES semisimple_algebras, canonical_json TEXT NOT NULL CHECK(json_valid(canonical_json))) STRICT;
CREATE TABLE entries (entry_id TEXT PRIMARY KEY, name TEXT NOT NULL,
  schema_version TEXT NOT NULL CHECK(schema_version IN ('field-content-2','field-content-3')),
  specification_json TEXT NOT NULL CHECK(json_valid(specification_json)),
  fingerprint TEXT NOT NULL UNIQUE, semisimple_id TEXT NOT NULL REFERENCES semisimple_algebras,
  full_algebra_id TEXT NOT NULL REFERENCES full_gauge_algebras, core_id TEXT NOT NULL REFERENCES nonabelian_cores) STRICT;
CREATE TABLE entry_papers (entry_id TEXT NOT NULL REFERENCES entries, paper_id TEXT NOT NULL REFERENCES papers,
  locators_json TEXT NOT NULL CHECK(json_valid(locators_json)), parameter_names_json TEXT NOT NULL CHECK(json_valid(parameter_names_json)),
  PRIMARY KEY(entry_id,paper_id)) STRICT;
CREATE TABLE problems (problem_id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK(length(trim(name,char(9,10,11,12,13,32)))>0),
  category TEXT NOT NULL CHECK(category IN ('empirical','structural','reported_discrepancy'))) STRICT;
CREATE INDEX problem_categories ON problems(category);
-- Positive links only; model_id identifies an entries.entry_id.
CREATE TABLE model_problems (model_id TEXT NOT NULL, problem_id TEXT NOT NULL REFERENCES problems,
  paper_id TEXT NOT NULL, PRIMARY KEY(model_id,problem_id,paper_id),
  FOREIGN KEY(model_id,paper_id) REFERENCES entry_papers(entry_id,paper_id)) STRICT;
CREATE INDEX problem_models ON model_problems(problem_id,model_id);
-- 0 means no qualifying demonstration recorded, not a demonstrated failure.
CREATE VIEW model_problem_matrix AS SELECT e.entry_id AS model_id,p.problem_id,
  EXISTS(SELECT 1 FROM model_problems mp WHERE mp.model_id=e.entry_id AND mp.problem_id=p.problem_id) AS solves
  FROM entries e CROSS JOIN problems p;
CREATE TABLE aliases (alias_id TEXT PRIMARY KEY, entry_id TEXT NOT NULL REFERENCES entries, name TEXT NOT NULL) STRICT;
CREATE TABLE gauge_factors (entry_id TEXT NOT NULL REFERENCES entries, factor_id TEXT NOT NULL, position INTEGER NOT NULL CHECK(position>=0),
  family TEXT NOT NULL CHECK(family IN ('A','B','C','D','E','F','G','U1')), rank INTEGER NOT NULL,
  CHECK((family='A' AND rank>=1) OR (family='B' AND rank>=3) OR (family='C' AND rank>=2)
    OR (family='D' AND rank>=4) OR (family='E' AND rank IN (6,7,8)) OR (family='F' AND rank=4)
    OR (family='G' AND rank=2) OR (family='U1' AND rank=1)),
  PRIMARY KEY(entry_id,factor_id), UNIQUE(entry_id,position)) STRICT;
CREATE TABLE matter (entry_id TEXT NOT NULL REFERENCES entries, row_id INTEGER NOT NULL CHECK(row_id>=0),
  lorentz_json TEXT NOT NULL CHECK(json_valid(lorentz_json)), reality TEXT NOT NULL CHECK(reality IN ('none','real','complex','real_module')),
  copies INTEGER NOT NULL CHECK(copies>0), PRIMARY KEY(entry_id,row_id)) STRICT;
CREATE TABLE matter_representations (entry_id TEXT NOT NULL, row_id INTEGER NOT NULL, factor_id TEXT NOT NULL,
  dynkin_json TEXT CHECK(dynkin_json IS NULL OR json_valid(dynkin_json)),
  -- Decimal TEXT stores arbitrary-precision integers; no floats or expressions.
  charge TEXT CHECK(charge IS NULL OR charge='0' OR
    (length(charge)>0 AND charge NOT GLOB '*[^0-9]*' AND substr(charge,1,1) BETWEEN '1' AND '9') OR
    (length(charge)>1 AND substr(charge,1,1)='-' AND substr(charge,2) NOT GLOB '*[^0-9]*' AND substr(charge,2,1) BETWEEN '1' AND '9')),
  charge_expression TEXT,
  CHECK((dynkin_json IS NOT NULL)+(charge IS NOT NULL)+(charge_expression IS NOT NULL)=1),
  PRIMARY KEY(entry_id,row_id,factor_id), FOREIGN KEY(entry_id,row_id) REFERENCES matter,
  FOREIGN KEY(entry_id,factor_id) REFERENCES gauge_factors) STRICT;
CREATE TRIGGER representation_kind BEFORE INSERT ON matter_representations BEGIN
  SELECT CASE WHEN (SELECT family='U1' FROM gauge_factors WHERE entry_id=NEW.entry_id AND factor_id=NEW.factor_id)
      != (NEW.dynkin_json IS NULL) THEN RAISE(ABORT,'Dynkin labels for simple factors; charges for U(1)') END;
  SELECT CASE WHEN NEW.charge_expression IS NOT NULL AND
      (SELECT schema_version FROM entries WHERE entry_id=NEW.entry_id)!='field-content-3'
      THEN RAISE(ABORT,'Charge expressions require a parameterized entry') END;
END;
CREATE TRIGGER representation_kind_update BEFORE UPDATE ON matter_representations BEGIN
  SELECT CASE WHEN (SELECT family='U1' FROM gauge_factors WHERE entry_id=NEW.entry_id AND factor_id=NEW.factor_id)
      != (NEW.dynkin_json IS NULL) THEN RAISE(ABORT,'Dynkin labels for simple factors; charges for U(1)') END;
  SELECT CASE WHEN NEW.charge_expression IS NOT NULL AND
      (SELECT schema_version FROM entries WHERE entry_id=NEW.entry_id)!='field-content-3'
      THEN RAISE(ABORT,'Charge expressions require a parameterized entry') END;
END;
CREATE TABLE entry_parameters (entry_id TEXT NOT NULL REFERENCES entries, name TEXT NOT NULL, domain TEXT NOT NULL CHECK(domain='integer'),
  PRIMARY KEY(entry_id,name)) STRICT;
CREATE TABLE entry_constraints (entry_id TEXT NOT NULL REFERENCES entries, position INTEGER NOT NULL CHECK(position>=0), expression TEXT NOT NULL,
  PRIMARY KEY(entry_id,position)) STRICT;
CREATE VIEW entry_layers AS SELECT e.entry_id,e.semisimple_id,e.full_algebra_id,e.core_id,a.abelian_rank
  FROM entries e JOIN full_gauge_algebras a USING(full_algebra_id);
CREATE VIEW entry_identity AS SELECT e.entry_id,e.fingerprint,e.specification_json AS input_json,
  a.canonical_json AS algebra_signature FROM entries e JOIN full_gauge_algebras a USING(full_algebra_id);
CREATE INDEX paper_entries ON entry_papers(paper_id);
CREATE INDEX entries_semisimple ON entries(semisimple_id);
CREATE INDEX entries_full_algebra ON entries(full_algebra_id);
CREATE INDEX entries_core ON entries(core_id);
