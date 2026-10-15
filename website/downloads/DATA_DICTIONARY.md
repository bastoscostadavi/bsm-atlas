# BSM Atlas data dictionary (SQLite schema version 10)

This is the human-readable contract for the **installed** [schema.sql](schema.sql). It lists every table and column, the row's meaning, and the writer responsible for it. The SQL file remains authoritative for types, `NOT NULL`, checks, keys, indexes, and foreign keys; [SCHEMA.md](SCHEMA.md) records why the design changed. Update this dictionary whenever the SQL schema or agent output contract changes. The paper and model agents receive this dictionary in their prompts. Neither agent writes SQL directly: Python validates and imports their JSON.

## Read these distinctions first

- **A run marked `complete` means its JSON was validated and imported.** It does not certify that the paper was fully read, that all models in it were reconstructed, or that any physics claim was independently checked.
- **A paper profile's `ready_for_model` means the assigned extraction scope has usable assertions and evidence.** Reviews can be selective. `partial` means the assigned scope itself has an important missing source dependency or coverage gap. The paper agent returns `coverage_status = complete | partial | abstract_only | unavailable`; Python maps `complete` to `ready_for_model` in SQLite.
- **A source description is the paper's own description, before model identity is decided.** Its `completeness_status` describes the captured source material, not a canonical model. The model agent can later `defer` a source description even when it is complete for the paper agent's scope.
- **A model specification is a selected structural identity.** Its `completeness_status` is one of the exact labels below. It is not a review or validity verdict. `covered_sectors` and `scope_note` must say what is represented and missing. A partial template may have a stable model ID without being a complete physical theory.
- **`review_status` and `reconciliation_status` are different.** The first records independent checking of paper claims; the second records confidence in a model identity or relationship. The initial corpus has `unchecked` claims and `provisional` links. Do not promote either just because an agent run succeeded.
- **Null means unknown, unstated, or inapplicable only when the accompanying status/scope makes that clear.** Do not interpret an omitted field, operator, charge, global quotient, or term as physically absent. Preserve source notation and state any normalization rule.
- **IDs are versioned at two different levels.** `paper_id` identifies a publication; `paper_version_id` identifies its pinned text. `(model_id, revision)` identifies an atlas specification revision, which does not change merely because an arXiv version changes.

### Enforced completeness labels

Both `completeness_status` columns are `NOT NULL` and have SQLite `CHECK` constraints. The paper JSON schema enforces the source-description choices; the model importer checks the specification choices before insertion. Use exactly one label from the relevant column. Keep the reason, source conflicts, and omissions in the scope and description fields rather than inventing a longer status string.

| Column | Exact value | Use when |
|---|---|---|
| `paper_model_descriptions.completeness_status` | `source_scope_captured` | The construction or scoped example has been captured to the extent the assigned paper and inspected scope state it. A source may itself give only a partial construction; that alone does not make the extraction partial. |
| | `source_scope_partial` | An important part of this source description within the assigned scope could not be reliably captured, for example because of an unreadable equation or unresolved extraction ambiguity. State the gap in `description_scope` or `description_text`. |
| | `reference_only` | The row records a method, software representation, classification overview, or shared convention rather than a source-specific physical construction. A concrete construction mentioned in a review uses one of the other two labels. |
| `theory_specifications.completeness_status` | `defined_for_stated_scope` | The recorded sectors and defining choices specify the selected construction or sector for the stated scope. This does not imply a full theory, a complete UV origin, or independent verification. |
| | `partial_structural_specification` | The row selects a construction or sector, but defining structure within that selected scope is still missing, ambiguous, or represented only at review level. Describe precisely what is missing in `covered_sectors` and `scope_note`. |
| | `framework_or_template` | The row intentionally represents a class, open representation/charge assignment, operator space, or mechanism template with material choices unselected. Do not treat its members as one fixed model. |

For model rows, first ask whether the row intentionally leaves member choices open (`framework_or_template`). Otherwise, ask whether the selected scope's defining structure is recorded (`defined_for_stated_scope`); if it is not, use `partial_structural_specification`. For paper rows, use `reference_only` for non-construction records; then distinguish captured from partial source extraction. `profile.coverage_status` still describes the assigned paper as a whole.

### Other status and label policy

