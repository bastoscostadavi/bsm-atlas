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

## Three views of one catalogue

1. **Non-Abelian gauge algebra** — the semisimple part, with matter and all U(1) factors omitted.
2. **Non-Abelian matter spectrum** — that algebra with Lorentz representations, non-Abelian irreps and multiplicities.
3. **Full gauge–matter entry** — every gauge factor, exact Abelian charges and linked source papers.

These are derived groupings, not three independently maintained inventories. A recorded algebra can appear before its matter extraction is complete. Unknown ranks and missing representations are never guessed.

## Conventions and evidence

- Simple algebras use canonical Cartan type/rank; non-Abelian irreps use exact highest-weight **Dynkin labels** with fixed node numbering. The website also offers familiar dimensions and Young diagrams where applicable.
- Four-dimensional Weyl fermions are left-handed. Charge conjugation conjugates every non-Abelian factor and negates every Abelian charge.
- Numerical U(1) charges use one shared primitive integer normalization over the complete inventory. Symbolic charge families have declared integer parameters and constraints; their schema/preflight exists, but automatic public-family ingestion is not yet connected.
- Paper versions, original notation, source passages and normalization steps remain traceable. Unfinished extraction, genuine source omissions and source-defined parameters are distinct.
- Exact field-content matches reuse an existing entry. Inclusion does not certify anomaly cancellation, viability or an SM embedding.

See the [complete conventions](atlas/FIELD_CONTENT_CONVENTIONS.md) and [entry schema](atlas/entry.schema.json). The historical machine key `copies` means multiplicity; it is retained for schema and fingerprint compatibility.

## Current coverage

The saved 50-paper seed supports 103 source-scoped entries: 21 complete numerical inventories, grouped into 17 non-Abelian matter spectra. Fourteen recorded semisimple algebras cover 94 entries; nine have unresolved or parameterized algebras. These are not counts of distinct complete physical theories.

The paper list is independent: general theory and tool papers can have no model association. R01 is an additional theory reference, not a BSM entry. Accepted scoped re-extractions cover eight seed papers. Of the 37 numerical candidates staged in the [historical followup handoff](atlas/reextraction/followup-20261016/handoff.json), 36 remain unaccepted. Neither a registered paper nor a staged candidate implies a completed or independently verified extraction.

The [SO(10) source and mathematics review](atlas/reextraction/so10-resolution-20261016/decision.json) completes both P19 entries, including the smaller 45H + 126H model previously extracted only as a scalar sector. Its three-family fermion baseline is explicitly declared source-SM inheritance; no literal multiplicity table or phenomenological viability is claimed. The original snapshot and earlier extraction decisions remain preserved.

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
