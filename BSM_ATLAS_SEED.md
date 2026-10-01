# BSM Atlas: first seed to download

Prepared October 1, 2026.

Start with these **six papers**. The selection tests how to represent different kinds of theories and reconcile descriptions across papers. It is not organized around solving a particular phenomenological problem. The encyclopedia is an independently useful first outcome; later work will propose potentially complex theories and investigate whether they address several problems together.

This is the active seed for the first extraction exercise. Use the companion [agent prompt](BSM_ATLAS_AGENT_PROMPT.md) to carry out the exercise.

## Download manifest

Download the pinned PDF versions below into `atlas/papers/`. The filenames are suggestions for consistent local storage; these files have not been downloaded as part of preparing this list. Years in the bibliography are first arXiv submission years.

| ID | arXiv version | Download | Suggested filename |
|---|---|---|---|
| P01 | hep-ph/0011335v3 | [PDF](https://arxiv.org/pdf/hep-ph/0011335v3) | `hep-ph_0011335v3.pdf` |
| P02 | 1306.4710v5 | [PDF](https://arxiv.org/pdf/1306.4710v5) | `1306.4710v5.pdf` |
| P03 | 1106.0034v3 | [PDF](https://arxiv.org/pdf/1106.0034v3) | `1106.0034v3.pdf` |
| P04 | 1005.5160v1 | [PDF](https://arxiv.org/pdf/1005.5160v1) | `1005.5160v1.pdf` |
| P05 | 0910.1785v5 | [PDF](https://arxiv.org/pdf/0910.1785v5) | `0910.1785v5.pdf` |
| P06 | hep-ph/0412089v2 | [PDF](https://arxiv.org/pdf/hep-ph/0412089v2) | `hep-ph_0412089v2.pdf` |

The corresponding arXiv pages below provide metadata and available source formats. Preserve the version when obtaining supplementary TeX or HTML; record any version difference instead of silently substituting it.

## Papers and initial extraction scope

### P01 — A baseline scalar extension

**C. P. Burgess, M. Pospelov and T. ter Veldhuis (2000). [The Minimal Model of Nonbaryonic Dark Matter: A Singlet Scalar](https://arxiv.org/abs/hep-ph/0011335v3).**

Begin with the model definition, scalar potential, symmetries and parameter conventions. This supplies a small, readable first record against which to test the extraction format. Its phenomenological motivation does not become an inclusion criterion for the atlas.

### P02 — A second source for a potentially overlapping specification

**James M. Cline, Kimmo Kainulainen, Pat Scott and Christoph Weniger (2013). [Update on scalar singlet dark matter](https://arxiv.org/abs/1306.4710v5).**

Compare its structural definition with P01. Determine which statements agree, which use different conventions, and which are study-specific assumptions or omissions. Do not assume in advance that every statement in the two papers describes an identical specification. This tests many-papers-to-one-model reconciliation and the difference between an omitted term and an explicitly absent term.

### P03 — Shared field content, different interaction structures

**G. C. Branco et al. (2011). [Theory and phenomenology of two-Higgs-doublet models](https://arxiv.org/abs/1106.0034v3).**

For the first pass, focus on **Type-I and Type-II Yukawa structures**, the scalar-sector assumptions relevant to those descriptions, and their symmetry realization. Record partial specifications if the discussion leaves choices open. Inventory other variants as unprocessed; do not attempt to catalogue the entire 180-page review now. This tests one-paper-to-many-model relations and the limits of identifying models by gauge group and representations alone.

### P04 — An enlarged gauge sector and different discrete actions

**Alessio Maiezza, Miha Nemevsek, Fabrizio Nesti and Goran Senjanovic (2010). [Left-Right Symmetry at LHC](https://arxiv.org/abs/1005.5160v1).**

Extract the gauge and matter structure, symmetry breaking, and the **parity and charge-conjugation implementations** of left-right symmetry. Record how these choices restrict interactions. The first pass concerns the structural definitions; numerical bounds remain attributed claims from the paper.

### P05 — Supersymmetry, additional fields and interaction restrictions

**Ulrich Ellwanger, Cyril Hugonie and Ana M. Teixeira (2009). [The Next-to-Minimal Supersymmetric Standard Model](https://arxiv.org/abs/0910.1785v5).**

Start with the model-definition discussion of the **general and Z3-invariant NMSSM**, including field content, superpotential, soft terms and symmetry assumptions. Read surrounding material as needed to resolve definitions. Leave detailed phenomenology and the many additional scenarios for later. This tests superfields versus component fields, soft breaking, and distinctions among specifications within a named family.

### P06 — A composite and extra-dimensional description

**Kaustubh Agashe, Roberto Contino and Alex Pomarol (2004). [The Minimal Composite Higgs Model](https://arxiv.org/abs/hep-ph/0412089v2).**

Extract the construction's symmetry structure, symmetry breaking, gauge embeddings and the relationship between its composite interpretation and five-dimensional realization. Record description regime, geometry or boundary information when needed. Preserve which statement belongs to which description. This tests whether the schema can accommodate theories beyond a list of elementary four-dimensional fields.

## What this seed is intended to reveal

Process P01 and P02 first, then P03–P06. Revisit earlier records whenever a justified schema change affects them. Six papers do not imply six model rows: some papers contain several variants, and different papers may support one specification.

The first deliverable should show what can actually be represented and supported by evidence. Allow additional model records and documented schema extensions to emerge from these sources. Keep a backlog of further papers justified by specific missing capabilities, but finish this seed before expanding the main corpus.

The seed intentionally leaves many topics uncovered, including grand unification, axion constructions and systematic EFT matching. This is a small test of the representation, not a claim of representative or complete BSM coverage. Labels such as “minimal” in several titles impose no simplicity requirement on the future encyclopedia.