| Field | Current contract and interpretation |
|---|---|
| Paper JSON `profile.coverage_status` | Enforced enum: `complete` (assigned scope captured), `partial`, `abstract_only`, `unavailable`. |
| SQLite `paper_profiles.extraction_status` | Python maps the above to `ready_for_model`, `partial`, `abstract_only`, `unavailable`; `not_started` is the table default. This is extraction state, not model or review state. |
| `paper_profiles.review_status`, `paper_summary_revisions.review_status`, `paper_model_descriptions.review_status`, `paper_assertions.review_status` | Initially `unchecked`. Change only after an independent review procedure; do not use this to describe extraction coverage. The SQL currently does not constrain the later review vocabulary. |
| `paper_model_descriptions.completeness_status` | Enforced source-description vocabulary above; describes source-side capture, not whether a canonical model can be created. |
| `theory_specifications.completeness_status` | Enforced structural vocabulary above; exact sectors and gaps belong in `covered_sectors` and `scope_note`. None of the labels means independent verification. |
| `theory_relations.reconciliation_status`, `theory_regime_relations.reconciliation_status`, `paper_theory_links.reconciliation_status` | Default `provisional`. Keep that status until a separate identity review. SQL currently permits other text but the agents must not invent a stronger status. |
| Model JSON `reconciliations[].decision` | Enforced enum: `create` a new specification, `reuse` an existing or same-proposal specification, `scope_only` for a choice/application within a linked construction, `defer` when identity is unresolved or a description is software/reference-only. Explain every decision. |
| `paper_assertions.value_status` | Enforced enum: `specified`, `unspecified_in_scope`, `explicitly_absent`, `not_applicable`, `ambiguous_conflicting`. `explicitly_absent` needs affirmative source support. |
| `paper_assertions.basis` | Enforced enum: `source_stated`, `source_assumed`, `agent_inferred`. An agent inference needs its own conditions and evidence path. |

The 50-paper corpus originally used many free-text labels. The v9 migration reviewed the existing rows individually; [completeness_review_v9.json](completeness_review_v9.json) preserves each previous label and its selected replacement. This migration does not change any source assertion, source evidence, scope note, or scientific review state.

## Shared ID, evidence, and ownership rules

Python owns seed registration in `papers` and `paper_versions`. The paper agent owns profiles, summaries, source descriptions, source assertions and evidence. The model agent owns canonical theory rows, paper–theory links and their support. A source description is not itself a model; a paper can have several descriptions and several roles linking to the same model. A tool paper may have zero physical-model links with `no_model_link_reason`.

Integer primary keys are database row IDs; they do not encode physics meaning. Source evidence is version-specific. `paper_assertion_evidence`, `paper_summary_assertions` and `paper_theory_link_evidence` are many-to-many junctions, not duplicate claims. The importer requires same-version evidence for assertions and model links. `theory_assertion_links.target_kind` is a provisional logical pointer: the Python validator checks the allowed kinds and verifies that `target_id` belongs to the cited model revision. A `specification` target has a null `target_id`.

**Targeted correction of a cited assertion:** `correct_assertion.py` checks the pinned PDF hash and a source-backed proposal, backs up SQLite, keeps the old and new assertion plus evidence IDs in `paper_assertion_corrections`, and queues every existing `theory_assertion_links` citation in `theory_assertion_rechecks`. The assertion ID and paper-version ID stay fixed. Its claim and any linked summaries return to `unchecked`; model rows stay unchanged until a curator inspects each queued target. `recheck_assertion.py` shows the corrected claim, evidence and target row, then records `confirmed` or `model_change_needed` with a reason. `pending` and `model_change_needed` require follow-up; a recorded decision is not an independent physics certification. The ordinary whole-paper reset still refuses linked or corrected paper extractions.

## Python-owned registration

### `papers` — one row per publication

| Column | Meaning |
|---|---|
| `paper_id` | Stable seed ID such as `P03`; primary key. |
| `arxiv_id` | Versionless arXiv identifier; unique. |
| `source_kind` | Seed classification: `model`, `review`, `classification`, `tool`, or `auxiliary`; this is not a model-completeness label. |

### `paper_versions` — one row per pinned source version

