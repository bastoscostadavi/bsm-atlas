# BSM Atlas

[Explore the atlas](https://davibc.com/bsm-atlas/) · [Notation and conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) · [Adding entries](BSM_ATLAS_AGENT_PROMPT.md)

The gauge algebra and the representations of matter are the defining structural ingredients of the Standard Model. BSM Atlas uses these same objects to organize models beyond it: **a gauge algebra, Lorentz and gauge representations, multiplicities, and references to the papers that study them**.

Each entry is a complete gauge–matter specification linked to the arXiv papers that study it. Papers with the same specification share an entry, even when their interactions differ. The atlas classifies this structural content; anomaly cancellation, phenomenological viability and embeddings are questions to investigate using the references.

## One catalogue, four views

The explorer groups the same entries by:

| | Gauge algebra | Gauge algebra and matter representations |
|---|---|---|
| Semisimple part | Simple non-Abelian factors | Those factors, Lorentz representations, irreps and multiplicities |
| Full | All factors, including U(1) | The complete specification, including charges |

These are derived views, not four independently maintained tables. One can add matter first or Abelian factors first and reach the same full entries. Restricting to the semisimple part also decomposes real scalar modules correctly; it is not merely hiding charge columns.

## Precise objects

Simple algebras use canonical Cartan type and rank; non-Abelian representations use highest-weight Dynkin labels in fixed node order. Numerical U(1) charges are primitive integers in an explicit generator basis. Four-dimensional independent Weyl fermions are all left-handed. Multiplicity counts repeated representations, not their dimensions; scalar multiplicity counts irreducible real gauge modules.

An entry may instead specify a symbolic charge family: integer parameters, expanded integer polynomials and explicit constraints. Parameter names are standardized to `z1,z2,...`; a family remains one entry rather than an enumeration of its members. The matcher removes the stated notation redundancies, not arbitrary reparameterizations or logically equivalent domains.

See the [conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) for scalar counting, conjugation, normalization and the limits of identity matching.

## Data

[atlas/catalogue.json](atlas/catalogue.json) is the single authoritative source. It contains paper records and complete entry specifications with paper references. References can identify relevant pages, equations or tables. Papers can be listed without an associated model.

The website derives its four browsing views and counts directly from this source. JSON, CSV and SQLite downloads expose the same catalogue for analysis and reuse.

The [catalogue schema](atlas/catalogue.schema.json) describes entries and references; the [specification schema](atlas/entry.schema.json) describes the mathematical input. Executable validation also enforces normalization, exact weights, charge syntax, complete inventories and duplicate identities. Only fully specified entries are added.

## Adding papers and models

The catalogue grows by harvesting complete specifications from arXiv papers. Read the source, express its gauge and matter content in the atlas conventions, and reconcile it with the existing entries. An exact match gains a paper reference; a distinct specification becomes a new entry.

Follow the [ingestion instructions](BSM_ATLAS_AGENT_PROMPT.md) for paper records, candidate files and source checks. The ingestion command normalizes and validates a candidate before saving it. Dry-run is the default.

```sh
python3 atlas/catalogue.py --add candidate.json
python3 atlas/catalogue.py --add candidate.json --write
make build
make check
```

## Build and preview

Python 3.10+ (with SQLite 3.37+) and Node.js 18+ are sufficient; no third-party packages are needed.

```sh
make build   # regenerate the website data and JSON, CSV and SQLite downloads
make check   # validate the source, exports, mathematics and interface
make serve   # preview at http://127.0.0.1:8000
```

GitHub Actions runs the checks and publishes `website/` to GitHub Pages. The self-contained static site serves the catalogue and its downloads without a database server.

## Repository map

| Path | Purpose |
|---|---|
| `atlas/catalogue.json` | Authoritative entries and bibliography |
| `atlas/reference_spectra.json` | Exact SM/MSSM spectra used only for presentation shorthand |
| `atlas/*.py` | Validation, normalization, identity, restriction and ingestion |
| `atlas/schema.sql` | Relational export schema |
| `website/` | Static explorer, builder, exports and regression tests |
| `scripts/check.py` | The shared local/CI verification command |
