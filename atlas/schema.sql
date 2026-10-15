-- Paper-tested operational BSM Atlas schema. No physics rows are prefilled.
-- Table ownership and meanings: DATABASE_DESIGN.md.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 10;

-- Python-owned registration: seed hints and local file inventory only.
CREATE TABLE papers (
    paper_id TEXT PRIMARY KEY,
    arxiv_id TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL CHECK (
        source_kind IN ('model', 'review', 'classification', 'tool', 'auxiliary')
    )
);

CREATE TABLE paper_versions (
    paper_version_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(paper_id),
    version_label TEXT NOT NULL,
    seed_title TEXT,
    seed_authors TEXT,
    first_arxiv_year INTEGER,
    source_url TEXT,
    pdf_url TEXT,
    local_filename TEXT,
    intended_scope TEXT,
    local_pdf_status TEXT NOT NULL DEFAULT 'unknown',
    pdf_sha256 TEXT,
    pdf_size_bytes INTEGER CHECK (pdf_size_bytes >= 0),
    UNIQUE (paper_id, version_label)
);

-- Paper-agent extraction: source descriptions remain distinct from models.
CREATE TABLE paper_profiles (
    paper_version_id TEXT PRIMARY KEY REFERENCES paper_versions(paper_version_id),
    verified_title TEXT,
    verified_authors TEXT,
    doi TEXT,
    first_submitted_date TEXT,
    version_date TEXT,
    author_abstract TEXT,
    inspected_scope TEXT,
    extraction_limitations TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'not_started',
    review_status TEXT NOT NULL DEFAULT 'unchecked',
    no_model_link_reason TEXT,
    extraction_run_id TEXT,
    updated_at TEXT
);

