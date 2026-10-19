# BSM Atlas

[Explore the atlas](https://davibc.com/bsm-atlas/) · [Conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) · [Contributing data](BSM_ATLAS_AGENT_PROMPT.md)

A source-backed catalogue of beyond-Standard-Model gauge algebras and matter representations.

## The organizing principle

The gauge algebra and the representations of the fields are fundamental data defining the Standard Model's gauge-and-matter structure. We organize BSM models around the same data: **gauge algebra, Lorentz and gauge representations, and multiplicities**, linked to the papers that describe them.

For the Standard Model,

`g_SM = su(3) ⊕ su(2) ⊕ u(1)`.

Its familiar matter content, in an all-left-handed convention with integer hypercharge `q = 6Y`, is:

| Field | Lorentz representation | g_SM representation | Multiplicity |
|---|---|---|---|
| Q | (1/2, 0) | (3, 2; 1) | 3 |
| uᶜ | (1/2, 0) | (3̄, 1; −4) | 3 |
| dᶜ | (1/2, 0) | (3̄, 1; 2) | 3 |
| L | (1/2, 0) | (1, 2; −3) | 3 |
| eᶜ | (1/2, 0) | (1, 1; 6) | 3 |
| H | (0, 0) | (1, 2; 3) | 1 |

Multiplicity counts repeated representations, not their dimensions. Scalar multiplicities use irreducible real gauge modules; the Higgs is one underlying real module of its complex gauge representation.

This is a catalogue of **gauge–matter content**, not complete Lagrangians. Interactions, couplings, global gauge-group quotients, additional symmetries and symmetry-breaking patterns carry further information. Different physical theories can therefore share one atlas entry. These richer structures can be added later without changing the present organizing principle.

## Two paths through one catalogue

```text
Semisimple gauge part ──────────→ Full gauge algebra
          │                              │
          ↓                              ↓
Semisimple matter spectrum ─────→ Full matter spectrum
```

The **semisimple part of the gauge algebra** omits every U(1) factor. From there, either add the Abelian factors to browse full gauge algebras, or add Lorentz representations, non-Abelian irreps and multiplicities to browse semisimple matter spectra. Both paths reach the same full entries with all gauge factors, matter representations, charges and linked papers.

The full-algebra grouping records canonical simple factors and the number of U(1) factors, not a generator basis or global gauge group. These are derived views, not independently maintained inventories. Only complete source-supported entries appear in any view. A partial sector cannot create an algebra category, and missing information is never guessed.

## Conventions and evidence

- Simple algebras use canonical Cartan type/rank; non-Abelian irreps use exact highest-weight **Dynkin labels** with fixed node numbering. The website also offers familiar dimensions and Young diagrams where applicable.
- Four-dimensional Weyl fermions are left-handed. Charge conjugation conjugates every non-Abelian factor and negates every Abelian charge.
- Numerical U(1) charges use one shared primitive integer normalization over the complete inventory. Symbolic families use canonical integer parameters `z1,z2,...` and expanded polynomials, with source names preserved in provenance. Stated constraints remain part of exact template matching; no logical domain-equivalence solver is used. Numerical normalization is applied after specialization.
- Paper versions, original notation, source passages and normalization steps remain traceable. Unfinished extraction, genuine source omissions and source-defined parameters are distinct.
- Exact field-content matches reuse an existing entry. Inclusion does not certify anomaly cancellation, viability or an SM embedding.

See the [complete conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) and [entry schema](atlas/entry.schema.json). The historical machine key `copies` means multiplicity; it is retained for schema and fingerprint compatibility.

## Current coverage

The atlas contains **67 complete gauge-matter entries: 65 fixed numerical specifications and two symbolic charge families**, linked to 37 papers. They form 58 semisimple matter spectra, 11 semisimple gauge parts and 14 full gauge algebras. These are field-content counts, not distinct complete physical theories.

All 50 seed papers and the independent theory reference R01 remain listed. A paper may have zero model links. There are no pending entries, incomplete sectors or exclusion log in the public atlas.

Publication follows **paper → full specification → normalization and validation → duplicate reconciliation → acceptance**. [Accepted harvests](atlas/reextraction/accepted-harvest.json) pin source evidence and exact inputs. An exact match adds the paper association to an existing entry. A sector that cannot establish a full inventory is not added. The historical DSI snapshot and earlier frozen research remain unchanged for reproducibility; they are not the current public catalogue.

## Develop and contribute

Python 3 and Node.js are required; no third-party Python or npm installation is needed.

```sh
make build   # regenerate catalogue JSON, CSV and SQLite
make check   # validate data, conventions, source integrity and website
make serve   # http://127.0.0.1:8000
```

Without Make, run `python3 website/build_field_catalogue.py`, `python3 scripts/check.py` and `python3 -m http.server 8000 --bind 127.0.0.1 --directory website`.

For new data, follow the [extraction → normalization → review workflow](BSM_ATLAS_AGENT_PROMPT.md). Start with the [numerical](atlas/examples/two-higgs-doublets.json) or [symbolic](atlas/examples/parameterized-charges.json) example; examples are not accepted source models. The [seed manifest](BSM_ATLAS_SEED.md) pins the original 50 sources.

## Repository

| Path | Purpose |
|---|---|
| `atlas/` | Representation conventions, schemas, normalization/identity code, curations and extraction evidence; [data map](atlas/README.md). |
| `website/` | The current static explorer, generated downloads, catalogue builder and focused tests; [maintenance guide](website/README.md). |
| `scripts/check.py` | The single local/CI verification command. |

The original DSI snapshot (`atlas/atlas.sqlite`, its SQL export and provenance) is preserved read-only for reproducibility. Its 34-table design documents describe that historical extraction, not additional requirements for the current catalogue. The superseded website, exporters and duplicate public snapshot files have been removed; earlier versions remain recoverable from Git history.
