# Gauge-algebra and matter catalogue

Version `gauge-matter-4`, October 16, 2026. This is a source-scoped projection with explicit curated corrections, not a replacement of `atlas.sqlite` or a new full physics review. The website deliberately exposes just this smaller catalogue.

### Accepted source-backed re-extractions

The first five papers (P01–P05) now have explicitly accepted, scoped gauge/matter re-extractions. Six paper/candidate occurrences reconcile to five existing entries; no model row is added. `reextraction/accepted.json` lists acceptance decisions, expected fingerprints and hashes of the reviewed checkpoint/attribute-evidence files. The public build rejects changed evidence, candidates still needing normalization, missing row provenance or a mismatched existing fingerprint. Unaccepted queue/batch work is never read by this gate. This protects this projection's reviewed intake; it is not a general-purpose, unbypassable database-write API.

P04 corrects the existing `lr-triplet-matter` entry and both parity/C regimes: colour explicitly suppressed in the source is restored using a declared SM baseline, Eq.(2) yields fermion B−L charges with stated SM electric-charge assumptions, all four fermion multiplets have three copies, and the common full-inventory unit is q=3(B−L). RH quarks/leptons become LH conjugates, including colour conjugation. The two scalar triplets have q=6, not `source:2`; Φ is a complex bidoublet. Definitions, inherited assumptions and derivations remain distinguished in provenance. The source coupling multiplies (B−L)/2, so in that convention g_atlas=g_source/6.

Original field IDs and original assertions are preserved, including each corrected field's `legacyProjection`. The normalized accepted input and separate source review are saved in the additive `extraction_reviews` table of the generated SQLite, as well as JSON. New review states do not alter legacy unchecked assertions. These are definition-scope agent source checks, not whole-paper readings or independent physics/anomaly/viability verification. P01/P02 share the existing real-singlet entry; 2HDM Type-I/II and NMSSM general/Z3 variants retain one field-content entry each. Frozen candidates and evidence retain their historical `field-content-1` fingerprints. Public numerical inputs now use `field-content-2`; each accepted review exposes both signatures and `identity_migrations` records the counting-convention change.

The all-50 agent pass is saved separately in `reextraction/corpus-handoff.json`: 18 completed-scoped, 27 partial-scoped and 5 reference-only papers; none queued/access-blocked. These are inspection-scope categories, not 50 complete spectra. P06–P50 contribute 42 frozen numerical candidate occurrences (41 historical signatures), plus partial descriptions. Their acceptance is not automatic: the public accepted gate remains P01–P05. The new counting convention has idempotent projections of all 48 pilot/corpus candidate occurrences without modifying frozen source evidence. Reported token/dollar/GPU costs remain null because those measurements were not exposed; retrieval and deterministic CPU/wall timings are recorded separately and are not inference cost.

## Papers are not model rows

The 50 seed papers remain independently listed. Additional general theory paper R01, **General solution to the U(1) anomaly equations**, arXiv:1905.13729v1, is a paper with **zero associations to the gauge/matter table**. It is listed independently, not as a BSM model. The notation convention below is defined directly and requires no paper association. Software, general theory, uninstantiated frameworks and SM operator-only examples likewise need not have a model association. Source records omitted from the BSM view remain in JSON `referenceRecords` and the unchanged original database.

There are 103 provisional field-content entries after the explicitly documented grouping/exclusion decisions. This is not a count of complete or distinct physical theories. Different interactions or global symmetries may share one field-content entry; incomplete entries cannot be globally deduplicated reliably.

## Algebra conventions

