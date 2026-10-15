# BSM Atlas extraction review: initial 50 papers

Updated 2026-10-04. The paper agent and model agent have each completed one run for every seed paper P01–P50. This is a source-scoped agent extraction, not an independent scientific review. [The seed manifest](../BSM_ATLAS_SEED.md) defines the pinned versions and intended scopes; [the design](DATABASE_DESIGN.md) assigns the SQLite tables to scripts, the paper agent, or the model agent.

## Recorded coverage

| Record or check | Result |
|---|---:|
| Registered papers and pinned versions | 50 each |
| Local PDFs with recorded hashes | 50 |
| Completed paper-agent runs | 50 |
| Paper profiles and generated summaries | 50 each |
| Profiles `ready_for_model` / `partial` | 47 / 3 |
| Source-specific model descriptions | 238 |
| Source-description completeness: captured / partial / reference-only | 222 / 3 / 13 |
| Paper assertions / evidence references | 1,812 / 2,378 |
| Completed model-agent runs | 50 |
| Model-specification revisions | 125 |
| Model completeness: defined for scope / partial / framework-template | 41 / 60 / 24 |
| Paper–model links / exact link-evidence rows | 233 / 960 |
| Model assertion-support rows | 4,218 |

The partial paper profiles are P21, P22 and P26. Their model reconciliations use only the prepared scope and retain its limitations. P47 is a software-tool paper and correctly has no physical-model link; its model-agent run completed with no structural inserts. The other 49 paper versions have at least one paper–model link. P48 has one explicitly partial SILH operator-sector specification alongside software-only descriptions.

All 50 paper profiles, 50 summaries and 1,812 assertions remain `unchecked`. All 233 paper–model links remain `provisional`. A link means that the importer checked its source pointer and database structure; it is not a physics endorsement or a claim of historical priority.

The v9 completeness labels follow the exact definitions in [DATA_DICTIONARY.md](DATA_DICTIONARY.md). The [row-by-row migration audit](completeness_review_v9.json) preserves the previous wording. This relabeling classified existing scope notes; it did not resolve physics ambiguities or promote review status.

## Provenance and checks

Each run retains its prompt, source text, structured JSON, manifest and Codex event log under `atlas/runs/papers/<ID>/` or `atlas/runs/models/<ID>/`; model runs also retain `packet.json`. The importer makes a SQLite backup before each import and refreshes `atlas/atlas.sql`. Corrections to failed proposals were imported from preserved JSON copies, leaving the original attempts available. The model agent processes one prepared paper per Codex CLI process and never edits paper-agent rows.

Schema version 10, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, and `python3 atlas/validate_atlas.py` pass after adding the correction workflow. No corpus claim has been corrected through that workflow yet. The SQL export restores into a fresh SQLite database with the same model and link counts. There are no paper assertions or paper–model links without evidence and no model specifications without a source-support row. The importer also requires source assertions for each new model component before committing a one-paper proposal. The PDFs' local hashes and parser checks establish the files used in these runs; they do not independently certify download origin.

## Review priorities

1. **Check consequential physics claims.** The agents preserved printed ambiguities instead of silently correcting them. The P01 scalar-potential conditions, P02 scan-range notation, P29 A4 assignments and Dirac-matrix convention, P31 generalized-GIM statement, P40 numerical warp estimate, and P49–P50 operator conventions and matching discrepancies are examples. Each run's `open_questions` and the SQLite evidence rows provide the exact source locations.
2. **Resolve scoped or incomplete constructions.** Review and classification papers often yielded bounded templates or deferred variants rather than complete models. P34 and P50 explicitly leave many classified examples unbuilt. P41 stores dimensional alternatives as regimes of a parameterized UED framework and warns that fixed five- and six-dimensional theories are not equivalent; compare this with the seed's request for separate constructions once their field and boundary details are extracted.
3. **Reconcile inspection scope.** Several model runs received selected PDF text pages even where the earlier paper profile reports a broader inspection. The model proposals relied on the paper agent's cited assertions for that broader scope and do not claim independent inspection of omitted pages. Review the coverage notes before promoting any claim to `checked`.
4. **Review model identity across papers.** Cross-paper reuse and distinctions are provisional. Examples include P01/P02's shared real singlet, P29/P30's different A4 constructions, P35/P36's shared SU(5)/SO(5) sector with different complete theories, P37/P38's Twin Higgs variants, and P48/P49's narrower versus general EFT operator spaces. The agent deferred comparisons when earlier source details or a unique field inventory were missing.

No `atlas/ATLAS.md` model cards or `atlas/PAPERS.md` readable profiles have been generated yet. The SQLite database and saved run proposals are the current inspectable artifacts. A scientific reviewer should verify high-impact claims and identity decisions before those publications are presented as vetted atlas entries.
