# Extract gauge–matter content for BSM Atlas

Use this prompt with the [conventions](atlas/FIELD_CONTENT_CONVENTIONS.md), [entry schema](atlas/entry.schema.json) and the requested source papers. The [seed manifest](BSM_ATLAS_SEED.md) pins the initial 50 papers; its broader historical reading scopes do not expand the present catalogue's required fields.

## Objective

Produce source-backed gauge-algebra and matter-representation entries, linked to paper versions. The fundamental organizing data are the gauge algebra, Lorentz and gauge representations, and multiplicities—not a model name, motivation or claimed phenomenological success.

This is a gauge–matter catalogue, not a catalogue of complete Lagrangians. Do not add interactions, global symmetries, breaking patterns, benchmark scans or viability classifications as new required structure. Preserve existing richer evidence without silently rewriting its meaning.

A theory, methods or convention paper may have a paper record and zero model links. Harvest a complete specification BEFORE adding a model. Incomplete sectors, unfinished extraction and uninstantiated frameworks are not public entries, and no permanent pending catalogue or exclusion log is maintained.

## Establish the source facts

1. Read the pinned paper's actual field definitions, equations, tables and necessary surrounding text. Abstracts alone are insufficient. Record inspected sections and pages; do not call a reused earlier source check a new independent rereading.
2. Select one description regime. Do not sum unified and low-energy spectra, elementary fields and dependent composite coordinates, or bulk and brane descriptions.
3. Establish all gauge factors, matter representations, Lorentz types and multiplicities, including explicitly inherited SM/MSSM content. Gauge connections are implied by the algebra, not extra independent matter.
4. Preserve the source notation and a paper-version/section/equation/table locator for each assignment. Distinguish source statements, inherited assumptions and mathematical derivations. Register any essential auxiliary source and its version.
5. Distinguish unfinished extraction from a genuine source omission. `not_extracted` is work remaining, not a scientific value. Use `not_specified_by_source` only after inspecting the relevant scope. A paper-defined free parameter is neither of these.

Never invent a missing singlet, generation count, field reality condition or completion sector to obtain a full inventory. Preserve disagreements and source misprints with their evidence.

## Normalize before proposing ingestion

- **Gauge algebra:** canonical simple Cartan type/rank and explicit U(1) factors. This is local information; do not infer a global group or quotient.
- **Non-Abelian irreps:** exact nonnegative Dynkin labels in the fixed Bourbaki/Sage node convention. Record any source-node conversion. A dimension alone is not a unique representation identifier.
- **Spacetime:** use the dimension-appropriate field representation. In 4D use `(j_L,j_R)`; scalars are `(0,0)` and LH Weyl fields `(1/2,0)`. Do not apply a 4D conversion blindly to higher-dimensional spinors.
- **Fermions:** every identified 4D Weyl field is left-handed. Replacing a RH field by its LH conjugate conjugates every non-Abelian irrep and negates every U(1) charge. A 4D Dirac field becomes two independent LH rows. Do not count dependent Hermitian conjugates again.
- **Scalars:** count irreducible real gauge modules. A source complex scalar in a real-type irrep contributes two real-module copies; in a complex- or pseudoreal-type irrep it contributes one underlying real module. Keep source field reality and source-container counts separately. Do not infer a source field reality condition from self-duality alone.
- **Multiplicity:** count repetitions of a representation, not its dimension. The compatible machine key remains `copies`. A family charge list such as `[0,-3,3]` becomes separate rows, not one scalar-valued charge or three identical copies.
- **Numerical charges:** use exact arithmetic and one shared primitive integer U(1) normalization over the complete inventory, including both scalars and fermions. Record the source-to-atlas scale and orientation. The SM reference uses `q=6Y`. Never normalize each matter row or the scalar subset independently.

Expand presentation baselines before identity comparison. Neutral fields and vector-like pairs remain matter even if they do not contribute to anomalies. Anomaly cancellation, phenomenological viability and an SM-embedding proof are not intake requirements.

## Symbolic charge families

Use `field-content-3` with declared integer parameters, charge polynomials and constraints, as in [the example](atlas/examples/parameterized-charges.json). A fixed version-3 entry has `parameters: {}`.

The restricted language permits integer literals, declared symbols, parentheses, `+`, `-`, `*` and literal nonnegative `**`. Constraints use exact polynomial comparisons. No floats, charge arrays, undeclared symbols, arbitrary functions or `eval`.