| Column | Meaning |
|---|---|
| `paper_version_id` | Exact source identifier, including version; primary key. |
| `paper_id` | Publication that owns this version. |
| `version_label` | Version suffix or pinned version label; unique together with `paper_id`. |
| `seed_title`, `seed_authors` | Manifest hints, not verified bibliography. |
| `first_arxiv_year` | Year supplied by the seed. |
| `source_url`, `pdf_url` | Pinned landing-page and PDF links. |
| `local_filename` | Filename under `atlas/papers/`. |
| `intended_scope` | Seed instructions for what to extract from this version. |
| `local_pdf_status` | Local availability/header check, not scientific or origin verification. |
| `pdf_sha256`, `pdf_size_bytes` | Hash and size of the local PDF used for the run. |

## Paper-agent-owned source records

### `paper_profiles` — one source-version profile

| Column | Meaning |
|---|---|
| `paper_version_id` | Pinned version; primary key. |
| `verified_title`, `verified_authors` | Bibliography read from the pinned source, distinct from seed hints. |
| `doi`, `first_submitted_date`, `version_date` | Source-supported identifiers/dates; null when not established. |
| `author_abstract` | Authors' abstract, separate from the generated summary. |
| `inspected_scope` | Pages/sections actually supplied and examined for this extraction. |
| `extraction_limitations` | Missing pages, damaged math text, uninspected references, deferred variants and other limits. |
| `extraction_status` | Python-mapped source coverage state, explained above. |
| `review_status` | Independent scientific review state; initially `unchecked`. |
| `no_model_link_reason` | Why no physical-model association is expected, especially for tool/method papers. |
| `extraction_run_id`, `updated_at` | Saved paper-agent run identity and import time. |

### `paper_summary_revisions` — generated summary for one version

| Column | Meaning |
|---|---|
| `summary_id` | Summary row ID. |
| `paper_version_id` | Paper profile summarized. |
| `revision` | Summary revision number within this paper version. |
| `summary_text` | Agent-written summary of inspected content; never the author abstract. |
| `coverage_note` | Scope and omissions of this summary. |
| `generated_at`, `extraction_run_id` | Creation time and originating paper-agent run. |
| `review_status`, `review_note` | Independent summary review state and any reviewer explanation. |

### `paper_summary_assertions` — summary-to-claim support

| Column | Meaning |
|---|---|
| `summary_id` | Supported generated summary. |
| `assertion_id` | Detailed source assertion supporting a substantive summary claim. |
| `paper_version_id` | Shared version for both IDs; composite foreign keys enforce agreement. |

### `paper_model_descriptions` — what this source calls a construction

| Column | Meaning |
|---|---|
| `description_id` | Source-description row ID. |
| `paper_version_id` | Pinned version containing this description. |
| `source_label` | Source-specific name or symbol; not a canonical model ID. |
| `description_scope` | Variant, regime, example or sector covered by the row. |
| `completeness_status` | Exactly one of the three source-description labels above; how this paper's description was captured. |
| `description_text` | Source-specific structural prose, uncertainties and restrictions. |
| `extraction_run_id`, `review_status` | Originating run and independent review state. |

### `paper_assertions` — one attributable source claim

| Column | Meaning |
|---|---|
| `assertion_id` | Source-assertion row ID. |
| `paper_version_id` | Exact text that made the claim. |
| `description_id` | Optional source description to which this claim belongs; must be in the same version. |
| `claim_kind` | Kind of claim, such as field, interaction, result, assumption or mechanism; currently free text. |
| `subject_label`, `property_name` | Source-specific subject and the property being asserted. |
| `claim_text` | Atomic claim in readable form. |
| `source_value` | Original value, symbol or statement as written. |
| `normalized_value`, `normalization_rule` | Optional converted form and the explicit conversion; the latter is required when the former is present. |
| `conditions` | Parameter, phase, approximation or other qualifications. |
| `value_status` | Enforced distinction among specified, unspecified, absent, inapplicable and conflicting. |
| `basis` | Whether stated, assumed by the source, or inferred by the agent. |
| `review_status`, `review_note` | Independent review state and explanation. |
| `extraction_run_id` | Paper-agent run that produced this claim. |

### `evidence_refs` — one exact source location

