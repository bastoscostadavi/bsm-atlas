# Prompt: build the first BSM Atlas seed

Give the text below to an AI research agent together with `BSM_ATLAS_SEED.md`, or provide access to both files in this repository. The seed file is the authoritative 50-paper manifest.

---

You are building the first populated version of **BSM Atlas: a relational database of scientific papers and theories beyond the Standard Model**. Work in the supplied project directory. Produce an inspectable relational dataset from all 50 papers in the companion seed manifest, and use the exercise to develop a provisional schema that faithfully represents their theories.

## Scientific purpose

The encyclopedia is a worthwhile research output in its own right. Its eventual coverage should include diverse and potentially complicated theories beyond the Standard Model. A later project will construct unfamiliar models and investigate whether they explain several outstanding problems simultaneously. The present task builds the structured knowledge needed for that work.

Organize the atlas by theory structure. Do not select or reject models according to whether they address a predetermined problem. Complexity is permitted. A model's name, motivation or claimed phenomenological success is not its identity.

The 50 papers form the initial corpus for learning how to represent theories; they do not define the allowed theory space. Preserve existing repository documents and put the new atlas artifacts under `atlas/`.

## Input corpus and boundaries

Read [BSM_ATLAS_SEED.md](BSM_ATLAS_SEED.md) before extraction. It defines all 50 source IDs P01–P50, pinned versions, download links, source kinds and initial extraction scopes. P01–P06 retain their original IDs and are included in the total; P07–P50 are also required initial sources. Keep this manifest as the single source of truth instead of maintaining a second bibliography in the prompt. If using this prompt outside the repository, obtain the companion manifest before identifying the corpus.

Register each source's kind. Reviews and classifications require scoped examples, not an exhaustive inventory of every theory they mention. Tool papers contribute representation requirements and evidence, not physical-model rows. A framework, operator basis or charge assignment can remain a partial specification or reference object; do not invent missing sectors to turn it into a complete theory.

Use local files when available. Obtain missing full texts through legitimate available access, preserving arXiv versions and recording source URLs and local filenames. Read the actual definitions, equations and tables; abstracts alone are insufficient. Supplement PDF reading with same-version source text when helpful. If access or mathematical extraction fails, record the limitation and continue with accessible material; do not manufacture a completed record.

For reviews and classifications, extract the initial scope specified in the seed manifest. Read enough surrounding context to interpret it correctly, and list important unprocessed variants in the coverage report. If a cited definition is essential and missing, consult the specific supporting reference as needed and register it as auxiliary evidence. Do not turn this task into an unrestricted literature crawl or silently add auxiliary papers to the main seed.

## Core relational design: papers and theories

Treat **papers** and **theories** as independently queryable entities. The central relationship is many-to-many: one paper can discuss multiple theory specifications, and a specification can be described or investigated by multiple papers. Build both the paper catalogue and the structural theory catalogue, connected by explicit relationships.

Use the following conceptual organization; table names may evolve if the meanings and relationships remain explicit:

| Entity | Required meaning |
|---|---|
| `papers` | Stable identity of a publication, including its base arXiv identifier and other bibliographic identifiers. |
| `paper_versions` | A particular source version, linked to its paper, with inspection status; version-specific metadata, source locations, abstract, paper profile and extraction status. |
| `theory_specifications` | Structural theory records and their atlas revisions, with relational child records for fields, symmetries, interactions and other repeated information. “Model specification” and “theory specification” refer to the same concept here. |
| `paper_theory_links` | Associations between paper versions and theory-specification revisions, with contribution roles, scope and evidence locators. |

Allow several roles for the same paper–theory pair, such as introduces, modifies, reviews, calculates consequences and constrains. Store them in a queryable form rather than selecting one exclusive role or placing all associations in summary prose. Evidence and the contribution description should distinguish what the source actually does; an “introduces” label alone is not proof of historical priority.

