# Catalogue data

[Catalogue source](catalogue.json) · [Conventions](FIELD_CONTENT_CONVENTIONS.md) · [Ingestion instructions](../BSM_ATLAS_AGENT_PROMPT.md)

The authoritative source has two lists: `papers` and `entries`. An entry contains a complete `specification` and its `references`. References may include short source locators and a source-to-canonical parameter-name map. Entry names and aliases help navigation; they do not distinguish mathematical objects.

Numerical specifications use `field-content-2`. Symbolic charge families use `field-content-3`, with integer parameters and polynomial constraints. The stored numerical scalar unit is `real_module`. The machine key `copies` means multiplicity.

Each representation row has exactly four fields: `lorentz`, `reality`, `copies` and `gauge_representations`. Free-text field labels, symbols and other annotations are rejected. Model names and paper metadata are stored separately from the mathematical specification; readable representation notation is computed for display.

## Schemas and reference data

`catalogue.schema.json` and `entry.schema.json` document structure; executable checks enforce cross-field mathematics and canonical storage. `reference_spectra.json` supplies the SM/MSSM display shorthand and never replaces the full inventory in an entry. `examples/` contains illustrative intake specifications, not accepted source models.

`schema.sql` defines the relational export tables and the `entry_layers` and `entry_identity` views. The [Python package](../bsm_atlas/) implements validation, normalization, exact identities and the derived catalogue views; [tests](../tests/) check those conventions independently of the data files.

From the repository root, use `python3 -m bsm_atlas add candidate.json` for a dry run and add `--write` to save a validated entry or merge its references. The same command provides `prepare` for read-only normalization, `lookup` for duplicate preflight against the built SQLite export, and `validate` for checking the authoritative source.

Run `make build` after source changes and `make check` before publication. Do not edit generated website data or downloads directly.
