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

The Catalogue disclosure groups four links under Gauge algebra and Gauge algebra and matter representations. Each group offers Semisimple part and Full. These menu links open catalogue-wide views, clearing any algebra or matter-core selection made by drilling down. Search, paper filters, Abelian rank and notation selections survive navigation. Links within the catalogue retain the selected grouping; selecting a matter core and a full gauge algebra intersects the two groupings.

Algebra lists sort by the semisimple part's total rank, then dimension, then its canonical Cartan signature (family letters and numeric ranks). Full algebras with the same semisimple part sort next by the number of U(1) factors; remaining ties use the group ID. The semisimple filter and grouping CSVs preserve this order.

Matter cores and full entries use that algebra order, followed by the total real dimension of their Lorentz × gauge field representations, including multiplicities. Equal dimensions compare exact numeric Lorentz labels, gauge weights and charges, reality conventions and multiplicities; canonical symbolic metadata resolves remaining ties. The ordering is independent of model names and source row order. It does not change canonical factor order, representation columns or identities. See the [field-content conventions](../atlas/FIELD_CONTENT_CONVENTIONS.md#browsing-order) for counting examples and the exact tie-breaking convention.

Routes include `#catalogue`, `#full-algebras`, `#algebra/<id>`, `#full-algebra/<id>`, `#cores`, `#core/<id>` and `#entry/<id>`. `#atlas`, `#notation` and `#sources` explain the catalogue, its conventions and its bibliography. Entry details show the papers studying that specification.

Each full entry has one References toggle showing the number of linked papers. It opens the linked titles, authors and arXiv URLs in oldest-first order. Paper IDs remain internal keys, not visible labels. The paper browser and filters use the same chronological order.

The Papers page opens with an empty bibliography search. Submit a title, author or arXiv identifier, optionally narrowed by first-submission year; a year alone also works. Results appear only after searching, with 20 papers per page. Each result links to arXiv and lists direct links to its associated atlas entries under a disclosure. Search is case- and accent-insensitive. Searches and pagination can be shared through `#sources?search=...&year=...&page=...`; these controls are independent of the model catalogue filters.

Dates use the first-submission month encoded in the [arXiv identifier](https://info.arxiv.org/help/arxiv_identifier.html). Papers are ordered by month, then by sequence number within an archive; cross-archive ties use a deterministic archive order. Dates are displayed with month precision.

The website shows only complete specifications. Its dimension labels and diagrams are presentation aids; exact Dynkin labels, Lorentz irreps, multiplicities and typed charges remain the stored objects.

GitHub Actions checks the files and publishes this directory on pushes to main. Reading new arXiv papers and adding their specifications is a separate ingestion step; the website build uses the checked-in catalogue.