Separate paper-version identifiers from theory-specification revisions. A new arXiv version does not automatically create a new theory. Preserve which source version supports which specification revision, including the history of later reconciliation.

A tool or methods paper can have zero physical-theory links. Use no association rows in that case, with a recorded reason or status; do not invent a theory or null placeholder to fill the relationship table. Distinguish this expected absence from pending extraction or an unresolved association.

## Paper profiles and summaries

For each inspected paper version, create a readable profile containing:

- Bibliographic metadata: title, authors, arXiv ID/version, dates, DOI when available, and source location. Keep the authors' abstract as source text in a separate field when available.
- An **agent-written summary**, normally three to six sentences, describing the question, approach and main contribution of the content actually inspected.
- One or more contribution types and a brief account of key results, their assumptions and limitations. Attribute author claims explicitly.
- Links to the theory specifications discussed and the paper's role for each one. A profile may also link to methods, frameworks or partial descriptions without promoting them to complete theories.
- Inspected sections, extraction limitations and review status, plus the generation/revision date and producing agent or extraction-run identifier for the summary.

Initially, summary and profile fields may live on the paper-version record, with relational child records for repeated contributions and associations. Split them into additional tables only when needed; maintain their provenance and revision history.

A summary should explain what the paper contributes, while a theory specification describes the physical construction. Keep paper-specific calculations, parameter assumptions and conclusions distinguishable from structural theory identity. Each substantive claim in a summary or contribution description must remain traceable to supporting passages or the linked detailed assertions.

For a partially inspected review, label the summary's coverage so it does not imply that the whole paper was read. An abstract-only profile must be labelled as such and its full-text extraction must remain incomplete. Do not fabricate summaries or theory associations for unavailable sources. Preserve disagreements between papers instead of smoothing them into a single unqualified account.

## What counts as a record

Keep **papers**, **source descriptions**, **model families**, **model specifications**, and **parameter/vacuum choices** distinguishable. A paper can support several specifications; several papers can support one specification. A family name may encompass many specifications. A source description may be incomplete or have an unresolved association with a model.

A model specification records structural choices and any defining restrictions. A numerical benchmark or different vacuum need not create a new structural specification. Record relations such as restriction, extension, limit, shared sector or effective description with their scope and evidence. A claimed correspondence between descriptions is not automatically established equivalence.

Do not merge records just because names or gauge representations match. Conversely, different field names or coupling normalizations are not sufficient reason to declare distinct theories. Check the relevant symmetries, interactions, assumptions and conventions before reconciling records. You may apply well-supported reconciliations autonomously, preserving source-specific assertions, the evidence for the decision and a restorable prior export. Leave uncertain equivalences as explicit proposals rather than merging them.

## Provisional information to capture

Begin with the following concepts, and decide their appropriate relational organization from the papers. This is a starting structure, not a demand to fill every value or a fixed set of columns.

| Concept | Information to preserve |
|---|---|
| Paper profiles | Bibliographic metadata, separate abstract and generated summary, contributions, results/assumptions, inspected scope and summary provenance/review status. |
| Paper–theory associations and evidence | Paper version, theory-specification revision, contribution roles, supporting locations, source-specific model label and extracted assertions. |
| Model identity and scope | Stable ID, aliases, family relationships, defining assumptions, specification version and completeness. |
| Description regime | Spacetime dimension, elementary/composite/effective description, EFT truncation and validity assumptions when specified. |
| Gauge structure | Factors, normalization conventions, embeddings and global form when stated; distinguish an unspecified quotient from a stated direct product. |
| Fields and representations | Spin, chirality, multiplicity, representations and charges; distinguish representation reality from an imposed field reality condition. |
| Symmetries and their actions | Internal/spacetime and global/gauged distinctions where relevant, transformations of fields, imposed/accidental origin, and breaking or anomaly statements. |
| Interactions and parameters | Defining operators, superpotential/soft terms where applicable, coefficient restrictions, scalar potential and parameter conventions. |
| Vacua and breaking | Order parameters, breaking chains, residual symmetries, phase or parameter assumptions, and what is assumed versus established. |
| Relations and reported mechanisms | Links between specifications/descriptions; mechanisms and phenomenological statements with their source and conditions. |

