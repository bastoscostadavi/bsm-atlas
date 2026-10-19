# Catalogue data

[Catalogue source](catalogue.json) · [Conventions](FIELD_CONTENT_CONVENTIONS.md) · [Ingestion instructions](../BSM_ATLAS_AGENT_PROMPT.md)

The authoritative source has two lists: `papers` and `entries`. An entry contains a complete `specification` and its `references`. References may include short source locators and a source-to-canonical parameter-name map. Entry names and aliases help navigation; they do not distinguish mathematical objects.

Numerical specifications use `field-content-2`. Symbolic charge families use `field-content-3`, with integer parameters and polynomial constraints. The stored numerical scalar unit is `real_module`. The machine key `copies` means multiplicity.

## Code

- `catalogue.py`: strict source validation and normalized ingestion, merging exact duplicate references.
- `entry_validation.py`, `catalogue_identity.py`, `scalar_conventions.py`: numerical shape validation, normalization, real scalar counting and exact identity.
- `charge_expressions.py`, `parameterized_entry.py`, `symbolic_identity.py`: safe integer-polynomial syntax, specialization and canonical symbolic-template matching.
- `nonabelian_core.py`: derived semisimple gauge and matter restrictions and full-algebra keys.
- `prepare_entry.py`, `check_entry.py`: read-only normalization and duplicate preflight against the generated SQLite export.
- `schema.sql`: relational export tables and the `entry_layers` and `entry_identity` views.

`catalogue.schema.json` and `entry.schema.json` document structure; executable checks enforce cross-field mathematics and canonical storage. `reference_spectra.json` supplies the SM/MSSM display shorthand and never replaces the full inventory in an entry. `examples/` contains illustrative intake specifications, not accepted source models.

Run `make build` after source changes and `make check` before publication. Do not edit `FIELD_CONTENT_CATALOGUE.json` or the website downloads directly.