| Column | Meaning |
|---|---|
| `evidence_id` | Evidence-location row ID. |
| `paper_version_id` | Exact version containing the location. |
| `locator_type` | Equation, table, section, figure or passage type; currently free text. |
| `locator` | Precise source locator, such as `§2, eq. (3)`. |
| `pdf_page`, `printed_page` | One-based PDF page and, where available, printed page. |
| `excerpt` | Short source excerpt, when useful. |
| `note` | Locator or text-extraction qualification. |

### `paper_assertion_evidence` — exact evidence for a claim

| Column | Meaning |
|---|---|
| `assertion_id` | Paper assertion being supported. |
| `evidence_id` | Supporting source location. |
| `paper_version_id` | Same version on both sides; composite foreign keys enforce it. |

### `paper_assertion_corrections` — audit of a targeted source correction

| Column | Meaning |
|---|---|
| `correction_id` | Stable ID for this source correction and its model recheck queue. |
| `assertion_id` | Existing paper assertion being corrected; its row ID is preserved. |
| `old_snapshot_json`, `new_snapshot_json` | Full before/after assertion values and supporting evidence IDs. |
| `reason`, `created_at` | Source-grounded reason and UTC correction time. |

## Model-agent-owned identity and description records

The model agent proposes `rows` for these tables, plus one reconciliation decision for **every** target `paper_model_descriptions` row. Python inserts only after checking the proposed column names, foreign keys, source-support paths and exact link evidence. New specifications and source-linkable structural components need `theory_assertion_links` support from the assigned target paper; family and alias rows have no typed support target in the current schema. A distinct vacuum or benchmark alone does not require a new model ID.

### `theory_families` — named family hierarchy

| Column | Meaning |
|---|---|
| `family_id` | Stable family key; primary key, not a model specification. |
| `display_name` | Readable family name. |
| `parent_family_id` | Optional broader family, referring to another family row. |
| `scope_note` | What this family label includes or excludes. |

### `theory_specifications` — one canonical model revision

| Column | Meaning |
|---|---|
| `model_id` | Stable lowercase model identifier, shared across atlas revisions. |
| `revision` | Atlas structural revision number; together with `model_id` the primary key. |
| `display_name` | Readable model/specification name. |
| `family_id` | Optional family membership. |
| `completeness_status` | Exactly one of the three model-specification labels above; selected structural scope, not scientific review. |
| `covered_sectors` | Explicitly represented physics sectors, not an assertion of a full theory. |
| `scope_note` | Missing sectors, alternatives, source limits and identity qualifications. |
| `baseline_label` | Named inherited baseline such as SM or MSSM, if the source uses one. |
| `baseline_status` | `explicit`, `unresolved`, or `not_applicable`; null if no decision was made. |
| `baseline_model_id`, `baseline_model_revision` | Optional exact canonical specification used as a baseline; both identify the same referenced revision. |

### `theory_aliases` — alternate names for a specification

| Column | Meaning |
|---|---|
| `model_id`, `model_revision` | Specification owning the alias. |
| `alias` | Alternate name or source-used spelling; unique per revision. |
| `alias_kind` | Why the alias is used, such as acronym or source label; free text. |

### `theory_assumptions` — defining or conditional assumptions

| Column | Meaning |
|---|---|
| `assumption_id` | Assumption row ID. |
| `model_id`, `model_revision` | Specification to which it applies. |
| `statement` | Exact assumption, without silently making it a theorem. |
| `assumption_kind` | Structural, parameter, validity or other source-qualified type; free text. |
| `status` | Whether assumed, derived, unresolved or otherwise qualified; currently free text. |

### `theory_regimes` — one description of a model

| Column | Meaning |
|---|---|
| `regime_id` | Description-regime row ID. |
| `model_id`, `model_revision` | Specification described in this regime. |
| `spacetime_dimension` | Source-stated dimension, such as four- or five-dimensional; preserve conventions. |
| `description_kind` | Elementary, composite, effective, microscopic or other scoped description; free text. |
| `eft_truncation` | Operator order, energy expansion or retained terms if this is an EFT. |
| `validity_assumptions` | Cutoff, hierarchy, weak-coupling or other conditions for the description. |
| `geometry_boundary_notes` | Bulk, compactification, interval, brane and boundary context. |

### `theory_boundaries` — named boundary of a regime