- Local compact Lie algebras use lowercase `su(n)`, `so(n)`, `u(1)` and direct sums. The SM shorthand is **g_SM = su(3) ⊕ su(2) ⊕ u(1)**. No global group or central quotient is inferred.
- Simple-factor keys use Cartan type and rank, e.g. A2 and A1. Low-rank B1=A1, D3=A3 and B2=C2 are normalized only at the algebra level. Numeric source Sp(N) conventions remain unresolved unless rank versus fundamental-dimension convention is known.
- Factor slots are sorted by Cartan family, descending rank, then role. Abelian factors follow non-Abelian factors; identified hypercharge is the first Abelian slot. Repeated factors retain role labels. A permutation is applied to representations together with the algebra; the slot keys are retained.
- Separate source groups are combined only as recorded product sectors. In the littlest-Higgs record, the diagonal EW subgroup is not appended to the UV doubled EW algebra.
- A source that records only an EW/new sector remains scoped. No missing colour representation or complete SM-containing embedding is inferred. A declared baseline can supply the SM algebra, but not invented assignments for new fields.

## Representations and charges

**Dynkin labels are the canonical database identifiers.** `([1,0], [1]; 1)` denotes the su(3) fundamental, su(2) doublet and Abelian charge +1. Square brackets hold one nonnegative highest-weight coefficient per simple-root node, not a dimension. Tuples list non-Abelian irreps in factor-slot order followed by Abelian charges after the semicolon. A question mark is unresolved, **not a singlet or zero**. For example, an SM singlet is `([0,0], [0]; 0)` and the Higgs is `([0,0], [1]; 3)`.

The machine convention is `dynkin-gauge-1`: finite-dimensional complex irreps, with **Bourbaki node numbering as implemented by [Sage finite Cartan types](https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/root_system/cartan_type.html)**. A_r uses the chain 1,…,r; B_r ends with the short-root spinor node; C_r ends with the long-root node; D_r has spinor nodes r−1,r attached to r−2. The referenced numbering also fixes E/F/G. This is a gauge convention, separate from the existing dimension-specific Lorentz B/D convention. Map any differently numbered source labels explicitly before intake; do not silently reverse or exchange nodes. Algebra aliases such as D3=A3 also require an explicit weight map when the source supplies Dynkin labels.

The implemented A-series conversions have fundamental `[1,0,…,0]` and conjugate `[0,…,0,1]`; SU(2) dimension d has label `[d−1]`. Familiar SU(3) 6/10 and their conjugates are converted conservatively. Dimensions do not uniquely identify all irreps: ambiguous cases, including SO spinor conventions, remain null/`?` in the canonical data and Dynkin display, never a bare dimension masquerading as a Dynkin label. Original representations, exact charges and normalization notes remain in provenance. A-series Young row lengths are sums of the Dynkin labels to the right; they are derived displays, not additional identity rules.

The website defaults to readable dimensions/charges such as `(3,2;1)`. A visible notation control switches to Dynkin labels, A-series Young diagrams, or an in-cell comparison of all three. Gauge-column headings show finite-type Dynkin diagrams in the same Bourbaki node convention; these describe the **algebra**, not a particular matter irrep. Abelian factors are explicitly labelled without a Dynkin graph. Parameterized or unknown factors get no invented diagram. SVG.js 3.2.8, vendored with its MIT license, renders the geometry locally; it does not infer representations. Oversized Young diagrams fall back to exact row lengths rather than silently clipping boxes.

The JSON adds `representationConvention` and `dynkinRepresentation` on source containers, Lorentz components and baseline templates. Structured `components[].dynkin`, per-component `gaugeComponents[].dynkin`, charges and factor keys remain the actual machine identifiers; formatted strings are displays, not identity keys. Legacy `representation` fields retain their dimension/source-container shorthand for compatibility. The summary CSV now uses Dynkin tuples. SQLite saves the same convention in `metadata.representation_convention_json`; `dynkin_json` remains the canonical weight column, while `representation_label` retains the prior shorthand. The notation-only version-3 change did not modify scalar counting; version 4 below does, explicitly and with signature migration history.

