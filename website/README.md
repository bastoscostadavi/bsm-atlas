# Static explorer

The GitHub Pages site at [davibc.com/bsm-atlas](https://davibc.com/bsm-atlas/) presents the catalogue through four views, with search, representation notation choices, paper references and downloads. It reads a self-contained payload generated from `atlas/catalogue.json`.

From the repository root, run `make build`, `make check` and `make serve`. Preview at http://127.0.0.1:8000/. Building and checking require only Python and Node.js; the published site needs no server-side runtime.

## Source and exports

`make build` runs `python3 -m bsm_atlas build`. The builder reads only `atlas/catalogue.json` and the SM/MSSM reference spectra. It validates every specification, computes identities and the four browsing views, then generates:

- `catalogue.json`: the source catalogue, identical to `atlas/catalogue.json`; the JSON download points here.
- `field-catalogue.json`: entries, references and derived presentation data; `field-catalogue-data.js` supplies the same payload to the browser without a separate fetch.
- `entry.schema.json` and `catalogue.schema.json`: published schema copies.
- `downloads/field-catalogue.sqlite`: a typed relational projection, with full exact specifications and paper links.
- `downloads/field-catalogue.csv`: one row per entry, including its exact specification as JSON.
- The three grouping CSVs: one row per semisimple algebra, full algebra or semisimple matter spectrum, with exact canonical content and linked entry IDs.

Do not hand-edit generated files. `make check` rebuilds them in memory or temporary storage and detects stale text or SQLite content. It also checks strict ingestion, normalization, identity invariances, diagram geometry and navigation.

The build updates the catalogue data and runtime script URLs in `index.html` with content hashes. A changed catalogue or renderer therefore receives a new cache key when the page is reloaded after deployment.

## Interface

`index.html`, `field-catalogue.css` and `field-catalogue.js` implement the interface. `field-matrix.js` lays out exact derived rows. In the Python package, `presentation.py` computes readable dimensions and safe SM/MSSM shorthand, and `core_projection.py` generates all four view memberships. `representation-diagrams.js` and locally vendored SVG.js draw Dynkin and eligible A-series Young diagrams.

Python implementation files and regression tests live in `bsm_atlas/` and `tests/`, outside this published directory.

The Catalogue disclosure groups four links under “Forces” and “Forces and Matter”. Each group offers Semisimple part and Full. These menu links open catalogue-wide views, clearing any algebra or matter-core selection made by drilling down. Search, problem and mechanism selections, and notation choices survive navigation. Links within the catalogue retain the selected grouping; selecting a matter core and a full gauge algebra intersects the two groupings.

Algebra lists sort by the semisimple part's total rank, then dimension, then its canonical Cartan signature (family letters and numeric ranks). Full algebras with the same semisimple part sort next by the number of u(1) factors; remaining ties use the group ID. The grouping CSVs preserve this order.

Matter cores and full entries use that algebra order, followed by the total real dimension of their Lorentz × gauge field representations, including multiplicities. Equal dimensions compare exact numeric Lorentz labels, gauge weights and charges, reality conventions and multiplicities; canonical symbolic metadata resolves remaining ties. The ordering is independent of model names and source row order. It does not change canonical factor order, representation columns or identities. See the [field-content conventions](../atlas/FIELD_CONTENT_CONVENTIONS.md#browsing-order) for counting examples and the exact tie-breaking convention.

Routes include `#catalogue`, `#full-algebras`, `#algebra/<id>`, `#full-algebra/<id>`, `#cores`, `#core/<id>` and `#entry/<id>`. `#atlas`, `#notation` and `#sources` explain the catalogue, its conventions and its bibliography. Entry details show the papers studying that specification.

Each full entry has one References toggle showing the number of linked papers. It opens the linked titles, authors and arXiv URLs in oldest-first order. Paper IDs remain internal keys, not visible labels. The paper browser and filters use the same chronological order.

The Papers page opens with an empty bibliography search. Submit a title, author or arXiv identifier, optionally narrowed by first-submission year; a year alone also works. Results appear only after searching, with 20 papers per page. Each result links to arXiv and lists direct links to its associated atlas entries under a disclosure. Search is case- and accent-insensitive. Searches and pagination can be shared through `#sources?search=...&year=...&page=...`; these controls are independent of the model catalogue filters.

Dates use the first-submission month encoded in the [arXiv identifier](https://info.arxiv.org/help/arxiv_identifier.html). Papers are ordered by month, then by sequence number within an archive; cross-archive ties use a deterministic archive order. Dates are displayed with month precision.

The website shows only complete specifications. Its dimension labels and diagrams are presentation aids; exact Dynkin labels, Lorentz irreps, multiplicities and typed charges remain the stored objects.

GitHub Actions checks the files and publishes this directory on pushes to main. Reading new arXiv papers and adding their specifications is a separate ingestion step; the website build uses the checked-in catalogue.

## Problems and mechanisms

`#problems` and `#mechanisms` are separate browsing pages. Each offers a
searchable, category-grouped list of checkboxes and a list of matching model
entries in catalogue order. Selecting several terms retains only entries linked
to every selected term. The mechanism layer includes all 31 definitions; the
problem layer retains its 13 visible definitions, omitting the established-theory
dynamics category from the original experiment.

Both pages retain rationales, short source quotations, locators and the specific
automated source-check flags. Entry details offer separate Problems and
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
`problem-data.js` and `mechanism-data.js` are generated from the frozen experiment
exports. Refresh them from local research inputs with:

```sh
python3 -B scripts/build_problem_preview.py
python3 -B scripts/build_mechanism_preview.py
make build
```

Both exporters reject changed specifications and missing paper references for
positive annotations, and omit removed catalogue entries. Each supports `--check`
for verification without rewriting its asset. Frozen experiment inputs stay
outside the published website. `make check` tests the generated assets, evidence,
multiple-selection intersections, catalogue integration, routes and controls.
`make serve` previews the site locally. GitHub Pages publishes the website through
the existing workflow; no server-side runtime is needed.
