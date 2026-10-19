# Static explorer

The GitHub Pages site at [davibc.com/bsm-atlas](https://davibc.com/bsm-atlas/) reads a generated local payload. It needs no backend, cluster connection or login.

From the repository root, run `make build`, `make check` and `make serve`. Preview at http://127.0.0.1:8000/. Python and Node are the only runtime dependencies.

## Source and exports

`build_field_catalogue.py` reads only `atlas/catalogue.json` and the SM/MSSM reference spectra. It validates every specification, computes identities and the four browsing views, then generates:

- `catalogue.json`: the minimal source catalogue, identical to `atlas/catalogue.json`; the JSON download points here.
- `field-catalogue.json`, `field-catalogue-data.js` and `../atlas/FIELD_CONTENT_CATALOGUE.json`: the same entries, references and derived presentation data.
- `entry.schema.json` and `catalogue.schema.json`: published schema copies.
- `downloads/field-catalogue.sqlite`: a typed relational projection, with full exact specifications and paper links.
- `downloads/field-catalogue.csv`: one row per entry, including its exact specification as JSON.
- The three grouping CSVs: one row per semisimple algebra, full algebra or semisimple matter spectrum, with exact canonical content and linked entry IDs.

Do not hand-edit generated files. `make check` rebuilds them in memory or temporary storage and detects stale text or SQLite content. It also checks strict ingestion, normalization, identity invariances, diagram geometry and navigation.

## Interface

`index.html`, `field-catalogue.css` and `field-catalogue.js` implement the interface. `field-matrix.js` lays out exact derived rows; `presentation.py` computes readable dimensions and safe SM/MSSM shorthand. `core_projection.py` generates all four view memberships. `representation-diagrams.js` and locally vendored SVG.js draw Dynkin and eligible A-series Young diagrams.

The Catalogue disclosure groups four links under Gauge algebra and Gauge algebra and matter representations. Each group offers Semisimple part and Full. Search, paper filters, Abelian rank and notation selections survive navigation. Selecting a matter core and a full gauge algebra intersects the two groupings.

A compact Back link returns from a nested catalogue view to its parent, retaining search and filter selections. It uses catalogue routes rather than browser history, so it also works when a filtered page is opened directly.

Routes include `#catalogue`, `#full-algebras`, `#algebra/<id>`, `#full-algebra/<id>`, `#cores`, `#core/<id>` and `#entry/<id>`. `#atlas`, `#notation` and `#sources` explain the catalogue, its conventions and its bibliography. Legacy `#about` opens The atlas. Entry details show paper references, not extraction logs or review states.

Each full entry has one References toggle, regardless of how many papers are linked. It opens the linked titles, authors and arXiv URLs in oldest-first order. Paper IDs remain internal keys, not visible labels. The paper browser and filters use the same chronological order.

Dates use the first-submission month encoded in the [arXiv identifier](https://info.arxiv.org/help/arxiv_identifier.html), not the selected revision date. Sequence numbers order papers within a month and archive; legacy cross-archive ties use a deterministic archive order. The interface shows month precision and does not fabricate exact submission days.

The website shows only complete specifications. Its dimension labels and diagrams are presentation aids; exact Dynkin labels, Lorentz irreps, multiplicities and typed charges remain the stored objects.

GitHub Actions checks the same files and publishes this directory on pushes to main. No data is fetched from DSI or arXiv at build time.
