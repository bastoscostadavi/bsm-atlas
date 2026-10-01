# BSM Atlas

> An AI-built atlas of theories beyond the Standard Model.

BSM Atlas is a project to build a structured, source-backed encyclopedia of BSM theories. It organizes models by their gauge structure, fields and representations, symmetry actions, defining interactions, and symmetry breaking, with links to the papers and passages that support each description.

The encyclopedia is an independently and potentially useful scientific resource. It also provides a foundation for a [separate AI search project](https://github.com/bastoscostadavi/ai-search-for-physics-bsm), whose long-term aim is to propose unfamiliar, potentially complex theories and investigate whether they address several outstanding problems simultaneously.

The atlas welcomes complex constructions. Model structure determines how entries are organized; their motivations and reported phenomenological results are recorded with evidence and assumptions.

## Current status

This repository contains the initial 50-paper seed and the instructions for building an initial atlas. Paper extraction has not yet been run, and no populated database is included.

The seed spans scalar and matter extensions, enlarged gauge sectors and grand unification, supersymmetry, axion and flavor symmetries, radiative structures, strong dynamics, extra dimensions, hidden sectors, and effective theories. It includes paired descriptions for reconciliation, scoped reviews and classifications, and two software references. The original six papers retain their IDs within the 50-paper corpus.

## Getting started

1. Open the [seed list](BSM_ATLAS_SEED.md) and download the specified paper versions into `atlas/papers/`.
2. Give the [agent prompt](BSM_ATLAS_AGENT_PROMPT.md) and [seed manifest](BSM_ATLAS_SEED.md) to an AI research agent with access to this repository and the papers.
3. Review the resulting model records, evidence, schema decisions and unresolved questions before expanding the corpus.

The prompt asks the agent to populate a relational database in batches while refining the schema in response to the papers. All 50 papers belong to the initial corpus; the first six provide an initial comparison set. It includes extraction boundaries, provenance requirements, reconciliation rules and completion checks.

## How the atlas is organized

- **Papers and models have separate identities.** One paper may describe several specifications, and several papers may support one specification.
- **Claims retain their evidence.** Detailed assertions point to a paper version and an equation, table or passage. Source statements and agent inferences remain distinguishable.
- **Incomplete information stays visible.** Unspecified, explicitly absent, assumed and conflicting information are recorded separately.
- **The schema can evolve.** Agents may add supported model entries and justified structural extensions, documenting changes and revisiting affected records.
- **Phenomenological claims retain their conditions.** Parameter choices, vacua and other assumptions accompany reported results. A historical claim is not automatically a current viability assessment.

## Expected first outputs

The initial extraction is intended to produce:

| Planned artifact | Purpose |
|---|---|
| `atlas/atlas.sqlite` | Populated relational database. |
| `atlas/atlas.sql` | Reproducible export of the schema and data. |
| `atlas/ATLAS.md` | Readable model table and concise model cards. |
| `atlas/SCHEMA.md` | Data dictionary, identity rules and schema decision log. |
| `atlas/REVIEW.md` | Coverage, validation results, unresolved issues and proposed next papers. |

The first release should be a useful, auditable seed with explicit coverage and gaps. Broader literature coverage can grow from that foundation.
