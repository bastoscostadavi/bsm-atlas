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

Routes include `#catalogue`, `#full-algebras`, `#algebra/<id>`, `#full-algebra/<id>`, `#cores`, `#core/<id>` and `#entry/<id>`. `#atlas`, `#notation` and `#sources` explain the catalogue, its conventions and its bibliography. Legacy `#about` opens The atlas. Entry details show paper references, not extraction logs or review states.

The website shows only complete specifications. Its dimension labels and diagrams are presentation aids; exact Dynkin labels, Lorentz irreps, multiplicities and typed charges remain the stored objects.

GitHub Actions checks the same files and publishes this directory on pushes to main. No data is fetched from DSI or arXiv at build time.
