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

This repository contains the initial 50-paper seed and the instructions for building an initial atlas. Paper extraction has not yet been run, and no populated database is included.

The seed spans scalar and matter extensions, enlarged gauge sectors and grand unification, supersymmetry, axion and flavor symmetries, radiative structures, strong dynamics, extra dimensions, hidden sectors, and effective theories. It includes paired descriptions for reconciliation, scoped reviews and classifications, and two software references. The original six papers retain their IDs within the 50-paper corpus.

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