CREATE TABLE paper_summary_revisions (
    summary_id INTEGER PRIMARY KEY,
    paper_version_id TEXT NOT NULL REFERENCES paper_profiles(paper_version_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    summary_text TEXT NOT NULL,
    coverage_note TEXT,
    generated_at TEXT NOT NULL,
    extraction_run_id TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'unchecked',
    review_note TEXT,
    UNIQUE (paper_version_id, revision)
);

CREATE UNIQUE INDEX idx_paper_summaries_id_version
    ON paper_summary_revisions(summary_id, paper_version_id);

CREATE TABLE paper_model_descriptions (
    description_id INTEGER PRIMARY KEY,
    paper_version_id TEXT NOT NULL REFERENCES paper_versions(paper_version_id),
    source_label TEXT,
    description_scope TEXT,
    completeness_status TEXT NOT NULL CHECK (completeness_status IN (
        'source_scope_captured', 'source_scope_partial', 'reference_only'
    )),
    description_text TEXT,
    extraction_run_id TEXT,
    review_status TEXT NOT NULL DEFAULT 'unchecked',
    UNIQUE (description_id, paper_version_id)
);

CREATE TABLE paper_assertions (
    assertion_id INTEGER PRIMARY KEY,
    paper_version_id TEXT NOT NULL REFERENCES paper_versions(paper_version_id),
    description_id INTEGER,
    claim_kind TEXT NOT NULL,
    subject_label TEXT,
    property_name TEXT,
    claim_text TEXT NOT NULL,
    source_value TEXT,
    normalized_value TEXT,
    normalization_rule TEXT,
    conditions TEXT,
    value_status TEXT NOT NULL CHECK (value_status IN (
        'specified', 'unspecified_in_scope', 'explicitly_absent',
        'not_applicable', 'ambiguous_conflicting'
    )),
    basis TEXT NOT NULL CHECK (basis IN (
        'source_stated', 'source_assumed', 'agent_inferred'
    )),
    review_status TEXT NOT NULL DEFAULT 'unchecked',
    review_note TEXT,
    extraction_run_id TEXT,
    FOREIGN KEY (description_id, paper_version_id)
        REFERENCES paper_model_descriptions(description_id, paper_version_id),
    CHECK (normalized_value IS NULL OR normalization_rule IS NOT NULL),
    UNIQUE (assertion_id, paper_version_id)
);

CREATE TABLE evidence_refs (
    evidence_id INTEGER PRIMARY KEY,
    paper_version_id TEXT NOT NULL REFERENCES paper_versions(paper_version_id),
    locator_type TEXT NOT NULL,
    locator TEXT NOT NULL,
    pdf_page INTEGER,
    printed_page TEXT,
    excerpt TEXT,
    note TEXT,
    UNIQUE (evidence_id, paper_version_id)
);

CREATE TABLE paper_assertion_evidence (
    assertion_id INTEGER NOT NULL,
    evidence_id INTEGER NOT NULL,
    paper_version_id TEXT NOT NULL,
    PRIMARY KEY (assertion_id, evidence_id),
    FOREIGN KEY (assertion_id, paper_version_id)
        REFERENCES paper_assertions(assertion_id, paper_version_id),
    FOREIGN KEY (evidence_id, paper_version_id)
        REFERENCES evidence_refs(evidence_id, paper_version_id)
);

-- Summary claims cite the detailed assertions that support them.
CREATE TABLE paper_summary_assertions (
    summary_id INTEGER NOT NULL,
    assertion_id INTEGER NOT NULL,
    paper_version_id TEXT NOT NULL,
    PRIMARY KEY (summary_id, assertion_id),
    FOREIGN KEY (summary_id, paper_version_id)
        REFERENCES paper_summary_revisions(summary_id, paper_version_id),
    FOREIGN KEY (assertion_id, paper_version_id)
        REFERENCES paper_assertions(assertion_id, paper_version_id)
);

-- Model-curator reconciliation and structural records.
CREATE TABLE theory_families (
    family_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    parent_family_id TEXT REFERENCES theory_families(family_id),
    scope_note TEXT
);

CREATE TABLE theory_specifications (
    model_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    display_name TEXT,
    family_id TEXT REFERENCES theory_families(family_id),
    completeness_status TEXT NOT NULL CHECK (completeness_status IN (
        'defined_for_stated_scope', 'partial_structural_specification',
        'framework_or_template'
    )),
    covered_sectors TEXT,
    scope_note TEXT,
    baseline_label TEXT,
    baseline_status TEXT CHECK (baseline_status IN (
        'explicit', 'unresolved', 'not_applicable'
    )),
    baseline_model_id TEXT,
    baseline_model_revision INTEGER,
    PRIMARY KEY (model_id, revision),
    FOREIGN KEY (baseline_model_id, baseline_model_revision)
        REFERENCES theory_specifications(model_id, revision)
);

CREATE TABLE theory_aliases (
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    alias TEXT NOT NULL,
    alias_kind TEXT,
    PRIMARY KEY (model_id, model_revision, alias),
    FOREIGN KEY (model_id, model_revision)
        REFERENCES theory_specifications(model_id, revision)
);

CREATE TABLE theory_assumptions (
    assumption_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    statement TEXT NOT NULL,
    assumption_kind TEXT,
    status TEXT,
    FOREIGN KEY (model_id, model_revision)
        REFERENCES theory_specifications(model_id, revision)
);

CREATE TABLE theory_regimes (
    regime_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    spacetime_dimension TEXT,
    description_kind TEXT,
    eft_truncation TEXT,
    validity_assumptions TEXT,
    geometry_boundary_notes TEXT,
    FOREIGN KEY (model_id, model_revision)
        REFERENCES theory_specifications(model_id, revision),
    UNIQUE (regime_id, model_id, model_revision)
);

-- A 5D regime can have several boundaries with different residual symmetries.
CREATE TABLE theory_boundaries (
    boundary_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    boundary_label TEXT NOT NULL,
    position_expression TEXT,
    residual_symmetry TEXT,
    scope_note TEXT,
    FOREIGN KEY (regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    UNIQUE (boundary_id, model_id, model_revision, regime_id),
    UNIQUE (regime_id, boundary_label)
);

-- A correspondence is between descriptions, not automatically between models.
CREATE TABLE theory_regime_relations (
    relation_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    from_regime_id INTEGER NOT NULL,
    to_regime_id INTEGER NOT NULL,
    relation_kind TEXT NOT NULL,
    scope_note TEXT,
    reconciliation_status TEXT NOT NULL DEFAULT 'provisional',
    FOREIGN KEY (from_regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    FOREIGN KEY (to_regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    CHECK (from_regime_id != to_regime_id)
);

CREATE TABLE theory_gauge_groups (
    group_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    group_label TEXT,
    global_form_status TEXT CHECK (global_form_status IN (
        'stated_direct_product', 'stated_quotient', 'stated_other',
        'unspecified_in_scope', 'not_applicable'
    )),
    global_form_expression TEXT,
    normalization_note TEXT,
    FOREIGN KEY (regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    UNIQUE (group_id, model_id, model_revision, regime_id)
);

CREATE TABLE theory_gauge_factors (
    factor_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    factor_order INTEGER,
    factor_label TEXT NOT NULL,
    normalization_convention TEXT,
    embedding_note TEXT,
    FOREIGN KEY (group_id, model_id, model_revision, regime_id)
        REFERENCES theory_gauge_groups(group_id, model_id, model_revision, regime_id),
    UNIQUE (factor_id, model_id, model_revision, regime_id)
);

CREATE TABLE theory_fields (
    field_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    field_label TEXT NOT NULL,
    field_kind TEXT,
    spin TEXT,
    chirality TEXT,
    multiplicity TEXT,
    field_reality_condition TEXT,
    inherited_baseline_label TEXT,
    scope_note TEXT,
    FOREIGN KEY (regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    UNIQUE (field_id, model_id, model_revision, regime_id)
);

-- A source may state a field's action under the whole group without listing
-- factors. Exactly one of factor_id and group_id identifies the stated scope.
CREATE TABLE theory_field_representations (
    representation_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    factor_id INTEGER,
    group_id INTEGER,
    representation_label TEXT,
    representation_reality TEXT,
    exact_charge TEXT,
    source_notation TEXT,
    normalization_note TEXT,
    CHECK ((factor_id IS NULL) != (group_id IS NULL)),
    FOREIGN KEY (field_id, model_id, model_revision, regime_id)
        REFERENCES theory_fields(field_id, model_id, model_revision, regime_id),
    FOREIGN KEY (factor_id, model_id, model_revision, regime_id)
        REFERENCES theory_gauge_factors(factor_id, model_id, model_revision, regime_id),
    FOREIGN KEY (group_id, model_id, model_revision, regime_id)
        REFERENCES theory_gauge_groups(group_id, model_id, model_revision, regime_id)
);

CREATE TABLE theory_field_boundary_conditions (
    condition_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    boundary_id INTEGER NOT NULL,
    field_component_label TEXT,
    chirality TEXT,
    condition_kind TEXT NOT NULL,
    source_notation TEXT,
    scope_note TEXT,
    FOREIGN KEY (field_id, model_id, model_revision, regime_id)
        REFERENCES theory_fields(field_id, model_id, model_revision, regime_id),
    FOREIGN KEY (boundary_id, model_id, model_revision, regime_id)
        REFERENCES theory_boundaries(boundary_id, model_id, model_revision, regime_id)
);

CREATE TABLE theory_symmetries (
    symmetry_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    symmetry_label TEXT NOT NULL,
    internal_or_spacetime TEXT,
    global_or_gauged TEXT,
    imposed_or_accidental TEXT,
    breaking_status TEXT,
    anomaly_statement TEXT,
    FOREIGN KEY (regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    UNIQUE (symmetry_id, model_id, model_revision, regime_id)
);

CREATE TABLE theory_symmetry_actions (
    action_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    symmetry_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    transformation_rule TEXT,
    exact_charge TEXT,
    conditions TEXT,
    FOREIGN KEY (symmetry_id, model_id, model_revision, regime_id)
        REFERENCES theory_symmetries(symmetry_id, model_id, model_revision, regime_id),
    FOREIGN KEY (field_id, model_id, model_revision, regime_id)
        REFERENCES theory_fields(field_id, model_id, model_revision, regime_id)
);

CREATE TABLE theory_interactions (
    interaction_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    operator_label TEXT,
    interaction_kind TEXT,
    expression TEXT,
    source_notation TEXT,
    allowed_by_symmetry INTEGER CHECK (allowed_by_symmetry IN (0, 1)),
    included_in_specification INTEGER CHECK (included_in_specification IN (0, 1)),
    set_to_zero_by_assumption INTEGER CHECK (set_to_zero_by_assumption IN (0, 1)),
    coefficient_restriction TEXT,
    assumptions TEXT,
    FOREIGN KEY (regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    UNIQUE (interaction_id, model_id, model_revision, regime_id),
    UNIQUE (interaction_id, model_id, model_revision)
);

-- Lets Yukawa assignments and other operator participants be queried as fields.
CREATE TABLE theory_interaction_participants (
    participant_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    interaction_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    participant_role TEXT NOT NULL,
    source_notation TEXT,
    FOREIGN KEY (interaction_id, model_id, model_revision, regime_id)
        REFERENCES theory_interactions(interaction_id, model_id, model_revision, regime_id),
    FOREIGN KEY (field_id, model_id, model_revision, regime_id)
        REFERENCES theory_fields(field_id, model_id, model_revision, regime_id),
    UNIQUE (interaction_id, field_id, participant_role)
);

CREATE TABLE theory_parameters (
    parameter_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    interaction_id INTEGER,
    symbol TEXT NOT NULL,
    definition TEXT,
    normalization_convention TEXT,
    restriction TEXT,
    value_status TEXT,
    FOREIGN KEY (model_id, model_revision)
        REFERENCES theory_specifications(model_id, revision),
    FOREIGN KEY (interaction_id, model_id, model_revision)
        REFERENCES theory_interactions(interaction_id, model_id, model_revision)
);

CREATE TABLE theory_vacua (
    vacuum_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    regime_id INTEGER NOT NULL,
    vacuum_label TEXT,
    phase_assumptions TEXT,
    parameter_assumptions TEXT,
    status TEXT,
    FOREIGN KEY (regime_id, model_id, model_revision)
        REFERENCES theory_regimes(regime_id, model_id, model_revision),
    UNIQUE (vacuum_id, model_id, model_revision)
);

CREATE TABLE theory_breaking_steps (
    step_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    vacuum_id INTEGER NOT NULL,
    step_order INTEGER,
    order_parameter TEXT,
    from_symmetry TEXT,
    residual_symmetry TEXT,
    assumed_or_established TEXT,
    FOREIGN KEY (vacuum_id, model_id, model_revision)
        REFERENCES theory_vacua(vacuum_id, model_id, model_revision)
);

CREATE TABLE theory_relations (
    relation_id INTEGER PRIMARY KEY,
    from_model_id TEXT NOT NULL,
    from_revision INTEGER NOT NULL,
    to_model_id TEXT NOT NULL,
    to_revision INTEGER NOT NULL,
    relation_kind TEXT NOT NULL,
    scope_note TEXT,
    reconciliation_status TEXT NOT NULL DEFAULT 'provisional',
    FOREIGN KEY (from_model_id, from_revision)
        REFERENCES theory_specifications(model_id, revision),
    FOREIGN KEY (to_model_id, to_revision)
        REFERENCES theory_specifications(model_id, revision)
);

-- Source assertions supporting or disputing a precise canonical subject/property.
-- target_kind/target_id are checked by curator validation until source-led
-- migrations establish a stronger shared component key or typed FKs.
CREATE TABLE theory_assertion_links (
    support_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    assertion_id INTEGER NOT NULL REFERENCES paper_assertions(assertion_id),
    target_kind TEXT NOT NULL,
    target_id INTEGER,
    subject_label TEXT,
    property_name TEXT,
    support_stance TEXT NOT NULL CHECK (support_stance IN (
        'supports', 'disputes', 'qualifies'
    )),
    decision_note TEXT,
    FOREIGN KEY (model_id, model_revision)
        REFERENCES theory_specifications(model_id, revision)
);

-- Corrections preserve the old source claim and queue every model citation.
CREATE TABLE paper_assertion_corrections (
    correction_id INTEGER PRIMARY KEY,
    assertion_id INTEGER NOT NULL REFERENCES paper_assertions(assertion_id),
    old_snapshot_json TEXT NOT NULL,
    new_snapshot_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE theory_assertion_rechecks (
    correction_id INTEGER NOT NULL REFERENCES paper_assertion_corrections(correction_id),
    support_id INTEGER NOT NULL REFERENCES theory_assertion_links(support_id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'confirmed', 'model_change_needed'
    )),
    decision_note TEXT,
    reviewed_at TEXT,
    PRIMARY KEY (correction_id, support_id),
    CHECK (status = 'pending' OR (decision_note IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE TABLE paper_theory_links (
    link_id INTEGER PRIMARY KEY,
    paper_version_id TEXT NOT NULL REFERENCES paper_versions(paper_version_id),
    description_id INTEGER,
    model_id TEXT NOT NULL,
    model_revision INTEGER NOT NULL,
    role TEXT NOT NULL,
    source_model_label TEXT,
    contribution_summary TEXT,
    scope_note TEXT,
    reconciliation_status TEXT NOT NULL DEFAULT 'provisional',
    FOREIGN KEY (description_id, paper_version_id)
        REFERENCES paper_model_descriptions(description_id, paper_version_id),
    FOREIGN KEY (model_id, model_revision)
        REFERENCES theory_specifications(model_id, revision),
    UNIQUE (link_id, paper_version_id)
);

CREATE TABLE paper_theory_link_evidence (
    link_id INTEGER NOT NULL,
    evidence_id INTEGER NOT NULL,
    paper_version_id TEXT NOT NULL,
    PRIMARY KEY (link_id, evidence_id),
    FOREIGN KEY (link_id, paper_version_id)
        REFERENCES paper_theory_links(link_id, paper_version_id),
    FOREIGN KEY (evidence_id, paper_version_id)
        REFERENCES evidence_refs(evidence_id, paper_version_id)
);

CREATE INDEX idx_paper_versions_paper_id ON paper_versions(paper_id);
CREATE INDEX idx_paper_descriptions_version ON paper_model_descriptions(paper_version_id);
CREATE INDEX idx_paper_assertions_version ON paper_assertions(paper_version_id);
CREATE INDEX idx_paper_assertions_description ON paper_assertions(description_id);
CREATE INDEX idx_evidence_refs_version ON evidence_refs(paper_version_id);
CREATE INDEX idx_model_fields_model ON theory_fields(model_id, model_revision);
CREATE INDEX idx_model_fields_regime ON theory_fields(regime_id);
CREATE INDEX idx_model_interactions_model ON theory_interactions(model_id, model_revision);
CREATE INDEX idx_model_interactions_regime ON theory_interactions(regime_id);
CREATE INDEX idx_model_boundaries_regime ON theory_boundaries(regime_id);
CREATE INDEX idx_model_boundary_conditions_field ON theory_field_boundary_conditions(field_id);
CREATE INDEX idx_model_participants_field ON theory_interaction_participants(field_id);
CREATE INDEX idx_model_support_model ON theory_assertion_links(model_id, model_revision);
CREATE INDEX idx_corrections_assertion ON paper_assertion_corrections(assertion_id);
CREATE INDEX idx_rechecks_status ON theory_assertion_rechecks(status);
CREATE INDEX idx_paper_theory_links_model ON paper_theory_links(model_id, model_revision);
CREATE UNIQUE INDEX idx_paper_theory_links_description_role
    ON paper_theory_links(
        paper_version_id, description_id, model_id, model_revision, role
    ) WHERE description_id IS NOT NULL;
CREATE UNIQUE INDEX idx_paper_theory_links_paper_role
    ON paper_theory_links(paper_version_id, model_id, model_revision, role)
    WHERE description_id IS NULL;