For each concrete U(1) assignment, one positive common rescaling makes charges integral with gcd 1. Field labels and the source generator orientation are retained; fields are not sorted into an unlabeled charge set. A declared SM reference supplies its charge unit. Ordinary textbook hypercharge uses **q = 6Y**; sources with Q=T3+Y_source/2 instead use q=3Y_source. The corresponding coupling is g_atlas=g_source/scale.

An incomplete or symbolic assignment is not normalized using an arbitrary numeric subset. Source strings such as `source:2` remain provenance, never values in the numerical charge column. In pending views the cell is `?` until the full shared unit is established; P04 now supplies that unit for the left–right entry. All-zero charges alone do not define a unit. Multiple U(1) basis changes and kinetic mixing are not resolved by separate gcd rescalings. The JSON records each factor's normalization status, scale, reference and scope.

## Matter and baselines

### Scalar counting in version 4

The canonical unit is **one irreducible real gauge module** (`scalar-real-modules-1`). A displayed highest weight still labels an irreducible complex representative R of complex dimension d:

- Real type: use its real form (real dimension d). One source real field contributes one copy; one unconstrained source complex field contributes two copies.
- Complex type: use the underlying real module (real dimension 2d). R and its **full** conjugate specify the same scalar module; one source complex field contributes one copy.
- Pseudoreal type: use the underlying real module (real dimension 2d). An ordinary half-dimensional real condition is not allowed. One source complex field contributes one copy.

