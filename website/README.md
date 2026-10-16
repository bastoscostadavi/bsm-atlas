# BSM Atlas website

Static GitHub Pages catalogue at [davibc.com/bsm-atlas](https://davibc.com/bsm-atlas/). No DSI connection, backend or login is required.

## Current public view

The October 16, 2026 release deliberately narrows the main interface to **BSM gauge algebras, matter multiplets and papers**. It projects the saved extraction of 50 seed papers into 103 source-scoped field-content entries. The paper list additionally contains arXiv:1905.13729 as general theory paper R01, with **zero gauge/matter associations**. Papers are independently retained even if they yield no BSM row.

Search by model, algebra, representation, paper or author; filter by algebra, source and coverage; expand an entry for variants, separate description regimes, copies, scalar reality, fermion chirality, original notation and passage evidence. Representations can be displayed using dimensions, safe Dynkin conversions or A-series Young diagrams. The notation section expands the SM and MSSM baselines.

The minimal layout uses one representation matrix per model: spacetime first, actual gauge factors next (bundled as g_SM only for direct factors), and copies last. Repeated known rows combine copies. Chiral supermultiplets become scalar and LH Weyl component rows; 4D Dirac fields become LH conjugate pairs without duplicating model entries. Baselines, filters, downloads and technical provenance expand on demand. Catalogue, Papers, Notation and About are separate views.

`spacetime_conventions.py` defines dimension-aware Lorentz labels and the all-LH 4D convention. `field-matrix.js` renders the matrices. `atlas/entry.schema.json`, `catalogue_identity.py` and `check_entry.py` provide complete-entry validation and read-only duplicate checks. The generated SQLite contains Lorentz components and a unique signature registry; incomplete records never imply that a new candidate is absent. See the conventions document for mathematical limits and editorial dimension interpretations.

Partial and parameterized inventories remain visible and are not complete machine-ready spectra. “Recorded inventory” means the converted, scoped inventory is recorded—not that the full theory, anomalies, viability or paper extraction has been independently verified. Missing colour singlets, family counts and unselected sectors are not filled by assumption. All original assertions remain unchecked; P21/P22/P26 have partial source profiles.

Only explicit presentation groupings merge variants with the same stated field content; interaction choices do not establish full theory equivalence. General convention/theory/tool references, operator-only SM inventories and uninstantiated frameworks do not become main catalogue rows. Original excluded structural records are preserved in JSON `referenceRecords`, not linked to new model rows.

See [field-content conventions and schema](../atlas/FIELD_CONTENT_CONVENTIONS.md).

## Files and regeneration

- `index.html`, `field-catalogue.css`, `field-catalogue.js`: buildless interface.
- `field_conventions.py`, `build_field_catalogue.py`: exact, conservative, read-only projection.
- `../atlas/field_content_curations.json`: explicit grouping, baseline, exclusion and reference-paper decisions.
- `field-catalogue.json`, `field-catalogue-data.js`: generated payload; JSON is also saved in `atlas/FIELD_CONTENT_CATALOGUE.json`.
- `downloads/field-catalogue.csv`: one summary row per entry.
- `downloads/field-catalogue.sqlite`: entries, all papers, associations, separate regimes and recorded multiplets. It is separate from the authoritative database.
- `data.js`, `atlas-data.json`, `downloads/atlas.sqlite`, SQL and original reports remain preserved from the full October 15 export. They are not loaded by the simplified home page. Old `app.js`, `catalog.js` and `search.js` are retained supporting source, not the current UI.

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 website/build_field_catalogue.py
python3 website/build_field_catalogue.py --check
PYTHONDONTWRITEBYTECODE=1 python3 website/test_field_catalogue.py
PYTHONDONTWRITEBYTECODE=1 python3 website/test_identity.py
node website/field-catalogue.test.mjs
python3 -m http.server 8000 --bind 127.0.0.1 --directory website
```

Open http://127.0.0.1:8000/. Hash routes work under the GitHub Pages project path: `#entry/real-singlet-z2`, `#catalogue?paper=R01`, `#notation`, `#sources`. Filtering to a reference-only paper returns zero model entries by design; its paper record remains in the paper list.

The generator never changes `atlas/atlas.sqlite`. The source checksum is checked by regression tests. Before accepting a new extraction, review the curation file and regenerate both this projection and the original relational export if the authoritative snapshot changes.

GitHub Actions checks generated files, reference-only separation, exact normalization, field types, source-ID coverage, SQLite/JSON roundtrips, old snapshot integrity and source assets, then publishes `website/` on `main`. It does not validate physics or contact DSI.

## Original full export

The original 34-table snapshot retains all 50 profiles and summaries, 125 source model specifications, 573 source field rows, 233 paper-model links, 1,812 assertions and 2,378 evidence references. Its retrieval and limitations are recorded in `atlas/source_snapshot.json` and `atlas/REVIEW.md`. The source-generated ATLAS.md and PAPERS.md were unavailable; no PDFs are published.

To refresh that lossless export separately, use `python3 website/export_atlas.py /path/to/atlas.sqlite` and `python3 website/build_manifest.py`. Existing `check.mjs`, `search.test.mjs`, `catalog.test.mjs`, `test_export_atlas.py` and `test_snapshot.py` continue to validate the preserved extraction layer.
