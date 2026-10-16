# Catalogue website

Static GitHub Pages explorer at [davibc.com/bsm-atlas](https://davibc.com/bsm-atlas/). It needs no backend, DSI connection or login.

## Build, check and preview

From the repository root:

```sh
make build
make check
make serve
```

The equivalent commands are `python3 website/build_field_catalogue.py`, `python3 scripts/check.py` and `python3 -m http.server 8000 --bind 127.0.0.1 --directory website`. Preview at http://127.0.0.1:8000/.

The build reads the immutable source snapshot, explicit curations and accepted re-extractions. It never modifies `atlas/atlas.sqlite`. Do not hand-edit generated JSON, CSV or SQLite files. `make check` detects stale generated text, tests SQLite/JSON agreement and normalization, verifies frozen evidence and the original snapshot, and checks the active frontend assets.

GitHub Actions runs the same checks and publishes `website/` on `main`.

## Active files

| Files | Responsibility |
|---|---|
| `index.html`, `field-catalogue.css`, `field-catalogue.js` | Buildless interface, search, filters, navigation, notation and provenance. |
| `field-matrix.js` | Representation matrices and aggregation of identical resolved rows. |
| `representation-diagrams.js`, `vendor/svgjs/` | Local Dynkin and eligible A-series Young diagrams; vendored dependency and license. |
| `build_field_catalogue.py` | Read-only source projection and reproducible exports. |
| `field_conventions.py`, `spacetime_conventions.py`, `scalar_projection.py` | Exact representation, Lorentz and scalar-counting conversions. |
| `core_projection.py` | Derived non-Abelian algebra and matter-spectrum groupings. |
| `reextraction_reviews.py`, `current_reextraction_reviews.py` | Explicit hash-pinned acceptance gates; mutable agent queues are not ingested automatically. |
| `test_*.py`, `*.test.mjs`, `check.mjs` | Current catalogue, source-integrity and frontend regression checks. |

## Generated outputs

- `field-catalogue.json`: downloadable catalogue, including pending records, separate regimes, evidence, papers and templates.
- `field-catalogue-data.js`: the same payload for the static interface, including local-file use.
- `../atlas/FIELD_CONTENT_CATALOGUE.json`: the same saved data for offline inspection.
- `entry.schema.json`: the published copy of the canonical input schema.
- `downloads/field-catalogue.sqlite`: focused relational export and full numerical identity registry.
- `downloads/field-catalogue.csv`: one primary-regime summary per entry.
- `downloads/nonabelian-cores.csv`, `downloads/semisimple-algebras.csv`: the two derived browsing layers.

Algebra membership does not require complete matter. Matter-spectrum keys do: pending inventories are listed separately, never promoted by deleting unknown fields. An empty factor list is unknown, not the zero semisimple algebra. Different description regimes are not combined.

The visible column is **Multiplicity**. Existing JSON/SQLite `copies` keys retain their meaning and compatibility. Scalar component multiplicities follow the irreducible-real-module convention; source-container counts remain provenance.

## Source review and routes

`atlas/reextraction/accepted.json` preserves the historical pilot decisions; `accepted-followup.json` and `accepted-so10.json` separately pin reviewed current candidates and evidence. The latter also pins the independent D5 mathematics review. Accepted normalized inputs must agree with the published field-content identity. Current source adapters support reviewed A-series and D5 spectra; a readable SO(10) dimension is derived from exact weights, never used to infer them. New adapters or source mappings require review; preflight alone is not a general write API.

The full-entry view defaults to complete numerical spectra. Coverage also exposes pending records. Symbolic-family input validation exists, but automatic public-family ingestion does not. These limits and the current counts are documented in the [main README](../README.md) and [conventions](../atlas/FIELD_CONTENT_CONVENTIONS.md).

Shareable routes include `#catalogue`, `#algebra/<id>`, `#core/<id>`, `#entry/<id>`, `#sources`, `#notation` and `#about`. Query filters and notation choices are retained through drill-down.

## Historical source

The original rich extraction remains under `atlas/`, with its SQL export and design/review documents. The unused old frontend, full-snapshot exporters and duplicate website downloads were removed in the focused-catalogue cleanup. Recover them from Git history if needed; do not reintroduce them into the active deployment.
