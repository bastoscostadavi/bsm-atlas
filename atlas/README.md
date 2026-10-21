# Catalogue data

[Catalogue source](catalogue.json) · [Conventions](FIELD_CONTENT_CONVENTIONS.md) · [Ingestion instructions](../BSM_ATLAS_AGENT_PROMPT.md)

The authoritative source uses `bsm-atlas-4` and has four lists: `papers`, `entries`, `problems` and `model_problems`. An entry contains a complete `specification` and its `references`. References may include short source locators and a source-to-canonical parameter-name map. Entry names and aliases help navigation; they do not distinguish mathematical objects.

Numerical specifications use `field-content-2`. Symbolic charge families use `field-content-3`, with integer parameters and polynomial constraints. The stored numerical scalar unit is `real_module`. The machine key `copies` means multiplicity.

Each representation row has exactly four fields: `lorentz`, `reality`, `copies` and `gauge_representations`. Free-text field labels, symbols and other annotations are rejected. Model names and paper metadata are stored separately from the mathematical specification; readable representation notation is computed for display.

## Problems

`problems` defines each target with `id` (exported as `problem_id`), `name` and a required `category`: `empirical`, `structural` or `reported_discrepancy`. Empirical problems are established gaps in the minimal SM's account of observations. Structural questions seek explanations or naturalness rather than repairing an established contradiction; strong CP and the inflationary scenario are classified here. Reported discrepancies are source-era anomaly targets without a current-status assessment, not a declaration that an anomaly is resolved. These are editorial distinctions, not changes to model identity or scientific-quality scores.

`model_problems` contains only `model_id`, `problem_id` and `paper_id`. `model_id` identifies an `entries.entry_id`; the supporting model–paper pair must exist in `entry_papers`. Each row is a positive link backed by that paper, with scientific details left in the reference. The triple is unique; additional papers can support the same model–problem pair.

Only source-demonstrated parameter regions, benchmarks or analytic results qualify. Mere candidates, possible mechanisms, motivation, collider signatures or constraints without a solution do not. Source review establishes scientific support; schema checks establish shape and cross-reference integrity, not the truth of the result. Claims concern the source's assumptions and constraints, not certified present-day viability or simultaneous solutions. Missing evidence is not a negative classification.

Use `catalogue.py --add-problem-link link.json` for a dry run, with `--write` to save. Problem names and categories are curated in the source vocabulary; do not create synonyms for an existing target. These links never enter model fingerprints or the four structural groupings.

To count distinct recorded targets per model, keeping their categories separate and not double-counting supporting papers:

```sql
SELECT e.entry_id, e.name,
  COUNT(DISTINCT CASE WHEN p.category='empirical' THEN mp.problem_id END) AS empirical_problems,
  COUNT(DISTINCT CASE WHEN p.category='structural' THEN mp.problem_id END) AS structural_questions,
  COUNT(DISTINCT CASE WHEN p.category='reported_discrepancy' THEN mp.problem_id END) AS reported_discrepancies
FROM entries AS e LEFT JOIN model_problems AS mp ON mp.model_id=e.entry_id
LEFT JOIN problems AS p USING (problem_id)
GROUP BY e.entry_id, e.name
ORDER BY e.name;
```

For a binary matrix, query `model_problem_matrix(model_id, problem_id, solves)`. This derived view returns 1 when at least one supporting paper is recorded and 0 otherwise; it does not duplicate stored links. A zero is an absence of recorded qualifying evidence, not a demonstrated inability to solve problems.

## Code

- `catalogue.py`: strict source validation, normalized model ingestion and paper-backed problem-link ingestion.
- `entry_validation.py`, `catalogue_identity.py`, `scalar_conventions.py`: numerical shape validation, normalization, real scalar counting and exact identity.
- `charge_expressions.py`, `parameterized_entry.py`, `symbolic_identity.py`: safe integer-polynomial syntax, specialization and canonical symbolic-template matching.
- `nonabelian_core.py`: derived semisimple gauge and matter restrictions and full-algebra keys.
- `prepare_entry.py`, `check_entry.py`: read-only normalization and duplicate preflight against the generated SQLite export.
- `schema.sql`: relational export tables and the `entry_layers`, `entry_identity` and `model_problem_matrix` views.

`catalogue.schema.json` and `entry.schema.json` document structure; executable checks enforce cross-field mathematics and canonical storage. `reference_spectra.json` supplies the SM/MSSM display shorthand and never replaces the full inventory in an entry. `examples/` contains illustrative intake specifications, not accepted source models.

Run `make build` after source changes and `make check` before publication. Do not edit `FIELD_CONTENT_CATALOGUE.json` or the website downloads directly.
