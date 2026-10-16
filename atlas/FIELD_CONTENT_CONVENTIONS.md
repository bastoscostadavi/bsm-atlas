# Gauge-algebra and matter catalogue

Version `gauge-matter-1`, October 16, 2026. This is a read-only, source-scoped projection, not a replacement of `atlas.sqlite` or a new physics review. The website deliberately exposes just this smaller catalogue.

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
| metadata | Convention version, source checksum, scope, explicit templates |

`source_rows_json` retains the full projected field object, including inherited/excluded flags, original notation, chirality/reality, normalization conversions and evidence. Thus a raw multiplet count is not an independent-particle count. The CSV is a primary-regime summary; JSON/SQLite preserve separate regimes. Excluded reference structural records are in JSON and the original source DB, not the BSM `entries` table.

Rebuild with `python3 website/build_field_catalogue.py`; use `--check` to detect stale generated text outputs. Tests check the immutable source hash, paper/model separation (especially R01), all source-ID coverage, exact arithmetic, normalization scope, and SQLite/JSON roundtrips. They are data/convention tests, not an anomaly, embedding, completeness or viability certificate. Do not feed partial inventories to an AI search as complete spectra.
