-- Read-only recipes for the downloaded atlas.sqlite.
-- These are query definitions, not results from the live DSI database.
-- Stored labels are not mathematical group equivalence or exhaustive literature coverage.

-- 1. Papers linked to models whose recorded gauge-group label contains SU(5).
SELECT DISTINCT p.paper_id, p.arxiv_id, v.version_label,
       l.model_id, l.model_revision, l.role, l.reconciliation_status,
       g.regime_id, g.group_label
FROM papers AS p
JOIN paper_versions AS v ON v.paper_id = p.paper_id
JOIN paper_theory_links AS l ON l.paper_version_id = v.paper_version_id
JOIN theory_gauge_groups AS g
  ON g.model_id = l.model_id AND g.model_revision = l.model_revision
WHERE g.group_label LIKE '%SU(5)%'
ORDER BY p.paper_id, l.model_id, l.model_revision;

-- 2. Source registration, actual inspection/review, and association counts.
-- A NULL profile or absent link is not proof that extraction was completed.
SELECT p.paper_id, p.source_kind, v.version_label,
       pp.inspected_scope, pp.extraction_status, pp.review_status,
       pp.no_model_link_reason, count(DISTINCT l.model_id) AS linked_model_ids
FROM papers AS p
JOIN paper_versions AS v ON v.paper_id = p.paper_id
LEFT JOIN paper_profiles AS pp ON pp.paper_version_id = v.paper_version_id
LEFT JOIN paper_theory_links AS l ON l.paper_version_id = v.paper_version_id
GROUP BY p.paper_id, v.paper_version_id
ORDER BY p.paper_id, v.version_label;

-- 3. Compare recorded operators without merging their model/regime identities.
SELECT model_id, model_revision, regime_id, operator_label, expression,
       source_notation, coefficient_restriction, assumptions,
       allowed_by_symmetry, included_in_specification, set_to_zero_by_assumption
FROM theory_interactions
WHERE model_id IN ('lr-triplet-parity', 'lr-triplet-charge-conjugation',
                   'nmssm-general-rpc-cpc', 'nmssm-z3-rpc-cpc')
ORDER BY model_id, model_revision, regime_id, interaction_id;