Do not enumerate an infinite family. Preflight without parameter values produces a validated symbolic payload, not a numerical fingerprint. Specialization checks integer assignments and constraints, then normalizes that member's full inventory. Special charge loci can change scalar counting or row aggregation.

Reviewed version-3 families can be published on the same entry with typed SQL parameter, constraint and charge-expression storage. Never put a formula into the integer-only numerical charge column. A family fingerprint identifies the exact normalized template, not general equivalence under reparameterization. Compute non-Abelian restriction before realification of the source fields, without using a fictitious specialization. A charge-dependent scalar counting jump needs a reviewed piecewise adapter; do not display a guessed generic multiplicity.

## Preflight and reconciliation

From the repository root:

```sh
python3 atlas/prepare_entry.py candidate.json --database website/downloads/field-catalogue.sqlite
python3 atlas/prepare_entry.py normalized.json --require-normalized --database website/downloads/field-catalogue.sqlite
python3 atlas/check_entry.py normalized.json --database website/downloads/field-catalogue.sqlite
```

Preflight emits the normalized entry, conversions and duplicate results; it is read-only and does not inspect papers or add records. Save its output and the exact normalized candidate using the available file tools. A blocked or still unnormalized candidate must not be accepted.

An exact match reuses the existing field-content entry and adds the source/paper association. A nonmatch is `no_exact_match_review_required`, not proof of a new or inequivalent theory. Review comparable published entries, description regimes, repeated factors, multi-U(1) basis choices and outer-automorphism limits. Aliases must resolve to the reused entry.

Do not mark a partial sector `inventory_complete` just to get a fingerprint. Different interactions may share one gauge–matter entry; different field names need not create one.

## Review, persistence and checks

Work on candidate extraction outside the public catalogue. Save complete candidates and evidence in a new explicitly named run directory under `atlas/reextraction/`, then pin accepted files in `accepted-harvest.json`. Do not save a new exclusion log or insert incomplete model rows. Do not overwrite frozen runs, accepted evidence or `atlas/atlas.sqlite`. Do not claim inferred token/dollar/GPU measurements; unavailable telemetry remains null.

For each candidate provide:

- Target entry or a proposed reconciliation, paper/version and description regime.
- Original source containers and explicit source-field/model/regime mappings, including inherited fields.
- Exact normalized payload, transformation/preflight receipts and attribute-level evidence.
- Genuine omissions, unresolved extraction tasks and source-defined parameter domains, separately.
- Actual inspection scope, review status and any supporting-source hashes.

Only explicitly reviewed, hash-pinned acceptance decisions are read by the public builder. A new paper requires verified title, authors and pinned arXiv version in the acceptance metadata; the generic adapter can create its complete entry directly, without a provisional DSI record. New catalogue row IDs are not historical source field IDs. Extend and test an adapter when a supported new source structure requires it. Do not force it through an unrelated conversion. The publication gate rejects unnormalized inputs or new complete identities lacking source-reviewed acceptance.

Then run:

```sh
make build
make check
```

Checks must preserve the original source checksum, frozen evidence and source IDs; validate exact normalization and SQLite/JSON agreement; and keep independent papers without fabricated model links.

## Derived browsing layers

The website derives four views from the same entries, arranged as a square rather than numbered steps:

- **Semisimple gauge part:** canonical non-Abelian factors, with matter and every U(1) omitted. This is the semisimple part of the full gauge algebra. Incomplete sectors must not create categories such as isolated su(2).
- **Full gauge algebra:** restore all U(1) factors, still omitting matter. Group by canonical simple factors and Abelian rank, not source generator names, global groups or quotients.
- **Semisimple matter spectrum:** Lorentz and non-Abelian irreps with multiplicities, omitting all U(1) factors. Restrict scalar real modules correctly and aggregate identical restricted rows.
- **Full matter spectrum:** all gauge factors, matter representations and charges, with linked sources.

From the semisimple gauge part, users can add Abelian factors first or matter first. Both paths reach the same full entries. All views derive only from complete published entries; do not guess omitted factors or finite ranks.

Do not maintain these as separate hand-edited inventories. A coarse match is not a full-spectrum match, physical-theory equivalence, a global-group specification or an SM-embedding certificate.

## Handoff

Report the actually published entries, their source-inspection scope and any remaining access/implementation limitation. A paper that does not establish a full supported inventory can have zero model links; do not add a placeholder. Structural checks and source-scoped extraction do not independently certify the physics.
