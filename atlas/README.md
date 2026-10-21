# Catalogue data

[Catalogue source](catalogue.json) · [Conventions](FIELD_CONTENT_CONVENTIONS.md) · [Ingestion instructions](../BSM_ATLAS_AGENT_PROMPT.md)

The authoritative source uses `bsm-atlas-2` and has four lists: `papers`, `entries`, `problems` and `entry_problems`. An entry contains a complete `specification` and its `references`. References may include short source locators and a source-to-canonical parameter-name map. Entry names and aliases help navigation; they do not distinguish mathematical objects.

Numerical specifications use `field-content-2`. Symbolic charge families use `field-content-3`, with integer parameters and polynomial constraints. The stored numerical scalar unit is `real_module`. The machine key `copies` means multiplicity.

Each representation row has exactly four fields: `lorentz`, `reality`, `copies` and `gauge_representations`. Free-text field labels, symbols and other annotations are rejected. Model names and paper metadata are stored separately from the mathematical specification; readable representation notation is computed for display.

## Problems

`problems` defines each target with `id`, `name` and `description`. `entry_problems` contains `entry_id`, `problem_id`, `paper_id`, nonempty `locators` and a concise `result`. One row records a paper's demonstrated solution for that exact specification, including the relevant assumptions or benchmark. Its supporting `(entry_id, paper_id)` must exist in the model's references. The triple is unique; additional papers can support the same model–problem pair.

Only source-demonstrated parameter regions, benchmarks or analytic results qualify. Mere candidates, possible mechanisms, motivation, collider signatures or constraints without a solution do not. Source review establishes scientific support; schema checks establish shape and cross-reference integrity, not the truth of the result. Claims concern the source's assumptions and constraints, not certified present-day viability or simultaneous solutions. Missing evidence is not a negative classification.

Use `catalogue.py --add-demonstration demonstration.json` for a dry run, with `--write` to save. Problem definitions are curated in the source vocabulary; do not create synonyms for an existing target. These records never enter model fingerprints or the four structural groupings.

To count recorded problems per model without double-counting supporting papers:

```sql
SELECT e.entry_id, e.name, COUNT(DISTINCT p.problem_id) AS recorded_problems
FROM entries AS e LEFT JOIN entry_problems AS p USING (entry_id)
GROUP BY e.entry_id, e.name
ORDER BY recorded_problems DESC, e.name;
```

A zero is an absence of recorded qualifying evidence, not a demonstrated inability to solve problems.

## Code

- `catalogue.py`: strict source validation, normalized model ingestion and source-linked demonstration ingestion.
- `entry_validation.py`, `catalogue_identity.py`, `scalar_conventions.py`: numerical shape validation, normalization, real scalar counting and exact identity.
- `charge_expressions.py`, `parameterized_entry.py`, `symbolic_identity.py`: safe integer-polynomial syntax, specialization and canonical symbolic-template matching.
- `nonabelian_core.py`: derived semisimple gauge and matter restrictions and full-algebra keys.
- `prepare_entry.py`, `check_entry.py`: read-only normalization and duplicate preflight against the generated SQLite export.
- `schema.sql`: relational export tables and the `entry_layers` and `entry_identity` views.

`catalogue.schema.json` and `entry.schema.json` document structure; executable checks enforce cross-field mathematics and canonical storage. `reference_spectra.json` supplies the SM/MSSM display shorthand and never replaces the full inventory in an entry. `examples/` contains illustrative intake specifications, not accepted source models.

Run `make build` after source changes and `make check` before publication. Do not edit `FIELD_CONTENT_CATALOGUE.json` or the website downloads directly.
