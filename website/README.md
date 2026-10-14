# BSM Atlas website

Static explorer for the atlas, published at https://davibc.com/bsm-atlas/.

The site uses plain HTML, CSS, and JavaScript; there are no runtime dependencies, login requirements, or connections to the DSI cluster. GitHub Actions deploys only this directory after a change on `main`.

## Local preview

From this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://127.0.0.1:8000/. The relative asset URLs and hash routes also work under a GitHub Pages project path. Individual models and sections have shareable URLs.

## Gauge-group literature search

The Sources view searches papers through their recorded theory associations. It offers group-label text search, exact stored group labels, and exact factors recovered from separately recorded gauge-factor rows. It displays matching theory records, exact contribution roles, source scope and reconciliation state. Paper IDs are deduplicated even when several models or contributions match.

Role categories group the stored role labels; they can overlap and do not certify originality or scientific review. Exact group/factor searches preserve case and suffix conventions. They do not infer mathematical equivalence, aliases, embeddings or absent factor data. Factor rows were retained as a joined string in the initial snapshot; all 65 rows can be recovered with its separator. Results are limited by the snapshot's extraction coverage.

Searches have shareable URLs, for example https://davibc.com/bsm-atlas/#papers?gauge=SU%285%29.

## Snapshot

The initial `data.js` preserves the records recovered from the DSI database on October 7, 2026: 125 theory specifications, 49 papers with model provenance, and metadata for 34 tables. The complete corpus had 50 papers. Exact columns were retained for 19 tables. Schema connections in the interface are explicitly conceptual, not verified SQL foreign keys.

Representation tuples, signs and charge normalizations retain source conventions. Missing values are displayed as missing; SQL NULL in inclusion/permission flags is not converted to false. Scientific reconciliation may be provisional.

## Refresh from the database

Copy this directory to a machine that can read the atlas, then run:

```sh
python3 export_atlas.py /data/bsm-atlas/atlas/atlas.sqlite
node --check app.js
node --check data.js
node check.mjs
node search.test.mjs
```

The exporter opens SQLite read-only and refreshes the model data and complete column lists. It does not modify the database. Review changes and update the date and coverage labels in the interface before pushing to `main`. Updating SQLite alone does not update the published website.

`data.js` uses compact arrays. Their field order is documented by the column lists in `export_atlas.py`. `schema.info` and `schema.groups` are editorial descriptions of the relational model and should be reviewed when the database schema changes.