| Column | Meaning |
|---|---|
| `boundary_id` | Boundary row ID. |
| `model_id`, `model_revision`, `regime_id` | The exact regime that owns this boundary. |
| `boundary_label` | Name such as UV brane, IR brane or orbifold endpoint; unique within a regime. |
| `position_expression` | Coordinate or geometric location in source notation. |
| `residual_symmetry` | Symmetry left at that boundary when stated. |
| `scope_note` | Boundary conditions or uncertainty not represented elsewhere. |

### `theory_regime_relations` — correspondence between two regimes

| Column | Meaning |
|---|---|
| `relation_id` | Relation row ID. |
| `model_id`, `model_revision` | Shared specification containing both regimes. |
| `from_regime_id`, `to_regime_id` | Distinct regimes being compared, both inside the same revision. |
| `relation_kind` | Matching, dual interpretation, reduction or other stated relation; free text. |
| `scope_note` | Conditions and limits; a relation is not unconditional equivalence. |
| `reconciliation_status` | Initially `provisional`; separate from paper review. |

## Model-agent-owned gauge and field records

### `theory_gauge_groups` — gauge group at one regime

| Column | Meaning |
|---|---|
| `group_id` | Gauge-group row ID. |
| `model_id`, `model_revision`, `regime_id` | Regime in which this group is stated. |
| `group_label` | Source name or product expression. |
| `global_form_status` | `stated_direct_product`, `stated_quotient`, `stated_other`, `unspecified_in_scope`, or `not_applicable`; a factor list alone does not fix the global quotient. |
| `global_form_expression` | Exact direct-product/quotient expression when actually given. |
| `normalization_note` | Gauge-generator, hypercharge or coupling convention. |

### `theory_gauge_factors` — one factor of a stated group

| Column | Meaning |
|---|---|
| `factor_id` | Gauge-factor row ID. |
| `model_id`, `model_revision`, `regime_id`, `group_id` | Parent group and regime; composite foreign key prevents cross-regime assignment. |
| `factor_order` | Display order in the source's group expression. |
| `factor_label` | Named factor such as `SU(2)_L`; not a global-form assertion. |
| `normalization_convention` | Factor-specific charge or generator normalization. |
| `embedding_note` | Embedding within a larger group or breaking chain, if supported. |

### `theory_fields` — physical or explicitly typed source field

| Column | Meaning |
|---|---|
| `field_id` | Field row ID. |
| `model_id`, `model_revision`, `regime_id` | Exact regime containing the field. |
| `field_label` | Source symbol/name; clarify if it denotes a multiplet rather than a component. |
| `field_kind` | Scalar, fermion, gauge boson, superfield, composite, etc.; currently free text. |
| `spin`, `chirality`, `multiplicity` | Source-specified spin, handedness and number of copies; do not infer unstated generations. |
| `field_reality_condition` | Imposed real/Majorana or other field condition, distinct from representation reality. |
| `inherited_baseline_label` | Baseline field content referenced but not duplicated, if explicit. |
| `scope_note` | Component, flavor, effective/microscopic or inventory qualifications. |

### `theory_field_representations` — field action under group or factor

| Column | Meaning |
|---|---|
| `representation_id` | Representation row ID. |
| `model_id`, `model_revision`, `regime_id`, `field_id` | Field and its regime. |
| `factor_id`, `group_id` | **Exactly one** is non-null: factor-specific representation or representation under the whole group. Do not invent factors when the source only says “singlet.” |
| `representation_label` | Source representation label, including conjugation marks. |
| `representation_reality` | Real, complex, pseudoreal or unknown property of the representation, not of the field. |
| `exact_charge` | Stated Abelian charge, possibly symbolic. |
| `source_notation` | Original tuple, symbol or table notation. |
| `normalization_note` | Charge convention and any qualified conversion. |

### `theory_field_boundary_conditions` — one component's boundary rule

| Column | Meaning |
|---|---|
| `condition_id` | Boundary-condition row ID. |
| `model_id`, `model_revision`, `regime_id`, `field_id`, `boundary_id` | Field and boundary in the same regime. |
| `field_component_label` | Component of the field, if boundary rules differ within a multiplet. |
| `chirality` | Chirality to which the boundary rule applies. |
| `condition_kind` | Dirichlet, Neumann, parity or other source-stated rule. |
| `source_notation` | Original signs or symbols, such as `(+,−)`. |
| `scope_note` | Qualification or unresolved convention. |

## Model-agent-owned symmetries, interactions, and vacua

