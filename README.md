# BSM Atlas

> An AI-built atlas of theories beyond the Standard Model.

BSM Atlas is a **relational database of scientific papers and theories beyond the Standard Model**, presented as a structured, source-backed encyclopedia. Paper records explain what a publication contributes; theory records describe the physical construction. Evidence-backed relationships connect the two.

Theories are organized by gauge structure, fields and representations, symmetry actions, defining interactions, and symmetry breaking. Papers have bibliographic records, readable summaries and descriptions of their contributions.

The encyclopedia is an independently and potentially useful scientific resource. It also provides a foundation for a [separate AI search project](https://github.com/bastoscostadavi/ai-search-for-physics-bsm), whose long-term aim is to propose unfamiliar, potentially complex extensions to the Standard Model and investigate whether they address several outstanding particle physics problems simultaneously.

The atlas welcomes complex constructions. Model structure determines how entries are organized; their motivations and reported phenomenological results are recorded with evidence and assumptions.

## Papers, models and their relationships

One paper can describe several models, and one model can appear in several papers. The main catalogue uses **model** for its entries, table headings and cards; **theory** remains appropriate in broader prose.

| Record | What it describes |
|---|---|
| **Paper and paper version** | Publication metadata, the source version, author abstract, an agent-written summary, contribution types, key results and assumptions, and extraction/review status. |
| **Model specification** | A defined physical construction: its fields, symmetries, interactions, structural restrictions, breaking and description regime. |
| **Paper–model relationship** | What that paper does with that model: introduces, modifies, reviews, calculates consequences or constrains it, with supporting passage references. A pair can have multiple roles. |

Paper summaries explain the question, approach and contribution of the inspected content. They are stored separately from the authors' abstracts and retain source-version, coverage and generation/review information. Detailed physics claims retain their own evidence links.

The database should support browsing in both directions: from a paper to its theories and contributions, and from a theory to the papers that define or investigate it. Paper versions and revisions of an atlas theory specification are tracked separately. A software or methods paper can have a paper profile with no physical-theory association; that is different from an association still awaiting extraction.

## Current status

The public [BSM Atlas](https://davibc.com/bsm-atlas/) now focuses on the reduced **gauge-algebra/matter-representation catalogue**: 103 source-scoped entries from the existing extraction of 50 seed papers, plus an independent paper list. General theory paper [arXiv:1905.13729](https://arxiv.org/abs/1905.13729) is listed as a paper with **no associated gauge/matter row**.

The interface offers common algebra notation, explicit SM/MSSM reference inventories, field types, copies distinct from dimensions, source evidence, filtering and CSV/JSON/SQLite downloads. The database uses precise Dynkin labels with fixed node numbering; the website defaults to familiar dimension shorthand, with Dynkin, Young-diagram and comparison views. Gauge headings include Dynkin diagrams when defined; ambiguous canonical conversions stay unresolved. Entries with incomplete charges, representations, multiplicities or baseline sectors remain explicitly partial. Field-content grouping is not full theory equivalence. See [conventions and the small schema](atlas/FIELD_CONTENT_CONVENTIONS.md) and [website maintenance](website/README.md).

Each model is now displayed as a minimal matrix: spacetime representations, actual gauge-algebra factors, and copies. Four-dimensional Weyl fields are uniformly left-handed, with all charges and non-Abelian irreps conjugated when needed. The database saves those per-component assignments explicitly. Before adding an entry, use [the entry schema](atlas/entry.schema.json) and `python3 atlas/check_entry.py candidate.json` to find existing field-content signatures; partial records and deeper basis equivalences require reconciliation rather than a novelty claim.

This is a reusable projection of the prior source-scoped extraction, **not a new full-text reading of all 50 papers or independent physics validation**. All source assertions remain unchecked and model links provisional; P21/P22/P26 have partial inspection profiles. Pure convention/theory/tool references, uninstantiated frameworks and operator-only SM inventories do not automatically create BSM rows.

The complete original October 15 DSI snapshot is unchanged and preserved in `atlas/` and the original website downloads: all 34 tables, 50 profiles and summaries, 125 model specifications, 573 field rows, 233 paper-model links, 1,812 assertions and 2,378 evidence references. The source checksum and retrieval provenance are in `atlas/source_snapshot.json`; scientific limitations are in `atlas/REVIEW.md`. Source PDFs and extraction runners remain on DSI; PDFs are not published. The original source-generated ATLAS.md/PAPERS.md reports were unavailable. The simplified catalogue has its own generated SQLite and does not overwrite the rich extraction.

## Getting started

1. Open the [seed list](BSM_ATLAS_SEED.md) and download the specified paper versions into `atlas/papers/`.
2. Give the [agent prompt](BSM_ATLAS_AGENT_PROMPT.md) and [seed manifest](BSM_ATLAS_SEED.md) to an AI research agent with access to this repository and the papers.
3. Review the paper profiles, theory records, relationships, evidence, schema decisions and unresolved questions before expanding the corpus.

The prompt asks the agent to populate a relational database in batches while refining the schema in response to the papers. All 50 papers belong to the initial corpus; the first six provide an initial comparison set. It includes extraction boundaries, provenance requirements, reconciliation rules and completion checks.

## How the atlas is organized

- **Papers and theories are independently queryable.** Summaries describe publications; structural records describe theories. Typed relationships connect them without conflating their identities.
- **Claims retain their evidence.** Detailed assertions point to a paper version and an equation, table or passage. Source statements and agent inferences remain distinguishable.
- **Incomplete information stays visible.** Unspecified, explicitly absent, assumed and conflicting information are recorded separately.
- **The schema can evolve.** Agents may add supported model entries and justified structural extensions, documenting changes and revisiting affected records.
- **Phenomenological claims retain their conditions.** Parameter choices, vacua and other assumptions accompany reported results. A historical claim is not automatically a current viability assessment.

## Expected first outputs

The initial extraction is intended to produce:

| Planned artifact | Purpose |
|---|---|
| `atlas/atlas.sqlite` | Populated paper and theory records, their many-to-many relationships and evidence. |
| `atlas/atlas.sql` | Reproducible export of the schema and data. |
| `atlas/ATLAS.md` | Readable model table and concise model cards linked to supporting papers. |
| `atlas/PAPERS.md` | Paper table and profiles with summaries, contributions and links to models. |
| `atlas/SCHEMA.md` | Data dictionary, identity rules and schema decision log. |
| `atlas/REVIEW.md` | Coverage, validation results, unresolved issues and proposed next papers. |

The first release should be a useful, auditable seed with explicit coverage and gaps. Broader literature coverage can grow from that foundation.