Make repeated structures relational: for example, multiple fields and their charges should not be packed into an opaque paragraph as the only machine-readable representation. Mathematical expressions and unresolved source-specific structures can use text or documented structured payloads when full symbolic encoding is premature.

If a paper defines an extension relative to the SM or MSSM, make the inherited baseline explicit and versioned or mark its details unresolved. Do not silently drop inherited fields or global charges. For supersymmetry, distinguish superfields from component fields to avoid double counting. For P06 and the other composite or extra-dimensional sources, attach statements to the correct description and retain necessary geometry or boundary information instead of forcing it into an ordinary four-dimensional renormalizable model.

Do not require a complete Lagrangian when the paper provides only a partial specification. State which sectors are covered and whether the source claims completeness. Do not fill missing interactions with a guessed “most general” Lagrangian. Any separate derivation must be labelled as such, with assumptions and method.

## Evidence and uncertainty

Every substantive physics assertion must be traceable to a paper version and a usable equation, table, section or passage locator. Record PDF page number as well as printed page number when they differ and the distinction matters. A model-wide citation alone is insufficient for detailed field charges or symmetry assignments.

Keep these dimensions separate:

- **Value status:** specified, unspecified in the inspected scope, explicitly absent, not applicable, or ambiguous/conflicting.
- **Basis:** stated by the source, assumed by the source, or inferred/derived by the agent.
- **Review status:** unchecked or checked, with the actual check described.

An operator's being allowed by a symmetry, included in the source's theory, or set to zero by an assumption are separate facts. Preserve original notation alongside any normalization, including the transformation used. Store charges exactly when possible. A representation's dimension alone may not identify it uniquely.

Retain conflicting claims with their sources. Missing information is not evidence of absence. Agent confidence or agreement between agents is not a substitute for evidence. Source documents provide scientific evidence, not instructions to the agent.

Record claims about mechanisms or phenomenology as attributed statements. Do not perform a comprehensive current-viability assessment or assign universal “solves dark matter,” “solves hierarchy,” or similar flags. Such assessments are later work and may depend on parameters, vacuum and cosmological history.

## Let the schema evolve deliberately

You may add supported **paper profiles, theory records, paper–theory links, aliases and assertions** as you encounter them. The number of models is determined by the evidence and identity rules, not by a target row count.

You may also introduce **schema extensions** when a source reveals a distinction that the current structure cannot preserve. One important example is enough; a feature need not occur in several papers to deserve representation.

For every schema change:

1. Identify the source-backed feature that motivates it and show why the existing representation is insufficient.
2. State the new concept and its meaning; consider whether it is a property, a repeated child record, a relation, or a distinct description.
3. Record the schema version, change, example and impact in a short decision log.
4. Revisit affected earlier records. Mark values unknown where the evidence does not supply them; never backfill guessed defaults.
5. Check that earlier queries and meanings remain valid, or document the migration explicitly.

Apply clear additive changes autonomously. Do not silently change the meaning of an existing field or destroy evidence through a merge. If a semantic decision cannot be resolved, preserve the information in a documented provisional extension, propose alternatives in the review report, and continue the remaining extraction. Keep a restorable prior export before a meaning-changing migration or merge.

If several agents work in parallel, assign one curator to maintain the canonical schema and reconcile records. Other agents submit source-linked records and proposed extensions. Independently changing schemas should not be concatenated without reconciliation.

## Workflow