### `theory_symmetries` — one named symmetry in one regime

| Column | Meaning |
|---|---|
| `symmetry_id` | Symmetry row ID. |
| `model_id`, `model_revision`, `regime_id` | Regime in which the symmetry acts. |
| `symmetry_label` | Source name/group or transformation label. |
| `internal_or_spacetime` | Whether the symmetry acts internally or on spacetime, when relevant. |
| `global_or_gauged` | Global/gauged distinction; do not infer gauging from a group name. |
| `imposed_or_accidental` | Source-stated or argued origin. |
| `breaking_status` | Assumed or established breaking, exactness, residual action or uncertainty. |
| `anomaly_statement` | Source's anomaly claim or qualification, not independent verification. |

### `theory_symmetry_actions` — transformation of a field

| Column | Meaning |
|---|---|
| `action_id` | Action row ID. |
| `model_id`, `model_revision`, `regime_id`, `symmetry_id`, `field_id` | Symmetry and field in the same regime. |
| `transformation_rule` | Field transformation, parity or representation rule. |
| `exact_charge` | Charge under this symmetry, when explicit. |
| `conditions` | Phase, parameter, basis or validity qualification. |

### `theory_interactions` — one operator or interaction class

| Column | Meaning |
|---|---|
| `interaction_id` | Interaction row ID. |
| `model_id`, `model_revision`, `regime_id` | Regime containing the operator. |
| `operator_label` | Source label or readable interaction name. |
| `interaction_kind` | Gauge, Yukawa, scalar potential, mass, soft term, effective operator, etc.; free text. |
| `expression`, `source_notation` | Canonicalized expression when justified and source's original notation. |
| `allowed_by_symmetry` | Nullable 0/1: whether symmetries permit the term. |
| `included_in_specification` | Nullable 0/1: whether this specification actually includes the term. |
| `set_to_zero_by_assumption` | Nullable 0/1: explicit assumption setting an otherwise possible coefficient to zero. |
| `coefficient_restriction` | Equality, reality, flavor or other coefficient restriction. |
| `assumptions` | Conditions for the operator or its use. The three 0/1 flags are not interchangeable. |

### `theory_interaction_participants` — queryable fields in an operator

| Column | Meaning |
|---|---|
| `participant_id` | Participant row ID. |
| `model_id`, `model_revision`, `regime_id`, `interaction_id`, `field_id` | Operator and field in the same regime. |
| `participant_role` | Role such as left-handed fermion, Higgs, mediator or conjugate; unique with interaction and field. |
| `source_notation` | Symbol or conjugation used for this participant. |

### `theory_parameters` — one named coefficient or parameter

| Column | Meaning |
|---|---|
| `parameter_id` | Parameter row ID. |
| `model_id`, `model_revision` | Owning specification. |
| `interaction_id` | Optional operator to which the parameter belongs; must be in this specification. |
| `symbol` | Parameter name as used or normalized. |
| `definition` | Meaning, dimensionality or expression. |
| `normalization_convention` | Factor, sign, basis or coupling normalization. |
| `restriction` | Structural restriction, range or conditional relation. |
| `value_status` | Whether a value is specified, free, assumed or unresolved; currently free text, so explain it explicitly. |

### `theory_vacua` — one phase or vacuum description

| Column | Meaning |
|---|---|
| `vacuum_id` | Vacuum row ID. |
| `model_id`, `model_revision`, `regime_id` | Regime for which this vacuum is described. |
| `vacuum_label` | Source name or readable phase label. |
| `phase_assumptions` | Chosen phase, condensate or symmetry-breaking assumptions. |
| `parameter_assumptions` | Region or benchmark needed for this vacuum. |
| `status` | Source-assumed, demonstrated, metastable, unresolved, etc.; free text and must not imply proof without evidence. |

### `theory_breaking_steps` — ordered symmetry-breaking step

| Column | Meaning |
|---|---|
| `step_id` | Breaking-step row ID. |
| `model_id`, `model_revision`, `vacuum_id` | Vacuum containing this step. |
| `step_order` | Order along the stated chain, when given. |
| `order_parameter` | VEV, condensate, boundary condition or other source-stated order parameter. |
| `from_symmetry`, `residual_symmetry` | Before and after symmetry labels. |
| `assumed_or_established` | Whether the transition/phase is assumed or established by the source; free text. |

