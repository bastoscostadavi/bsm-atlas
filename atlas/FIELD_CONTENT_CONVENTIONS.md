# Gauge-algebra and matter catalogue

Version `gauge-matter-2`, October 16, 2026. This is a source-scoped projection with explicit curated corrections, not a replacement of `atlas.sqlite` or a new full physics review. The website deliberately exposes just this smaller catalogue.

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

`(3, 2; 1)` denotes non-Abelian irreps in factor-slot order followed by Abelian charges in slot order. A question mark is unresolved, **not a singlet or zero**. Original representations, exact charges and normalization notes remain alongside the conversion.

Dynkin labels are the canonical irrep identifiers where unambiguous. The implemented A-series chain convention has fundamental `[1,0,…,0]` and conjugate `[0,…,0,1]`; SU(2) dimension d has label `[d−1]`. Familiar SU(3) 6/10 and their conjugates are converted conservatively. Dimensions do not uniquely identify all irreps: ambiguous cases, including SO spinor conventions, remain unconverted. A-series Young row lengths are sums of the Dynkin labels to the right; they are a derived display, not an additional identity rule.

For each concrete U(1) assignment, one positive common rescaling makes charges integral with gcd 1. Field labels and the source generator orientation are retained; fields are not sorted into an unlabeled charge set. A declared SM reference supplies its charge unit. Ordinary textbook hypercharge uses **q = 6Y**; sources with Q=T3+Y_source/2 instead use q=3Y_source. The corresponding coupling is g_atlas=g_source/scale.

An incomplete or symbolic assignment is not normalized using an arbitrary numeric subset. For example, incomplete left–right fermion charges prevent dividing the displayed scalar B−L charges by 2: they remain `source:2` until a shared primitive unit is established. All-zero charges alone do not define a unit. Multiple U(1) basis changes and kinetic mixing are not resolved by separate gcd rescalings. The JSON records each factor's normalization status, scale, reference and scope.

## Matter and baselines

The website uses **one matrix per entry**: rows are independent matter representations, columns are spacetime and the actual gauge-algebra factors, followed by copies. A direct SM factor is shown as g_SM; an SM subgroup embedded inside SU(5), SU(4), etc. is not appended as a second gauge factor. Identical resolved rows in one regime combine their copy counts. Source variants and separate regimes never become duplicated simultaneous spectra. Baseline rows expand on demand.

### Lorentz convention: all 4D Weyl fields are left-handed

The machine convention is `lorentz-field-1`. Four-dimensional labels are (j_L,j_R) for finite-dimensional representations of Spin^+(1,3): scalar (0,0), LH Weyl (1/2,0), vector (1/2,1/2). These are **field representations**, not on-shell Poincare particle spin/polarization counts. Scalar real/complex conditions are independent metadata.

Every identified RH Weyl field is replaced by its independent LH charge conjugate: `(R; q_1,…,q_k)_R → (conjugate(R); −q_1,…,−q_k)_L`. For example `(3,1;4)_R → (bar(3),1;−4)_L`. All non-Abelian factors must be conjugated, not only hypercharge negated. A 4D Dirac multiplet is two LH rows in R and conjugate(R); a Majorana field is one independent LH Weyl row with its source conjugacy condition retained. Neither operation creates a new model entry. Unknown source handedness leaves the gauge assignment versus its conjugate unresolved and blocks an exact fingerprint.

The NMSSM singlet chiral supermultiplet expands to two rows: a complex scalar `(0,0)` and a Weyl fermion `(1/2,0)`, both in `(1,1;0)` under g_SM. Auxiliary fields and dependent conjugates are not new rows.

Higher dimensions use complexified Lorentz B/D Dynkin labels in standard vector-first/spinor-last node order. A 5D spinor has B2 label [0,1], not a 4D chirality label. A 6D chiral spinor with unrecorded chirality is explicitly ambiguous between the two D3 spinor nodes. Brane fields are distinguished from ambient bulk fields. Ordinary non-bulk descriptions whose original dimension column was NULL currently have a labelled **editorial 4D interpretation**, visible in provenance and exported per-field scope metadata; this is not a newly checked source assertion. Unresolved bulk or parameterized dimensions stay unresolved. No KK reduction is inferred.

### Reusable entry format and duplicate checks

`entry.schema.json` specifies complete candidate inputs: `schema_version`, `inventory_complete`, canonical `gauge_factors`, and `matter` rows with `lorentz`, `reality`, `copies`, and per-factor `gauge_representations`. Labels and paper IDs are metadata, not identity. Dynkin labels are required for non-Abelian factors; charges are exact rational strings and normalized jointly over the full inventory. Runtime checks reject missing factors, unresolved chirality/counts, invalid ranks and inconsistent Lorentz labels.

