# Static explorer

The [BSM Atlas](https://davibc.com/bsm-atlas/) is a static GitHub Pages site. Its four catalogue views share a compact index of model names, aliases, algebra memberships and reference counts. Field tables, bibliography records and evidence are separate content-addressed chunks. No database server is needed.

Run `make build`, `make check` and `make serve` from the repository root. A fresh clone first restores the source files pinned in `atlas/snapshot.json`. Existing working files are never overwritten. Python 3.12+ and Node.js 18+ suffice.

## Loading and search

`atlas-bootstrap.js` names one immutable manifest. `atlas-store.js` loads that manifest and the catalogue and annotation membership indexes. The initial request does not fetch full model specifications, paper titles/authors, evidence, or the bulk database.

Model tables load for the visible entries. References and bibliography results load 20 records per page. Opening a problem or mechanism disclosure loads just its requested evidence page and the corresponding paper metadata. Closing a disclosure does not discard its cached page. Counts and membership intersections remain available without fetching quotations.

The semisimple Forces and Matter view loads tables for its visible matter
spectra from separate core records. These tables retain Lorentz representations,
non-Abelian representations and multiplicities, with u(1) factors omitted.
Each card includes an Open entries link; model-name lists stay hidden.

Search uses precomputed word-prefix posting lists, including model specifications and linked bibliography. Queries intersect their postings rather than scanning every paper for each model. Search runs in a lazily started Web Worker; browsers without Workers use the same indexes on the main thread. Caches bound decoded chunks, model bodies, paper records, evidence pages and query results. Outdated asynchronous results never replace the current view.

Every data URL includes a content hash. An open tab stays on one snapshot, including during publication. If an old chunk is no longer available, the interface asks the visitor to reload and retains the route in the URL. Network failures have retry controls.

## Builds, downloads and publication

`make build` generates static chunks under `website/data/`, a small bootstrap, schemas, and complete JSON/CSV/SQLite research exports. Generated data, bulk exports and working data stores are ignored by Git. Research exports remain available locally for analysis and regression checks, but are excluded from the public site package.

The source JSON and new paper–model annotations are gzip-compressed Release assets pinned by `atlas/snapshot.json`, with compressed and uncompressed hashes and lengths. Complete JSON, CSV and SQLite downloads are also Release assets. Browser download links point to the same immutable publication used to build the site; they do not change with search filters.

To publish while ingestion continues:

```sh
python3 -B scripts/data_snapshot.py prepare --freeze --terra-reviewed-luna --upload
# Commit and push atlas/snapshot.json.
```

The command archives committed code, briefly locks and copies both working data files, then builds and checks the isolated copy. Ingestion continues on its original files. Assets are uploaded to a draft release before publication; uploads can be resumed with `scripts/data_snapshot.py upload`. Existing published assets are reused rather than overwritten.

`--terra-reviewed-luna` also freezes the local review registry and excludes
Luna-origin model references without a completed Terra inventory result. Terra
corrections qualify while awaiting Sol. Entries with independent support from
other extractors remain eligible; entries left without an eligible reference
are omitted. Luna annotations retain their inventory bindings. The selection
report remains alongside the prepared assets; the live ingestion stores are
preserved. Omit the flag only for an explicitly unfiltered publication.

GitHub Actions restores and verifies those exact sources, builds, runs the checks and packages only the runtime assets, schemas, vendored diagrams and static chunks into `.build/site`. Bulk research exports, worker receipts, prompts and paper text do not enter the Pages artifact. `scripts/package_site.py` rejects a package whose source hash differs from the pinned snapshot.

The [synthetic scale test](../benchmarks/README.md) exercises 100,000 papers, a large catalogue, and a model with thousands of references. It tests delivery and indexing; it does not measure scientific extraction quality or browser rendering speed.

## Interface

The visible “Matter representation notation” label identifies the selector for
dimensions, Dynkin labels, Young diagrams and comparison mode. “Download”
opens complete dataset downloads: CSV for all groups or entries in the current
view, plus the full catalogue in JSON or SQLite. Search and filter selections
are not applied to these files; problem and mechanism annotations are excluded.

`index.html`, `field-catalogue.css` and `field-catalogue.js` implement the interface. `field-matrix.js` lays out exact derived rows. In the Python package, `presentation.py` computes readable dimensions and safe SM/MSSM shorthand, and `core_projection.py` generates all four view memberships. `representation-diagrams.js` and locally vendored SVG.js draw Dynkin and eligible A-series Young diagrams.

SM/MSSM shorthand matches the complete reference field content and the three
gauge-factor types, independently of source-specific factor names. Matching
entries initially show the baseline plus additional fields; the baseline can
be expanded to show every row. Exact charges and multiplicities must match.

Python implementation files and regression tests live in `bsm_atlas/` and `tests/`, outside this published directory.

The main navigation has two direct catalogue links: **Forces** opens all full
gauge algebras (`#full-algebras`), and **Forces and Matter** opens full entries
(`#entries`). The home link also opens full gauge algebras. **Semisimple part
only** switches either page to its semisimple projection, omitting u(1) factors.
Search, problem/mechanism selections, notation and any current grouping survive
the toggle. The two main links always reopen their complete full view, clearing
drill-down grouping while retaining search and annotation filters. Old
`#catalogue` and `#cores` URLs continue to open semisimple views.

Algebra lists sort by the semisimple part's total rank, then dimension, then its canonical Cartan signature (family letters and numeric ranks). Full algebras with the same semisimple part sort next by the number of u(1) factors; remaining ties use the group ID. The grouping CSVs preserve this order.

Matter cores and full entries use that algebra order, followed by the total real dimension of their Lorentz × gauge field representations, including multiplicities. Equal dimensions compare exact numeric Lorentz labels, gauge weights and charges, reality conventions and multiplicities; canonical symbolic metadata resolves remaining ties. The ordering is independent of model names and source row order. It does not change canonical factor order, representation columns or identities. See the [field-content conventions](../atlas/FIELD_CONTENT_CONVENTIONS.md#browsing-order) for counting examples and the exact tie-breaking convention.

Routes include `#catalogue`, `#full-algebras`, `#algebra/<id>`, `#full-algebra/<id>`, `#cores`, `#core/<id>` and `#entry/<id>`. `#atlas`, `#notation` and `#sources` explain the catalogue, its conventions and its bibliography. Entry details show the papers studying that specification.

A direct entry link loads the first visible model page and the selected entry, without loading every intervening model.

Each full entry has one References toggle showing the number of linked papers. It opens the linked titles, authors and arXiv URLs in oldest-first order, 20 references per page. Paper IDs remain internal keys, not visible labels. The paper browser and filters use the same chronological order.

The Papers page opens with an empty bibliography search. Submit a title, author or arXiv identifier, optionally narrowed by first-submission year; a year alone also works. Results appear only after searching, with 20 papers per page, fetched independently of the rest of the bibliography. Each result links to arXiv and lists direct links to its associated atlas entries under a disclosure. Search words are case- and accent-insensitive prefixes; multiple words are intersected. Model searches also index their linked bibliography. Explicit algebra expressions such as `su(5)` select matching recorded factors. Searches and pagination can be shared through `#sources?search=...&year=...&page=...`; these controls are independent of the model catalogue filters.

Dates use the first-submission month encoded in the [arXiv identifier](https://info.arxiv.org/help/arxiv_identifier.html). Papers are ordered by month, then by sequence number within an archive; cross-archive ties use a deterministic archive order. Dates are displayed with month precision.

The website shows only complete specifications. Its dimension labels and diagrams are presentation aids; exact Dynkin labels, Lorentz irreps, multiplicities and typed charges remain the stored objects.

GitHub Actions restores the pinned input snapshot, builds and checks all exports, and publishes the package from `.build/site`. Reading new arXiv papers and adding their specifications is a separate ingestion step. A local ingestion update does not change the public snapshot until a new data release and descriptor are published.

## Problems and mechanisms

`#problems` and `#mechanisms` are separate browsing pages. Each offers a
searchable, category-grouped list of checkboxes and a list of matching model
entries in catalogue order. Selecting several terms retains only entries linked
to every selected term. The mechanism layer includes all 31 definitions; the
problem layer retains its 13 visible definitions, omitting the established-theory
dynamics category from the original experiment.

Both pages retain rationales, short source quotations, locators and the specific
automated source-check flags. Evidence is fetched only when its disclosure is opened,
and is paginated by at most 20 associations and a target byte budget per page. Entry details offer separate Problems and
Mechanisms buttons. An unassessed entry is distinguished from an assessed entry
with no detected positive links. `#entry/<id>?panel=mechanisms` opens the mechanism
evidence directly; the existing Problems panel and old single-problem URLs remain
supported. `#problems?about=layer` explains both annotation layers.

The Catalogue's **Filters** disclosure includes Problems and Mechanisms pickers.
All selections are intersected with each other and with the catalogue search
and the selected algebra or matter grouping. Every catalogue view uses the same
filtered entries: algebra and matter-core groups appear only when they contain a
matching entry. Selections survive drill-down, catalogue menu navigation and
shareable URLs, using repeated `problem` and `mechanism` parameters. For example:

```text
#entries?problem=dark_matter&mechanism=thermal_freeze_out&mechanism=coannihilation
```

Only positive `addresses` (problem) and `implements` (mechanism) decisions create
links. Absence, ambiguous decisions and failed processing create no links. Matching
several selections is an entry-level intersection across papers; it does not imply
the connections are realized together in the same paper or parameter choice.
All classifications remain machine-extracted and provisional. Review flags are
preserved, including those affecting model identification. Passing the automated
checks does not verify the scientific interpretation.

These layers are separate from the structural catalogue and its downloads.
Luna associations retain their canonical inventory bindings when Terra reviews
the model entries. Claims for replaced or withdrawn inventories are retained
in `detached_models` in the literature store; the public layer includes claims
with a matching current inventory and paper reference.
The local research exports `problem-data.js` and `mechanism-data.js` are generated from the compact published
baseline in `atlas/literature_baseline.json` and new paper-specific associations
in `atlas/literature_links.json`. Neither paper text nor raw extraction responses
are needed to reproduce these assets. The public site receives only their small
membership/count indexes and demand-loaded evidence pages. Refresh all website data with `make build`,
or rebuild the annotations separately with:

```sh
python3 -B scripts/build_problem_preview.py
python3 -B scripts/build_mechanism_preview.py
make build
```

Both exporters reject changed baseline specifications and missing paper references
for positive annotations, and omit removed catalogue entries. Each supports
`--check` for verification without rewriting its asset. `make check` verifies
that both assets match their compact inputs and tests evidence,
multiple-selection intersections, catalogue integration, routes and controls.
`make serve` previews the site locally. GitHub Pages publishes the website through
the existing workflow; no server-side runtime is needed.
