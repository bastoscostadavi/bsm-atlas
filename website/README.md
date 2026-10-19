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
| `core_projection.py` | Derived semisimple parts, full gauge algebras and semisimple matter-spectrum groupings. |
| `reextraction_reviews.py`, `current_reextraction_reviews.py`, `harvest_reviews.py` | Hash-pinned source acceptance, complete-only publication, direct new-paper ingestion and exact duplicate reconciliation; mutable agent queues are never automatically published. |
| `test_*.py`, `*.test.mjs`, `check.mjs` | Current catalogue, source-integrity and frontend regression checks. |

## Generated outputs

- `field-catalogue.json`: complete published entries, supported regimes, source evidence, papers and templates; no pending records.
- `field-catalogue-data.js`: the same payload for the static interface, including local-file use.
- `../atlas/FIELD_CONTENT_CATALOGUE.json`: the same saved data for offline inspection.
- `entry.schema.json`: the published copy of the canonical input schema.
- `downloads/field-catalogue.sqlite`: focused relational export and full numerical identity registry.
- `downloads/field-catalogue.csv`: one primary-regime summary per entry.
- `downloads/nonabelian-cores.csv`, `downloads/semisimple-algebras.csv`, `downloads/full-gauge-algebras.csv`: the three coarse projections of full entries.

The header's Catalogue disclosure contains two non-clickable group labels: Gauge algebra, and Gauge algebra and matter representations. Each has two links, Semisimple part and Full; the current view is marked. It replaces the former in-page navigation grid. Contextual selections, search filters and notation survive view changes. The menu supports keyboard and touch, closes on selection, outside click or Escape, and returns focus to its trigger on Escape. The atlas introduction also links directly to all four views. Users can add Abelian factors first or matter first, rather than follow numbered steps. All views derive only from complete source-supported inventories. Incomplete sectors cannot create an algebra category. Different description regimes are not combined. A paper can have no model association.

Full-algebra keys retain canonical simple factors and Abelian rank only; generator names, charges and global forms are not part of that grouping. SQLite `full_gauge_algebras` and `entry_full_algebras` are derived caches; `entry_layers` includes both full-algebra and matter-core memberships. No source inventory or full-entry fingerprint changes when these browsing views are rebuilt.

The visible column is **Multiplicity**. Existing JSON/SQLite `copies` keys retain their meaning and compatibility. Scalar component multiplicities follow the irreducible-real-module convention; source-container counts remain provenance.

## Source review and routes

`atlas/reextraction/accepted.json` preserves the historical pilot decisions; `accepted-followup.json` and `accepted-so10.json` separately pin reviewed current candidates and evidence. The latter also pins the independent D5 mathematics review. Accepted normalized inputs must agree with the published field-content identity. Current source adapters support reviewed A-series and D5 spectra; a readable SO(10) dimension is derived from exact weights, never used to infer them. New adapters or source mappings require review; preflight alone is not a general write API.

`accepted-harvest.json` additionally pins the complete-only paper harvests and previously complete seed identities. The generic adapter accepts new paper metadata and full validated entries without an intermediate incomplete database row. Source field IDs may be null; internal catalogue row IDs never masquerade as historical source IDs. Exact numerical matches reuse an existing entry and preserve source aliases.

Symbolic families retain parameters/constraints on the same entry. SQL `entry_parameters`, `entry_constraints` and `component_charge_expressions` supply typed storage; the integer-only charge column never receives a formula. `symbolic-template-2` uses canonical `z1,z2,...` names, expanded polynomials and order-independent factor/matter identity, while retaining syntactically normalized domain constraints. Source names and old evidence fingerprints remain in provenance and identity migrations. There is no logical domain solver or general reparameterization matching. Restriction to non-Abelian matter is performed before source realification, without inventing a parameter point. See the [conventions](../atlas/FIELD_CONTENT_CONVENTIONS.md).

The `#atlas` introduction is available through **The atlas** in the main navigation. It explains the arXiv-based extraction process and public scope, without the historical seed-run details. There is no separate About-the-data page or footer link; old `#about` links show the atlas introduction.

Notation explains the stored concepts in connected prose, with examples for representation labels, chirality, multiplicity, scalar counting and charge normalization. The SM and MSSM reference tables are collapsed by default. The linked conventions document remains the implementation reference.

Shareable routes include `#atlas`, `#catalogue`, `#full-algebras?semisimple=<id>`, `#full-algebra/<id>`, `#algebra/<id>`, `#core/<id>`, `#entry/<id>`, `#sources` and `#notation`. Legacy algebra/core links retain their original meaning. Query filters and notation choices survive both paths. `fullAlgebra=<id>` can additionally restrict a core route to the intersection of both groupings.

## Historical source

The original rich extraction remains under `atlas/`, with its SQL export and design/review documents. The unused old frontend, full-snapshot exporters and duplicate website downloads were removed in the focused-catalogue cleanup. Recover them from Git history if needed; do not reintroduce them into the active deployment.