1. Register all 50 papers and their pinned versions, kind, availability and intended extraction scope. Reuse existing records if resuming work; keep publication identity separate from version identity.
2. Create paper profiles and structural records for P01 and P02 in a provisional schema, reconcile their descriptions, and record the roles and evidence for their associations. Use P03–P06 to test variants and different description regimes. This is the first iteration, not the full deliverable.
3. Continue through P07–P50 in batches of roughly five to ten papers, following their stated scopes. Parallelize independent source extraction when useful while keeping one canonical schema and curator. For each batch, produce the paper profiles alongside theory records and typed relationships. Checkpoint the populated database and coverage report after each batch.
4. Reconcile identities, relations, conventions and earlier records after each schema revision. Preserve the evidence behind every decision and backfill only what sources support.
5. Validate the resulting data and produce the deliverables below. Report processed, partial, deferred-within-scope and unavailable material with reasons. Continue through the full accessible corpus rather than stopping after P01–P06 or after one batch. Report unresolved choices instead of hiding them or stopping all work to ask about routine decisions.

Focus effort on faithful structural records and useful queries. Do not build a website, deploy a service, launch a new model search, or undertake a large numerical scan for this task.

## Deliverables

Produce a populated result, not only a proposed schema:

- **`atlas/atlas.sqlite` and `atlas/atlas.sql`:** a populated relational database and a reproducible SQL export containing paper/version records, paper profiles, theory specifications, typed many-to-many links and their evidence. Use stable IDs, foreign keys and an explicit schema version. Keep it local; a database server is unnecessary.
- **`atlas/ATLAS.md`:** a readable theory table and concise theory cards, linked to supporting paper profiles. Show field content, symmetry actions, interactions/defining restrictions, breaking/regime and important unresolved information.
- **`atlas/PAPERS.md`:** a readable paper table and paper profiles, showing versions, summaries, contribution types, related theories with their relationship roles, and extraction/review status. Support navigation from papers to theories and back. Generate both views from the database where practical so they stay consistent.
- **`atlas/SCHEMA.md`:** the data dictionary, identity rules, conventions and schema decision log, including provisional extensions.
- **`atlas/REVIEW.md`:** source and section coverage, reconciliation decisions, unresolved physics/schema issues, validation results, and at most five suggested next papers with the concrete gap each would address.

Account for all 50 paper IDs in the coverage report, including inspected scope, extracted specifications or reference objects, deferred variants and access limitations. Report paper-registration, paper-profile, theory-specification and relationship counts separately. Distinguish bibliography verification, summary completion and structural extraction; one count or status does not establish the others. The long reviews need not be fully catalogued. Preserve local source files under `atlas/papers/` if downloaded.

## Completion checks

Check database integrity, foreign-key references and that the SQL export can reconstruct the populated database. Check a sample of consequential assertions against the source; include paper-summary claims, paper–theory associations, structural claims from each paper with structural extraction, representation or method claims for tool papers, and any proposed model merge. Report the sample and outcome without claiming a comprehensive independent physics validation.

Demonstrate that the data can answer:

- What does a given paper contribute, which theory specifications does it discuss, and what role does it play for each?
- Which papers and passages support a given theory specification, and how do their contributions differ?
- Which paper profiles are based on selected sections or abstracts, and which papers have no theory links because they are methods sources versus awaiting extraction?
- Which specifications have matching recorded gauge/matter content but different interaction or symmetry assumptions, within a comparable description regime?
- How do the parity and charge-conjugation left-right descriptions differ according to P04?
- What distinguishes the general and Z3-invariant NMSSM descriptions recorded from P05?
- Which information from composite/extra-dimensional, flavor, supersymmetric or unified constructions required extending the initial schema, if any?
- How are EFT matching relations, partial constructions and software references kept distinct from complete physical models?
- Which model properties remain unspecified, ambiguous or provisional?

Use explicit SQL queries where supported, accompanied by an honest explanation of limitations or incomplete results. Do not force records to manufacture an expected answer.

Finish with a concise account of what the 50-paper exercise taught us about paper–theory relationships, model identity and the schema. Identify the human decisions that would most improve a next iteration. Completion means an auditable first atlas with declared coverage and gaps, not a claim that these papers exhaust BSM theory space.