## Model-agent-owned relationships and source support

### `theory_relations` — between two model revisions

| Column | Meaning |
|---|---|
| `relation_id` | Relation row ID. |
| `from_model_id`, `from_revision` | First specification revision. |
| `to_model_id`, `to_revision` | Second specification revision. |
| `relation_kind` | Restriction, extension, correspondence, alternative or other qualified relationship; free text. |
| `scope_note` | Exact overlap, differences, assumptions and unresolved comparisons. |
| `reconciliation_status` | Initially `provisional`, pending independent identity review. |

### `theory_assertion_links` — source support for a canonical detail

| Column | Meaning |
|---|---|
| `support_id` | Support-row ID. |
| `model_id`, `model_revision` | Specification being supported, qualified or disputed. |
| `assertion_id` | Paper-agent assertion from the assigned paper, itself linked to evidence. |
| `target_kind` | Logical kind of target: `specification`, `assumption`, `regime`, `boundary`, `regime_relation`, `gauge_group`, `gauge_factor`, `field`, `field_representation`, `field_boundary_condition`, `symmetry`, `symmetry_action`, `interaction`, `interaction_participant`, `parameter`, `vacuum`, `breaking_step`, or `model_relation`. The Python validator checks this list. |
| `target_id` | Integer ID of the target component; null for `specification`. The validator checks that the ID belongs to the cited revision. |
| `subject_label`, `property_name` | Precise canonical subject and property to which the assertion applies. |
| `support_stance` | Enforced `supports`, `disputes`, or `qualifies`. |
| `decision_note` | Why this source evidence supports or limits the canonical choice. |

### `theory_assertion_rechecks` — one affected model citation per correction

| Column | Meaning |
|---|---|
| `correction_id`, `support_id` | The corrected assertion and exact source-to-model citation requiring review; together the primary key. |
| `status` | `pending` until inspected; `confirmed` if the target still agrees; `model_change_needed` if the target must be revised. The latter remains an open repair item. |
| `decision_note`, `reviewed_at` | Required explanation and UTC time once a decision is recorded. |

### `paper_theory_links` — one contribution role of a paper version

| Column | Meaning |
|---|---|
| `link_id` | Paper–model link row ID. |
| `paper_version_id` | Exact source version doing the work. |
| `description_id` | Optional same-version source description being reconciled. |
| `model_id`, `model_revision` | Canonical specification revision discussed. |
| `role` | Source contribution role, such as introduces, reviews, calculates or constrains; free text and not historical priority by itself. |
| `source_model_label` | Label used in this paper, distinct from canonical `model_id`. |
| `contribution_summary` | What this version does with this specification. |
| `scope_note` | Limits, parameter assumptions and source-specific qualifications. |
| `reconciliation_status` | Initially `provisional`; a successful import does not promote it. |

### `paper_theory_link_evidence` — exact evidence for a contribution link

| Column | Meaning |
|---|---|
| `link_id` | Supported paper–model role row. |
| `evidence_id` | Exact source location supporting this role. |
| `paper_version_id` | Same pinned version on both sides; composite foreign keys enforce agreement. |

## Agent output versus database rows

The paper agent returns the keys in [paper_agent_output.schema.json](../agents/paper-agent/paper_agent_output.schema.json), not literal INSERT statements. Python assigns integer IDs, maps `profile.coverage_status` to `paper_profiles.extraction_status`, creates `paper_summary_assertions` from `summary_assertion_keys`, creates evidence junctions from each assertion's `evidence` list, and stores deferred variants and auxiliary citations in `extraction_limitations`. It stamps run IDs, times and initial review states. Therefore the paper agent should explain scope and provenance in its JSON and leave canonical identity to the model agent.

The model agent returns the keys in [model_agent_output.schema.json](../agents/model-agent/model_agent_output.schema.json). Its `reconciliations` list accounts for every source description; its `rows` list names model-owned SQL tables and exact columns. Python validates allowed columns, assigned-paper source assertions, foreign keys, exact link evidence and whole-atlas integrity, then commits atomically. A `defer` decision does **not** delete the paper description or mean the paper run failed. A `scope_only` decision records a parameter, vacuum, application or other aspect inside an already linked construction. The saved proposal and `open_questions` remain the audit trail for unresolved choices.