Run the read-only check **before creating an entry**:

```sh
python3 atlas/check_entry.py atlas/examples/two-higgs-doublets.json
python3 atlas/check_entry.py candidate.json --database website/downloads/field-catalogue.sqlite
```

An exact field-content match returns the existing entry ID: add the paper association instead of creating a duplicate. The database's `content_signatures.fingerprint` is a primary key. `entry_identity` maps existing IDs to that signature, or records why identity is unresolved. The internal canonical JSON is a deterministic fingerprint encoding (with IDs removed), not another source paper record or the candidate-input format.

The checker canonicalizes row ordering, identical-row copy aggregation, gauge-factor ordering/permutations of repeated factors, common U(1) rational rescalings and independent generator sign flips. It normalizes explicit RH/Dirac inputs to the LH basis. It retains neutral fields and vector-like pairs. Scalar reality and all copy counts contribute to identity.

**Limits:** this is field-content identity under the stated schema, not full physical-theory equivalence. General multi-U(1) basis mixing, simple-algebra outer automorphisms, alternate scalar realifications and cross-regime dualities are not exhaustively quotiented. A nonmatch returns `no_exact_match_review_required`, never “new model proven.” Partial sectors and unknown inventories get no complete signature; same-algebra candidates still require reconciliation. The current source claims remain unchecked even when a complete structural signature can be computed.

- S is scalar, with source reality explicit. F is a source fermion, with handedness explicit when known; missing handedness stays missing. Identified right-handed four-dimensional Weyl fields are converted to left-handed conjugates, conjugating all factors together.
- F_D is one source Dirac/vector-like multiplet. In four dimensions it is a Weyl pair R ⊕ conjugate(R), not a single chiral fermion. Copies count Dirac multiplets in such a row. No bulk-to-4D dimensional reduction is assumed.
- S+F is one chiral supermultiplet, represented by one complex scalar and one left-handed Weyl fermion in that representation, with no auxiliary fields counted. V is additional vector matter, not an extra copy of the algebra's gauge connections.
- Multiplicity means copies of a multiplet, not its representation dimension. A family charge vector is not collapsed to identical copies. Unknown counts stay NULL/`?`.
- Gauge connections are implied by the algebra. Composite operator collections, spurion backgrounds, field coordinates and mass eigenstates are preserved for provenance but excluded from independent-matter summaries. Different description regimes are never summed into one spectrum.

All baseline templates are explicit presentation definitions, not claims that a source individually re-enumerates them:

| Template | Inventory in left-handed notation; integer q=6Y |
|---|---|
| F_SM | 3 copies each of Q=(3,2;1), u^c=(bar(3),1;−4), d^c=(bar(3),1;2), L=(1,2;−3), e^c=(1,1;6) |
| H_SM | One complex scalar H=(1,2;3) |
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
| spacetime_representations | representation_id, multiplet_id, component_kind, spacetime_dimension, lorentz_algebra, representation_label, status, representation_json; separate component rows, including conjugateGauge metadata |
| component_gauge_representations | component_id, factor_key, algebra_id, role, dynkin_json, charge, representation_label, status; actual per-component assignments after LH conversion, not just a flag requesting later conjugation |
| content_signatures | fingerprint (unique primary key), schema_version, canonical_json, canonical_entry_id |
| entry_identity | entry_id, status, reason, fingerprint, algebra_signature, input_json |
| metadata | Convention version, source checksum, scope, explicit templates |

`source_rows_json` retains the full projected field object, including inherited/excluded flags, original notation, chirality/reality, normalization conversions and evidence. Thus a raw multiplet count is not an independent-particle count. The CSV is a primary-regime summary; JSON/SQLite preserve separate regimes. Excluded reference structural records are in JSON and the original source DB, not the BSM `entries` table.

Rebuild with `python3 website/build_field_catalogue.py`; use `--check` to detect stale generated text outputs. Tests check the immutable source hash, paper/model separation (especially R01), all source-ID coverage, exact arithmetic, normalization scope, and SQLite/JSON roundtrips. They are data/convention tests, not an anomaly, embedding, completeness or viability certificate. Do not feed partial inventories to an AI search as complete spectra.

### Corrections in version 2

The two standard 2HDM Higgs doublets now explicitly have colour representation 1, giving `(1,2;3)` each. This is a field-specific, documented correction supported by P03, not a rule filling every missing colour slot with 1. Source assertions and the original SQLite remain unchanged; the completion is stored separately with its locator. Concise model display names retain full source labels in variants/provenance.
