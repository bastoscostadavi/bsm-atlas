# Static explorer

The GitHub Pages site at [davibc.com/bsm-atlas](https://davibc.com/bsm-atlas/) presents the catalogue through four views, with search, representation notation choices, paper references and downloads. It reads a self-contained payload generated from `atlas/catalogue.json`.

From the repository root, run `make build`, `make check` and `make serve`. Preview at http://127.0.0.1:8000/. Python and Node are the only runtime dependencies.

## Source and exports

`build_field_catalogue.py` reads only `atlas/catalogue.json` and the SM/MSSM reference spectra. It validates every specification, computes identities and the four browsing views, then generates:

- `catalogue.json`: the source catalogue, identical to `atlas/catalogue.json`; the JSON download points here.
- `field-catalogue.json`, `field-catalogue-data.js` and `../atlas/FIELD_CONTENT_CATALOGUE.json`: the same entries, references and derived presentation data.
- `entry.schema.json` and `catalogue.schema.json`: published schema copies.
- `downloads/field-catalogue.sqlite`: a typed relational projection, with full exact specifications, paper links, problem definitions and demonstrated results.
- `downloads/field-catalogue.csv`: one row per entry, including its exact specification as JSON.
- The three grouping CSVs: one row per semisimple algebra, full algebra or semisimple matter spectrum, with exact canonical content and linked entry IDs.
- `downloads/problems.csv` and `downloads/entry-problems.csv`: controlled targets and source-demonstrated model–problem–paper links, including results and locations. The entry CSV also gives distinct problem IDs.

Do not hand-edit generated files. `make check` rebuilds them in memory or temporary storage and detects stale text or SQLite content. It also checks strict ingestion, normalization, identity invariances, diagram geometry and navigation.

## Interface

`index.html`, `field-catalogue.css` and `field-catalogue.js` implement the interface. `field-matrix.js` lays out exact derived rows; `presentation.py` computes readable dimensions and safe SM/MSSM shorthand. `core_projection.py` generates all four view memberships. `representation-diagrams.js` and locally vendored SVG.js draw Dynkin and eligible A-series Young diagrams.

The Catalogue disclosure groups four links under Gauge algebra and Gauge algebra and matter representations. Each group offers Semisimple part and Full. These menu links open catalogue-wide views, clearing any algebra or matter-core selection made by drilling down. Search, paper filters, Abelian rank and notation selections survive navigation. Links within the catalogue retain the selected grouping; selecting a matter core and a full gauge algebra intersects the two groupings.

Routes include `#catalogue`, `#full-algebras`, `#algebra/<id>`, `#full-algebra/<id>`, `#cores`, `#core/<id>` and `#entry/<id>`. `#atlas`, `#notation` and `#sources` explain the catalogue, its conventions and its bibliography. Entry details show the papers studying that specification.

`#problems` separates Empirical problems, Structural questions and Reported discrepancies using the required source `category`. Each target retains its demonstrated results, exact entries and supporting papers. Full entries show a compact Demonstrated results disclosure only when evidence exists, with distinct-target counts within each category rather than one combined score. The Problem filter uses the same grouped vocabulary in all four structural views and persists through catalogue navigation. Counts distinguish unique model–problem pairs from supporting paper demonstrations; absent evidence is not presented as a failure. Results are source-era claims, not current-viability or simultaneous-solution certificates.

Each full entry has one References toggle, regardless of how many papers are linked. It opens the linked titles, authors and arXiv URLs in oldest-first order. Paper IDs remain internal keys, not visible labels. The paper browser and filters use the same chronological order.

Dates use the first-submission month encoded in the [arXiv identifier](https://info.arxiv.org/help/arxiv_identifier.html). Papers are ordered by month, then by sequence number within an archive; cross-archive ties use a deterministic archive order. Dates are displayed with month precision.

The website shows only complete specifications. Its dimension labels and diagrams are presentation aids; exact Dynkin labels, Lorentz irreps, multiplicities and typed charges remain the stored objects.

GitHub Actions checks the files and publishes this directory on pushes to main. Reading new arXiv papers and adding their specifications is a separate ingestion step; the website build uses the checked-in catalogue.
