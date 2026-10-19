# BSM Atlas

[Explore the atlas](https://davibc.com/bsm-atlas/) · [Notation and conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) · [Adding entries](BSM_ATLAS_AGENT_PROMPT.md)

The gauge algebra and the representations of matter are the defining structural ingredients of the Standard Model. BSM Atlas uses these same objects to organize models beyond it: **a gauge algebra, Lorentz and gauge representations, multiplicities, and references to the papers that study them**.

The catalogue deliberately stops there. Interactions, coupling constants, global gauge-group quotients, extra symmetries, symmetry-breaking histories and assessments of physical viability are not separate data objects. Papers with the same gauge–matter specification share an entry. Inclusion is not a certificate of anomaly cancellation or an SM embedding.

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

[atlas/catalogue.json](atlas/catalogue.json) is the single authoritative source. It contains paper records and complete entry specifications with paper references. Optional reference locators identify pages, equations or tables; there is no separate claims, evidence or review graph. Papers can be listed without any associated model.

There are currently **67 entries**: 65 numerical specifications and two symbolic charge families, linked to 37 of the 51 listed papers. They form 11 semisimple gauge parts, 14 full gauge algebras and 58 semisimple matter spectra. These count gauge–matter structures, not complete physical theories.

The [catalogue schema](atlas/catalogue.schema.json) describes entries and references; the [specification schema](atlas/entry.schema.json) describes the mathematical input. Executable validation also enforces normalization, exact weights, charge syntax, complete inventories and duplicate identities. Only fully specified entries are added.

## Build and contribute

Python 3.10+ (with SQLite 3.37+) and Node.js 18+ are sufficient; no third-party packages are needed.

```sh
make build   # regenerate the website data and JSON, CSV and SQLite downloads
make check   # validate the source, exports, mathematics and interface
make serve   # preview at http://127.0.0.1:8000
```

To add a source-checked candidate, follow [the ingestion instructions](BSM_ATLAS_AGENT_PROMPT.md). The writer normalizes it and merges paper references on an exact match. Dry-run is the default.

```sh
python3 atlas/catalogue.py --add candidate.json
python3 atlas/catalogue.py --add candidate.json --write
make build
make check
```

GitHub Actions runs these checks and publishes `website/` to GitHub Pages. The site is entirely static and does not connect to the DSI cluster.

## Repository map

| Path | Purpose |
|---|---|
| `atlas/catalogue.json` | Authoritative entries and bibliography |
| `atlas/reference_spectra.json` | Exact SM/MSSM spectra used only for presentation shorthand |
| `atlas/*.py` | Validation, normalization, identity, restriction and ingestion |
| `atlas/schema.sql` | Minimal relational export schema |
| `website/` | Static explorer, builder, exports and regression tests |
| `scripts/check.py` | The shared local/CI verification command |

The superseded DSI snapshot, extraction-run archives and rich-schema machinery have been removed from the active repository. Their previous versions remain recoverable in Git history. Locally cached papers are not part of the published site.
