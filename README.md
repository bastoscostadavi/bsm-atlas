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

Representation records contain only schema-defined mathematical data. Field symbols and descriptive labels are not stored; model names and paper metadata remain separate from the specification.

An entry may instead specify a symbolic charge family: integer parameters, expanded integer polynomials and explicit constraints. Parameter names are standardized to `z1,z2,...`; a family remains one entry rather than an enumeration of its members. The matcher removes the stated notation redundancies, not arbitrary reparameterizations or logically equivalent domains.

See the [conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) for scalar counting, conjugation, normalization and the limits of identity matching.

## Data

[atlas/catalogue.json](atlas/catalogue.json) is the single authoritative source. It contains paper records and complete entry specifications with paper references. References can identify relevant pages, equations or tables. Papers can be listed without an associated model.

The website derives its four browsing views and counts directly from this source. JSON, CSV and SQLite downloads expose the same catalogue for analysis and reuse.

The [catalogue schema](atlas/catalogue.schema.json) describes entries and references; the [specification schema](atlas/entry.schema.json) describes the mathematical input. Executable validation also enforces normalization, exact weights, charge syntax, complete inventories and duplicate identities. Only fully specified entries are added.

## Adding papers and models

Extraction texts, per-paper prompts and raw responses are temporary. Compact
completion receipts retain only the metadata, hashes, usage and ingestion targets
needed to resume without repeating paper attempts; see the
[retention policy](HARVESTING.md#temporary-data-and-compact-completion-tracking).

The catalogue grows by harvesting complete specifications from arXiv papers. Read the source, express its gauge and matter content in the atlas conventions, and reconcile it with the existing entries. An exact match gains a paper reference; a distinct specification becomes a new entry.

Follow the [ingestion instructions](BSM_ATLAS_AGENT_PROMPT.md) for paper records, entry files and source requirements. Manual entry commands normalize and validate an entry before saving it. Dry-run is the default.

```sh
python3 -m bsm_atlas add entry.json
python3 -m bsm_atlas add entry.json --write
make build
make check
```

All catalogue operations use `python3 -m bsm_atlas`. Use `validate` to check the source, `prepare specification.json` to inspect normalization, and `lookup specification.json` to find matches in the built SQLite export. These commands are read-only. Run commands from the repository root. No package installation is required.

For batches, the [paper-harvesting coordinator](HARVESTING.md) retrieves pinned full texts and assigns one paper to each isolated worker. Code normalizes, validates and automatically writes the extracted entries, merging canonical duplicates and their references. There is no separate proposal or model-approval pass. The existing paper records store an informational `extraction_status`; normal expansion skips every recorded arXiv version before retrieval or agent dispatch, including old failures. Retries require an explicit follow-up. Run files stay private and do not add tables to the atlas.

The [extraction pilot](experiments/extraction-pilot/README.md) documents the 20-paper model comparisons, including frozen prompts, per-paper outcomes, measured tokens and runtime, illustrative costs, and the limits of the comparison. It is separate from the catalogue and makes no arXiv-wide accuracy claim. The [manuscript](paper/main.tex) includes the same results. New extraction batches default to GPT-6.1 Sol with medium reasoning.

For expansion, the coordinator ranks unrecorded papers using INSPIRE citation metadata, verifies that their primary arXiv category is hep-ph, pins their versions, and feeds a rolling worker pool from one serial source fetcher. Completed work is retained when a run stops, and saved valid responses can be imported without another model call. See [citation-ranked expansion](HARVESTING.md#citation-ranked-expansion).

Codex and Claude Code workers share the same conventions, validator and automatic
ingester. Disjoint paper reservations prevent overlapping batches; shared locks
coordinate arXiv requests and catalogue updates. Papers retain compact extractor
provider, model and effort metadata, independently of the physics specification.
See [provider coordination and provenance](HARVESTING.md#codex-and-claude-batches).

## Build and preview

Python 3.10+ (with SQLite 3.37+) and Node.js 18+ on macOS/Linux are sufficient; no third-party Python packages are needed. Model extraction additionally requires a current, authenticated Codex CLI; building and checking the existing catalogue does not.

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
| `atlas/reference_spectra.json` | Exact SM/MSSM inventories for explicitly inherited input and presentation shorthand |
| `atlas/schema.sql` | Relational export schema |
| `bsm_atlas/` | Python package: intake, mathematical conventions, identities, projections and export |
| `tests/` | Python and JavaScript regressions, with identity fixtures |
| `website/` | Published static explorer and generated downloads |
| `scripts/check.py` | The shared local/CI verification command |
| `experiments/extraction-pilot/` | Frozen extraction-pilot inputs, audit outcomes, measurements and report checks |
| `paper/` | LaTeX manuscript and reproducible catalogue analysis |
