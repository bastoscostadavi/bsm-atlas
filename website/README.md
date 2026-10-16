# BSM Atlas website

Static GitHub Pages catalogue at [davibc.com/bsm-atlas](https://davibc.com/bsm-atlas/). No DSI connection, backend or login is required.

## Current public view

The overview lists all 14 resolved recorded semisimple algebras, covering 94 primary source records independently of matter completeness. Nine unknown/parameterized algebras remain separately accessible without guessed factors. Drill down to 15 complete non-Abelian matter spectra (19 full numerical entries), with pending source records listed separately. The full-entry view defaults to complete spectra; Coverage can include all 103 records. The derived SQLite `entry_layers` view retains algebra membership even for entries with no complete matter-core key. The original source database is unchanged.

The October 16, 2026 release deliberately narrows the main interface to **BSM gauge algebras, matter multiplets and papers**. It projects the saved extraction of 50 seed papers into 103 source-scoped field-content entries. The paper list additionally contains arXiv:1905.13729 as general theory paper R01, with **zero gauge/matter associations**. Papers are independently retained even if they yield no BSM row.

Accepted scoped re-extractions now cover P01–P05, P11 and P18: ten paper/candidate occurrences reuse nine existing entries. The left–right entry is corrected in both source variants, and four SU(5) primary unified inventories are filled. Its table includes colour, exact singlet slots, three fermion families and the explicit common unit **q=3(B−L)** (scalar triplets q=6). Provenance separates printed facts, inherited SM baseline assumptions and derived charges. There are still 103 entries; corrections do not create newly discovered models. The About view reports accepted review coverage; evidence and scope live in model/paper details. Unaccepted work on the remaining papers does not alter that published count.

`reextraction_reviews.py` reads only the hash-pinned pilot decisions in `atlas/reextraction/accepted.json`; `current_reextraction_reviews.py` reads the separately pinned `accepted-followup.json`, requires already normalized complete numerical payloads and attribute evidence, checks the expected published identity, and reuses the existing entry. The current adapter preserves explicit inherited-field origins and does not combine secondary regimes. The generated SQLite adds `extraction_reviews` with normalized inputs and review JSON. Source SQLite is immutable; `legacyProjection` retains corrected prior fields and original source assertions remain unchecked. This is scoped reviewed intake for this build, not a generalized write API, symbolic-family schema or independent scientific validation. `python3 website/test_reextraction_reviews.py` tests the acceptance gate.

Search by model, algebra, representation, paper or author; filter by algebra, source and coverage; expand an entry for variants, separate description regimes, copies, scalar reality, fermion chirality, original notation and passage evidence. **The website defaults to physics dimension shorthand**, e.g. `(3,2;1)`. The database identifiers are `dynkin-gauge-1` Bourbaki/Sage finite-type Dynkin labels and exact charges: Q is `([1,0], [1]; 1)`. A visible selector offers Dimensions, Dynkin labels, Young diagrams and Compare notations. Ambiguous canonical conversions remain `?`. The notation section expands SM/MSSM baselines with both readable and exact labels.

The minimal layout uses one representation matrix per model: spacetime first, actual gauge factors next (bundled as g_SM only for direct factors), and copies last. Repeated known rows combine copies. Chiral supermultiplets become scalar and LH Weyl component rows; 4D Dirac fields become LH conjugate pairs without duplicating model entries. Baselines, filters, downloads and technical provenance expand on demand. Catalogue, Papers, Notation and About are separate views.

The SM/MSSM reference tables likewise show Spacetime, g_SM and Copies, without a redundant Type column. Scalar `complex` annotations are omitted when a known nonzero Abelian charge already requires a complex multiplet. Neutral/unknown assignments retain their reality annotations until the separate real-scalar counting migration; no stored reality condition, multiplicity or signature changes in this presentation edit.

`spacetime_conventions.py` defines dimension-aware Lorentz labels and the all-LH 4D convention. `field-matrix.js` renders the matrices. `atlas/entry.schema.json`, `catalogue_identity.py` and `check_entry.py` provide complete-entry validation and read-only duplicate checks. The generated SQLite contains Lorentz components and a unique signature registry; incomplete records never imply that a new candidate is absent. See the conventions document for mathematical limits and editorial dimension interpretations.

The extraction agent must establish source assignments before adding them, then run `atlas/prepare_entry.py` to emit an explicitly normalized numerical candidate and conversion report. The generator normalizes complete identity inputs before persistence. This preflight is read-only and does not replace paper inspection or enforce arbitrary external SQLite writes. Unfinished extraction stays in staging; genuine source omissions and paper-defined free parameters require separate partial/family records, not guessed numerical values. The legacy catalogue still needs source-backed reconciliation of its existing gaps.

Partial and parameterized inventories remain visible and are not complete machine-ready spectra. “Recorded inventory” means the converted, scoped inventory is recorded—not that the full theory, anomalies, viability or paper extraction has been independently verified. Missing colour singlets, family counts and unselected sectors are not filled by assumption. All original assertions remain unchecked; P21/P22/P26 have partial source profiles.

Only explicit presentation groupings merge variants with the same stated field content; interaction choices do not establish full theory equivalence. General convention/theory/tool references, operator-only SM inventories and uninstantiated frameworks do not become main catalogue rows. Original excluded structural records are preserved in JSON `referenceRecords`, not linked to new model rows.

See [field-content conventions and schema](../atlas/FIELD_CONTENT_CONVENTIONS.md).

## Files and regeneration

- `index.html`, `field-catalogue.css`, `field-catalogue.js`: buildless interface.
- `representation-diagrams.js`: finite-type gauge-algebra Dynkin graphs and safe A-series Young diagrams. `vendor/svgjs/` contains pinned SVG.js 3.2.8 and its MIT license; no CDN is used. The package renders geometry, not representation-theory calculations. Dynkin graphs describe algebras; Young diagrams describe eligible irreps. Unknown/parameterized factors are not guessed.
- `field_conventions.py`, `build_field_catalogue.py`: exact, conservative, read-only projection.
- `../atlas/field_content_curations.json`: explicit grouping, baseline, exclusion and reference-paper decisions.
- `field-catalogue.json`, `field-catalogue-data.js`: generated payload; JSON is also saved in `atlas/FIELD_CONTENT_CATALOGUE.json`.
- `downloads/field-catalogue.csv`: one summary row per entry.
- `representationConvention` in JSON/SQLite metadata documents the gauge node numbering. `dynkinRepresentation` is a formatted display; structured Dynkin lists/charges remain the identity data. Legacy `representation` strings retain dimensional shorthand; CSV summaries now use Dynkin tuples. This notation-only release does not change scalar copy counting or fingerprints.
- `downloads/field-catalogue.sqlite`: entries, all papers, associations, separate regimes and recorded multiplets. It is separate from the authoritative database.
- `data.js`, `atlas-data.json`, `downloads/atlas.sqlite`, SQL and original reports remain preserved from the full October 15 export. They are not loaded by the simplified home page. Old `app.js`, `catalog.js` and `search.js` are retained supporting source, not the current UI.

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 website/build_field_catalogue.py
python3 website/build_field_catalogue.py --check
PYTHONDONTWRITEBYTECODE=1 python3 website/test_field_catalogue.py
PYTHONDONTWRITEBYTECODE=1 python3 website/test_identity.py
node website/field-catalogue.test.mjs
node website/representation-diagrams.test.mjs
python3 -m http.server 8000 --bind 127.0.0.1 --directory website
```

Open http://127.0.0.1:8000/. Hash routes work under the GitHub Pages project path: `#entry/real-singlet-z2`, `#catalogue?paper=R01`, `#catalogue?notation=compare`, `#notation`, `#sources`. Nondefault notation choices are included in shareable hash URLs. Filtering to a reference-only paper returns zero model entries by design; its paper record remains in the paper list.

The generator never changes `atlas/atlas.sqlite`. The source checksum is checked by regression tests. Before accepting a new extraction, review the curation file and regenerate both this projection and the original relational export if the authoritative snapshot changes.

GitHub Actions checks generated files, reference-only separation, exact normalization, field types, source-ID coverage, SQLite/JSON roundtrips, old snapshot integrity and source assets, then publishes `website/` on `main`. It does not validate physics or contact DSI.

## Original full export

The original 34-table snapshot retains all 50 profiles and summaries, 125 source model specifications, 573 source field rows, 233 paper-model links, 1,812 assertions and 2,378 evidence references. Its retrieval and limitations are recorded in `atlas/source_snapshot.json` and `atlas/REVIEW.md`. The source-generated ATLAS.md and PAPERS.md were unavailable; no PDFs are published.

To refresh that lossless export separately, use `python3 website/export_atlas.py /path/to/atlas.sqlite` and `python3 website/build_manifest.py`. Existing `check.mjs`, `search.test.mjs`, `catalog.test.mjs`, `test_export_atlas.py` and `test_snapshot.py` continue to validate the preserved extraction layer.
