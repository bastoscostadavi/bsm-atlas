# BSM Atlas website

Static, source-backed explorer for the atlas, published at https://davibc.com/bsm-atlas/.

The site uses plain HTML, CSS, and JavaScript; there are no runtime dependencies, login requirements, or connections to the DSI cluster. GitHub Actions deploys only this directory after a change on `main`.

## Local preview

From this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://127.0.0.1:8000/. The relative asset URLs and hash routes also work under a GitHub Pages project path. Individual models and sections have shareable URLs.

## Alignment with the atlas requirements

- **Models:** compact physics cards, scopes, source contributions and a warning when the legacy export omitted component-to-regime IDs. A refreshed export adds original rows, original notation, all IDs and detailed assertion/evidence navigation.
- **Papers:** an independent corpus catalogue, including P47 and other methods/tool sources without requiring physical-model links. `manifest.js` is generated from the authoritative `BSM_ATLAS_SEED.md`; its bibliography and planned scope are explicitly not extraction results. Paper pages distinguish authors' abstracts, generated summary revisions, inspected scope, limitations, run/review metadata, contributions and assertions when exported.
- **Database:** exact column lists plus, with a full export, searchable/paginated rows, original NULL values, stable primary-key links, declared (including composite) foreign-key navigation and original CREATE TABLE statements. Conceptual descriptions never substitute for SQL constraints.
- **Compare:** recorded definitions side by side, including interactions, symmetry actions, assumptions and source conventions. Includes left-right parity versus charge conjugation, and general versus Z3 NMSSM examples. Not an equivalence/viability test.
- **Coverage:** source registration, profiles, summaries, specifications, contributions and review are separate. Missing publication data is labelled "not exported", not zero or "not present in the database". Available validation and atlas reports are shown without a physics-validation claim.

Routes include `#paper/P47`, `#review`, `#compare`, and `#schema/theory_interactions`. Primary-key row links retain original IDs and revisions. All text from the database and reports is HTML-escaped; reports are displayed as source text, not executable HTML.

`queries.sql` provides read-only recipes for gauge-group paper associations, inspection/review coverage and operator comparisons. Definitions are tested for SQL syntax with the synthetic fixture, not presented as executed DSI results.

## Gauge-group literature search

The Sources view searches papers through their recorded theory associations. It offers group-label text search, exact stored group labels, and exact factors recovered from separately recorded gauge-factor rows. It displays matching theory records, exact contribution roles, source scope and reconciliation state. Paper IDs are deduplicated even when several models or contributions match.

Role categories group the stored role labels; they can overlap and do not certify originality or scientific review. Exact group/factor searches preserve case and suffix conventions. They do not infer mathematical equivalence, aliases, embeddings or absent factor data. Factor rows were retained as a joined string in the initial snapshot; all 65 rows can be recovered with its separator. Results are limited by the snapshot's extraction coverage.

A refreshed export also carries a separate factor-label array in `model.g[][5]`; exact-factor matching uses those original labels instead of parsing a display expression. Legacy snapshots retain the documented separator fallback.

Searches have shareable URLs, for example https://davibc.com/bsm-atlas/#papers?gauge=SU%285%29.

## Snapshot

The initial `data.js` preserves the records recovered from the DSI database on October 7, 2026: 125 theory specifications, 49 papers with model provenance, and metadata for 34 tables. The complete corpus had 50 papers. Exact columns were retained for 19 tables. Schema connections in the interface are explicitly conceptual, not verified SQL foreign keys.

That snapshot is still the published scientific dataset until cluster access is restored. Adding a paper catalogue from the seed does **not** recover the omitted database profiles or certify that all planned scopes were extracted. The new full-data UI is tested with synthetic records, which are never included in the public dataset.

Representation tuples, signs and charge normalizations retain source conventions. Missing values are displayed as missing; SQL NULL in inclusion/permission flags is not converted to false. Scientific reconciliation may be provisional.

## Refresh from the database

Copy this directory to a machine that can read the atlas, then run:

```sh
python3 export_atlas.py /data/bsm-atlas/atlas/atlas.sqlite
python3 build_manifest.py
node --check app.js
node --check data.js
node --check catalog.js
node check.mjs
node search.test.mjs
node catalog.test.mjs
python3 test_export_atlas.py
```

The exporter opens SQLite read-only and holds a consistent read transaction. It refreshes the compact model cards **and every row and column from every non-internal database table**, preserving SQL NULL, source/version/model/regime IDs and all specification revisions. SQL types, primary keys, declared foreign keys and CREATE TABLE definitions are included. Scientific strings and source conventions are never normalized into guessed values.

It also generates `atlas-data.json`, `downloads/atlas.sqlite`, `downloads/atlas.sql`, and copies ATLAS.md/PAPERS.md/SCHEMA.md/REVIEW.md from the database's directory when present. It checks SQLite integrity, foreign-key violations and exact row-value reconstruction from the SQL export; these are data checks, not an independent physics review. Download sizes and SHA-256 checksums are recorded. No PDFs are published. Use `--no-database-downloads` to omit the SQLite/SQL copies while retaining the relational JSON and available reports.

Review the exported content, scientific limitations and download files before pushing to `main`. Potential credential-named columns cause the export to stop. Updating SQLite alone does not update the published website. CI runs the source, manifest, search, catalogue and synthetic exporter checks; it cannot contact DSI or validate source claims.

`data.js` uses compact arrays. Their field order is documented by the column lists in `export_atlas.py`. `schema.info` and `schema.groups` are editorial descriptions of the relational model and should be reviewed when the database schema changes.

The complete relational layer is `data.relational.tables[tableName]`, with `columns`, `foreignKeys`, `sql` and object-valued `rows`. `export_relational.py` implements that lossless layer. Unknown added tables receive an explicit "description not provided" label rather than an invented scientific interpretation. Seed changes require regenerating `manifest.js`; `python3 build_manifest.py --check` detects stale output.