For self-dual irreps, real versus pseudoreal type is computed by the exact Tits/Frobenius–Schur indicator `(-1)^(lambda(2rho^vee))`; for tensor products the indicators multiply. See [Theorem 3.6](https://arxiv.org/html/0704.0165v1). A nonzero U(1) charge gives complex type. Self-duality alone does not establish a real form. In particular, a neutral SU(2)×SU(2) bidoublet is real type, so the source complex P04 Φ contributes two canonical copies. A charged SM Higgs contributes one underlying-real copy, not two. A complex neutral singlet contributes two copies; two source real singlets have the same signature.

Choose a scalar's complex representative by making its first nonzero Abelian charge positive; when all charges vanish, choose the lexicographically larger of its weight tuple and full dual. Rechoose after factor permutations/sign transformations during fingerprinting. Conjugate **all factors together**. This scalar equivalence is not used for Weyl fermions. The global gauge group/quotient remains unasserted.

Canonical scalar components have `reality: real_module`, their own `copies`, and normalization metadata. Source-container `copies`, reality and gauge labels remain provenance in `sourceScalar`/original fields; they are not canonical component counts. The website, CSV and SQL component table use component copies consistently. No separate real/complex annotation is needed on a completed scalar row. If the source count/reality has not been established, the component remains pending; the representation type alone cannot select one versus two real copies.

The default website now shows 15 complete numerical inventories under these conventions. The remaining 88 provisional source records are preserved behind Coverage → Pending source records and in downloads, not presented as accepted spectra. A computable identity is not independent source, anomaly or viability certification.

### Parameterized families: proposed organization, not implemented ingestion

Do not enumerate every integer substitution. Keep a separate family record with fixed gauge/field structure, shared parameter IDs, domains, constraints and one scalar-valued charge expression per field/factor. Keep concrete normalized spectra separately; associate them with a family only when a paper studies that specialization, or when a user explicitly materializes one. Papers can associate with either kind of record.

Distinguish counts of recorded concrete spectra from counts of families. A family's member set can be infinite. Remove normalization-only freedom: `(n,-n)` for integer n≠0 represents the same primitive spectrum `(1,-1)`, whereas `(1,-1,n,-n)` generally retains a charge-ratio parameter. Zero/special parameter values may change normalization, real-module type or identical-row merging and require separate strata. Arbitrary symbolic-family equivalence/overlap is not solved by the numerical fingerprint checker. A family-vector source assignment such as `[0,-3,3]` must expand into separate field rows (merging only identical representations), not become one charge-cell value. Until a dedicated validated family schema is implemented, these descriptions stay in separate staging/pending records.

The website uses **one matrix per entry**: rows are independent matter representations, columns are spacetime and the actual gauge-algebra factors, followed by copies. A direct SM factor is shown as g_SM; an SM subgroup embedded inside SU(5), SU(4), etc. is not appended as a second gauge factor. Identical resolved rows in one regime combine their copy counts using Dynkin labels and exact charges, not dimensions or source names. Unknown weights never establish a merge; su(3) [2,1] and [4,0], both dimension 15, stay distinct. Source variants and separate regimes never become duplicated simultaneous spectra. Baseline rows expand on demand.

### Lorentz convention: all 4D Weyl fields are left-handed

The machine convention is `lorentz-field-1`. Four-dimensional labels are (j_L,j_R) for finite-dimensional representations of Spin^+(1,3): scalar (0,0), LH Weyl (1/2,0), vector (1/2,1/2). These are **field representations**, not on-shell Poincare particle spin/polarization counts. Source scalar reality conditions remain provenance; canonical scalar rows use the real-module counting unit described below.

Every identified RH Weyl field is replaced by its independent LH charge conjugate: `(R; q_1,…,q_k)_R → (conjugate(R); −q_1,…,−q_k)_L`. For example `(3,1;4)_R → (bar(3),1;−4)_L`. All non-Abelian factors must be conjugated, not only hypercharge negated. A 4D Dirac multiplet is two LH rows in R and conjugate(R); a Majorana field is one independent LH Weyl row with its source conjugacy condition retained. Neither operation creates a new model entry. Unknown source handedness leaves the gauge assignment versus its conjugate unresolved and blocks an exact fingerprint.

The NMSSM singlet chiral supermultiplet expands to two rows: scalar `(0,0)` with **two real-module copies** and Weyl `(1/2,0)` with **one copy**, both in `(1,1;0)` under g_SM. Auxiliary fields and dependent conjugates are not new rows.

Higher dimensions use complexified Lorentz B/D Dynkin labels in standard vector-first/spinor-last node order. A 5D spinor has B2 label [0,1], not a 4D chirality label. A 6D chiral spinor with unrecorded chirality is explicitly ambiguous between the two D3 spinor nodes. Brane fields are distinguished from ambient bulk fields. Ordinary non-bulk descriptions whose original dimension column was NULL currently have a labelled **editorial 4D interpretation**, visible in provenance and exported per-field scope metadata; this is not a newly checked source assertion. Unresolved bulk or parameterized dimensions stay unresolved. No KK reduction is inferred.

### Reusable entry format and duplicate checks

`entry.schema.json` specifies complete candidate inputs: `schema_version`, `inventory_complete`, canonical `gauge_factors`, and `matter` rows with `lorentz`, `reality`, `copies`, and per-factor `gauge_representations`. Labels and paper IDs are metadata, not identity. Dynkin labels are required for non-Abelian factors; charges are exact rational strings and normalized jointly over the full inventory. Runtime checks reject missing factors, unresolved chirality/counts, invalid ranks and inconsistent Lorentz labels.

Run the read-only check **before creating an entry**:

```sh
python3 atlas/check_entry.py atlas/examples/two-higgs-doublets.json
python3 atlas/check_entry.py candidate.json --database website/downloads/field-catalogue.sqlite
```

Before that duplicate check, the extraction agent must establish the source facts and normalize the complete numerical candidate:

```sh
python3 atlas/prepare_entry.py candidate.json --database website/downloads/field-catalogue.sqlite
python3 atlas/prepare_entry.py normalized.json --require-normalized --database website/downloads/field-catalogue.sqlite
```

`prepare_entry.py` emits `normalized_entry`, positive common U(1) conversion scales, and optionally duplicate results. It validates the candidate object shape, fixed Dynkin-label ranks and exact charges, converts identified RH/Dirac descriptions to the LH basis, and applies primitive integer normalization across the full inventory while preserving generator orientation. `--require-normalized` rejects source-shaped candidates still needing conversion. `normalize_spec` is also called before the generator saves complete `entry_identity.input_json` payloads, not only inside fingerprint computation. Raw assertions and source units remain unchanged in provenance.

This is a read-only mathematical preflight, not a PDF-reading agent, source-evidence certificate, or enforced database-write API. Follow the mandatory extraction → normalization → ingestion instructions in `BSM_ATLAS_AGENT_PROMPT.md`. Evidence locators and the actual paper inspection remain the extracting agent's responsibility. Existing legacy projections are not retroactively validated by this change.

**Missing versus free:** `not_extracted` means unfinished agent work; it must stay in staging, not be accepted as a scientific table value. A scientific `?` is reserved for a genuine source omission, recorded as `not_specified_by_source` after inspection of the relevant source scope. A paper's explicit free parameter is a symbolic family with a shared parameter identity, domain and relations, not an unknown number. The current complete numerical preflight rejects both unknown and symbolic values; their dedicated partial/family ingestion schema remains future work. No raw `?`, `q`, `source:2` or extraction-error string belongs in a canonical numerical charge column.

An exact field-content match returns the existing entry ID: add the paper association instead of creating a duplicate. The database's `content_signatures.fingerprint` is a primary key. `entry_identity` maps existing IDs to that signature, or records why identity is unresolved. The internal canonical JSON is a deterministic fingerprint encoding (with IDs removed), not another source paper record or the candidate-input format.

The checker canonicalizes row ordering, identical-row copy aggregation, gauge-factor ordering/permutations of repeated factors, common U(1) rational rescalings and independent generator sign flips. It normalizes explicit RH/Dirac inputs to the LH basis. It retains neutral fields and vector-like pairs. Scalar real-module type/weights and all component copy counts contribute to identity. A complex scalar in a real-type irrep and two real copies now have the same identity.

**Limits:** this is field-content identity under the stated schema, not full physical-theory equivalence. General multi-U(1) basis mixing, simple-algebra outer automorphisms and cross-regime dualities are not exhaustively quotiented. A nonmatch returns `no_exact_match_review_required`, never “new model proven.” Partial sectors and unknown inventories get no complete signature; same-algebra candidates still require reconciliation. The current source claims remain unchecked even when a complete structural signature can be computed.

- S is scalar, with source reality explicit. F is a source fermion, with handedness explicit when known; missing handedness stays missing. Identified right-handed four-dimensional Weyl fields are converted to left-handed conjugates, conjugating all factors together.
- F_D is one source Dirac/vector-like multiplet. In four dimensions it is a Weyl pair R ⊕ conjugate(R), not a single chiral fermion. Copies count Dirac multiplets in such a row. No bulk-to-4D dimensional reduction is assumed.
- S+F is one chiral supermultiplet, represented by one complex scalar and one left-handed Weyl fermion in that representation, with no auxiliary fields counted. V is additional vector matter, not an extra copy of the algebra's gauge connections.
- Multiplicity means copies of a multiplet, not its representation dimension. A family charge vector is not collapsed to identical copies. Unknown counts stay NULL/`?`.
- Gauge connections are implied by the algebra. Composite operator collections, spurion backgrounds, field coordinates and mass eigenstates are preserved for provenance but excluded from independent-matter summaries. Different description regimes are never summed into one spectrum.

All baseline templates are explicit presentation definitions, not claims that a source individually re-enumerates them:

| Template | Inventory in left-handed notation; integer q=6Y |
|---|---|
| F_SM | 3 copies each of Q=([1,0],[1];1), u^c=([0,1],[0];−4), d^c=([0,1],[0];2), L=([0,0],[1];−3), e^c=([0,0],[0];6) |
| H_SM | One complex scalar H=([0,0],[1];3) |
| R_SM | F_SM ⊕ H_SM; no right-handed neutrino |
| R_MSSM | Three chiral families Q,u^c,d^c,L,e^c, two Higgs chiral multiplets (1,2;±3), and adjoint gluino/wino/bino Weyl multiplets; replaces R_SM |

Two-Higgs-doublet summaries use F_SM plus two doublets, not R_SM plus two more doublets. NMSSM uses R_MSSM plus a singlet chiral multiplet. Baseline-parent navigation alone does not silently import a full spectrum into a partial variant.

## Saved schema and provenance

`FIELD_CONTENT_CATALOGUE.json` and the website JSON contain entries, independently listed papers, templates and preserved reference records. Entry → source variants → regimes → fields retains all 125 original model IDs and all 573 source field IDs, including excluded-coordinate rows. Grouping, exclusions, baseline decisions and source-specific charge conversions live in `field_content_curations.json`. Exact source assertions and passage locators remain attached; none are promoted to checked.

The separate `website/downloads/field-catalogue.sqlite` has:

| Table | Main columns |
|---|---|
| entries | entry_id, name, gauge_algebra (primary display), baseline, coverage, source_variants_json |
| papers | paper_id, arxiv_version, title, inspection_status, review_status |
| entry_papers | entry_id, paper_id; many-to-many links, no minimum association count |
| regimes | regime_id, entry_id, source_model_id, description, spacetime_dimension, gauge_algebra, baseline, factors_json, notes_json |
| multiplets | multiplet_id, entry_id, source_model_id, regime_id, field_label, field_types, representation, copies, representation_dimension, source_field_id, source_rows_json, components_json, evidence_json |
| spacetime_representations | representation_id, multiplet_id, component_kind, spacetime_dimension, lorentz_algebra, representation_label, status, representation_json, copies; canonical component counts, separate component rows, including conjugateGauge metadata |
| component_gauge_representations | component_id, factor_key, algebra_id, role, dynkin_json, charge, representation_label, status; charge is an exact integer string or NULL with a database CHECK constraint, original expressions remain provenance; actual per-component assignments after LH conversion, not just a flag requesting later conjugation |
| content_signatures | fingerprint (unique primary key), schema_version, canonical_json, canonical_entry_id |
| entry_identity | entry_id, status, reason, fingerprint, algebra_signature, input_json |
| identity_migrations | entry_id, old_schema, old_fingerprint, new_schema, new_fingerprint, reason |
| metadata | Convention version, source checksum, scope, explicit templates, scalar_convention_json |

`source_rows_json` retains the full projected field object, including inherited/excluded flags, original notation, chirality/reality, normalization conversions and evidence. Thus a raw multiplet count is not an independent-particle count. The CSV is a primary-regime summary; JSON/SQLite preserve separate regimes. Excluded reference structural records are in JSON and the original source DB, not the BSM `entries` table.

Rebuild with `python3 website/build_field_catalogue.py`; use `--check` to detect stale generated text outputs. Tests check the immutable source hash, paper/model separation (especially R01), all source-ID coverage, exact arithmetic, normalization scope, and SQLite/JSON roundtrips. They are data/convention tests, not an anomaly, embedding, completeness or viability certificate. Do not feed partial inventories to an AI search as complete spectra.

### Corrections in version 2

The two standard 2HDM Higgs doublets now explicitly have colour representation 1, giving `(1,2;3)` each. This is a field-specific, documented correction supported by P03, not a rule filling every missing colour slot with 1. Source assertions and the original SQLite remain unchanged; the completion is stored separately with its locator. Concise model display names retain full source labels in variants/provenance.

### Notation decision in version 3

Make Dynkin labels the canonical stored identifiers and CSV summary notation, with explicit node numbering. Keep physics dimension shorthand as the website default, with a visible notation switch, in-cell comparisons, derived Young diagrams and gauge-algebra Dynkin diagrams. Preserve original labels in provenance. No new source identifications, model merges or scalar-realification conversions are implied by this display migration. That was a notation-only release. The version-4 real-module migration below implements the separate scalar-counting equivalence.
