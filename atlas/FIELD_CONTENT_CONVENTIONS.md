# Gauge-algebra and matter conventions

Version `gauge-matter-13`, October 21, 2026.

## Publication rule

The atlas contains complete, source-supported gauge-algebra and matter specifications. Read the source, normalize and validate its specification, then reconcile duplicates before adding an entry. A paper can remain in the bibliography without an associated model.

Complete here means the gauge algebra, Lorentz and gauge representations, and multiplicities in one stated description regime. It does not mean a complete Lagrangian, independently certified physics, anomaly cancellation, viable phenomenology or a UV completion of an explicitly specified EFT. Do not invent missing matter to supply any of those.

## Source and scope

Read actual pinned arXiv field definitions, equations, tables and surrounding context. A reference may include a short page, section, equation or table locator. Abstracts alone are insufficient. Resolve source notation before ingestion; do not silently convert an ambiguous label or source misprint into a normalized fact.

Choose one regime: do not combine UV and IR spectra, bulk and brane fields, fundamental fields and dependent composites, or a linear realization and its constrained nonlinear coordinates. Gauge connections follow from the algebra and are not extra matter. Spurion backgrounds and auxiliary fields are not independent propagating rows.

An explicitly inherited SM/MSSM baseline can be expanded using the templates below. Do not append colour, fermions, a Higgs, a breaking scalar or generations simply to complete a sector. An explicit finite benchmark can be harvested from a family; an arbitrary rank, replica count or charge substitution cannot be presented as a source-selected theory.

The authoritative source is `catalogue.json`: complete specifications and their paper references. Its JSON, CSV and SQLite exports describe the same objects.

Mathematical specifications accept only the fields defined by the schema. Each matter row contains `lorentz`, `reality`, `copies` and `gauge_representations`; free-text field labels, symbols and annotations are not stored or accepted on intake. Entry names and bibliography belong outside the specification. Factor IDs and row IDs are linking keys, not additional mathematical properties. Readable algebra and representation notation is derived from exact data for display.

## Gauge algebra

Use local compact Lie algebras and direct sums, not an inferred global gauge group or quotient:

`g_SM = su(3) ⊕ su(2) ⊕ u(1)`.

Each simple factor has a canonical Cartan family and rank, with an explicit factor ID. Normalize the low-rank algebra aliases B1=A1, D3=A3 and B2=C2, and map source weights accordingly. Repeated factors remain distinct slots. Source Sp(N) notation requires an explicit rank versus fundamental-dimension convention.

A BSM extension can retain g_SM with added matter; it need not enlarge the gauge algebra. A sector labelled su(2) alone is not the full algebra of an SM-containing model. Only complete published entries can create an algebra category.

## Exact non-Abelian representations

Store highest-weight **Dynkin labels**, one nonnegative integer per simple root, using Bourbaki/Sage finite Cartan node numbering. Dimensions and names are derived displays, not unique identifiers. Resolve the source node convention before entering the weights.

A_r has chain nodes 1,...,r. D_r has spinor nodes r-1,r attached to r-2. For D5 use roots e1-e2,e2-e3,e3-e4,e4-e5,e4+e5. The two spinor weights are `[0,0,0,1,0]` and `[0,0,0,0,1]`; the vector10 is `[1,0,0,0,0]`, adjoint45 `[0,1,0,0,0]`, and one 126 is `[0,0,0,2,0]`. The odd-D dual swaps the two final labels. Determine the source's spinor orientation from its embedding, not dimension16 alone.

Readable A- and D-series dimensions use exact Weyl arithmetic. For odd D_r, the penultimate spinor node is unbarred and its dual barred in dimension shorthand. Exact weights remain authoritative. A-series Young diagrams use row lengths given by sums of Dynkin labels to the right. An unavailable Young display for another family does not mean that its exact representation is unknown.

The website can switch between dimensions, Dynkin labels, eligible Young diagrams and comparison. Gauge-column Dynkin diagrams describe the algebra, not an individual field representation. SVG.js is vendored locally; it draws known geometry and does not infer source assignments.

## Lorentz representations and multiplicity

In four dimensions use Spin+(1,3) field representations `(j_L,j_R)`: scalar `(0,0)`, LH Weyl `(1/2,0)`, vector `(1/2,1/2)`. These are field representations, not on-shell polarization counts.

All independent 4D Weyl fields are left-handed. Conjugating a RH field conjugates every non-Abelian factor and negates every Abelian charge. A Dirac multiplet becomes two independent LH rows. A Majorana field supplies one independent Weyl row; dependent Hermitian conjugates are not new matter.

Higher-dimensional fields retain the appropriate B/D Lorentz Dynkin labels. The source-selected 5D UED branch uses B2 spinors `[0,1]` and scalar `[0,0]`, with physical source gauge representations. No 4D chirality conversion or invented KK decomposition is applied.

**Multiplicity** counts repetitions of a Lorentz × gauge representation, not its dimension. It is stored in the `copies` field. Distinct family charges become separate rows, not an array-valued charge or identical copies.

## Scalar counting

The canonical scalar unit is one irreducible **real gauge module** (`scalar-real-modules-1`). A displayed complex highest weight R of dimension d is its representative:

- Real type: the real form has real dimension d. One source real field contributes one copy; an unconstrained source complex field contributes two.
- Complex or pseudoreal type: the underlying real module has real dimension 2d. One source complex field contributes one copy.

A neutral complex singlet is therefore two real singlet copies. A charged Higgs doublet is one underlying real module. The NMSSM singlet chiral multiplet gives two scalar copies and one LH Weyl copy. The source complex SO(10) vector10 scalar gives two real10 copies.

Source reality is established from the paper, not guessed from self-duality. Real/pseudoreal representation type uses the exact Tits/Frobenius-Schur indicator; tensor-product indicators multiply. A nonzero Abelian charge gives complex type.

Choose a numerical scalar representative by making its first nonzero Abelian charge positive; with no such charge choose the lexicographically larger full weight tuple versus its dual. Conjugate all factors together. Do not apply scalar conjugation equivalence to Weyl fermions.

Numerical specifications store canonical component counts and `reality: real_module`, not source container counts. A table row never uses an unresolved scalar count. Symbolic families retain source container metadata; publication requires a correct uniform real-module display or a split into uniform families, not a guessed generic count.

## Abelian charges

For a fixed numerical spectrum, apply one positive common rescaling per U(1) over the complete fermion and scalar inventory so all charges are integers with gcd1. The input factor IDs fix the displayed generator basis; a common sign reversal does not create a new numerical identity. Ordinary SM hypercharge is `q=6Y`. Never normalize rows, generations or scalar subsets independently.

Multiple U(1) factors retain an explicit generator basis. Independent gcd rescalings/signs do not exhaust GL(n,Z) basis equivalence or kinetic-mixing conventions.

Families use `field-content-3`: fixed gauge factors, non-Abelian and Lorentz representations, positive integer multiplicities, declared integer parameters and exact charge polynomials. For example, `parameters: {z1:{domain:integer}, z2:{domain:integer}}`, charge `z1**2+z2`, constraints `0<z1<z2<3`. A fixed entry has no free parameters.

`integer-polynomial-1` permits integer literals, declared symbols, parentheses, +, -, *, and literal nonnegative powers **. Constraints are exact polynomial comparisons, conjoined with AND. No arrays, floats, undeclared symbols, arbitrary functions or eval. Parsing/expansion has explicit size/degree/coefficient limits.

Do not enumerate a family. The website displays its parameter domain and constraints on the same entry. Specialization validates the integer point, evaluates charges exactly, then applies numerical primitive normalization, scalar counting, aggregation and duplicate reconciliation. Family generator coordinates need not have a common gcd1 at every point before that specialization.

`symbolic-template-2` standardizes parameters as `z1,z2,...` everywhere in an entry. Expand each integer polynomial, collect equal monomials, discard zero coefficients, and order terms by descending lexicographic exponent tuple in that parameter order. For example, `(z1+z2)**2` becomes `z1**2 + 2*z1*z2 + z2**2`. An optional `parameter_names` map on a paper reference records source names.

The canonical template is the lexicographically smallest JSON serialization over consistent parameter relabelings and permutations of identical gauge factors, with simple factors ordered by Cartan family and descending rank and U(1) factors last. Factor IDs and matter-row order are not identity data; identical rows aggregate multiplicities. The executable canonicalizer bounds the combined relabeling search at 4096 choices and blocks larger comparisons explicitly rather than claiming a nonmatch. This limit is a resource bound, not mathematical inequivalence.

Constraints are retained in identity, with the same parameter renaming, expanded polynomials, split comparison chains and sorted/deduplicated comparisons. No logical domain solver is used: `z1 > 0` and `z1 >= 1` remain different templates despite defining the same integer domain. Do not drop constraints to manufacture a duplicate. Matching normalized templates reuse an entry; different templates do not prove different families of physical models. Parameter shifts, nonlinear reparameterizations, overlapping domains, pointwise charge rescalings and general U(1) basis mixing are not automatically identified.

Constraints record the source's definition of a family. Syntax validation does not certify domain nonemptiness, anomaly cancellation or physical viability.

Typed SQL tables `entry_parameters` and `entry_constraints` supplement the same entries. `matter_representations` separates `dynkin_json`, integer-only decimal `charge` and polynomial `charge_expression`; exactly one is present. Decimal text preserves arbitrarily large exact integer charges. The full specification is stored in `entries.specification_json`.

## SM presentation templates

Use these templates to expand matter content explicitly inherited from the SM or MSSM in a source.

| Template | Inventory in all-LH notation, q=6Y |
|---|---|
| F_SM | Three each of Q=(3,2;1), u^c=(bar3,1;-4), d^c=(bar3,1;2), L=(1,2;-3), e^c=(1,1;6) |
| H_SM | One complex scalar (1,2;3) |
| R_SM | F_SM + H_SM; no RH neutrino |
| R_MSSM | Three chiral matter families; two Higgs chiral multiplets; adjoint gluino/wino/bino Weyl fields; replaces R_SM |

Two-Higgs-doublet models use F_SM plus two Higgs doublets, not R_SM plus two more. NMSSM uses R_MSSM plus one singlet chiral multiplet.

## Four derived browsing views

```text
Semisimple gauge part ──────────→ Full gauge algebra
          │                              │
          ↓                              ↓
Semisimple gauge–matter ────────→ Full gauge–matter
```

The upper-left view is the **semisimple part of the gauge algebra**, not a claim that the full algebra has no Abelian factors. It forgets matter and every U(1). The upper-right view restores all Abelian factors but still omits matter; its canonical key is the multiset of simple factors plus the Abelian rank, independent of generator names or matter charges. It does not specify a global group or quotient.

The lower-left view retains Lorentz irreps, non-Abelian weights and multiplicities, forgetting all U(1) factors. The lower-right view is the complete gauge-matter entry, including exact charges and symbolic metadata when applicable. Both paths select the same underlying entries; selecting a matter core and a full algebra can also intersect those groupings.

All four derive from the same complete entries. A partial sector cannot create a category. Scalar real modules are decomposed again after restriction; a charged singlet yields two real singlets when its U(1) is forgotten. A source complex vector whose restricted gauge irrep becomes real similarly supplies two real vectors. Symbolic restriction removes Abelian factors before source-field realification; it never substitutes a fictitious parameter point.

The generated SQLite caches `full_gauge_algebras` alongside the semisimple and matter-core caches. `entry_layers` joins both branches. These are reproducible projections, not additional hand-curated model inventories. `downloads/full-gauge-algebras.csv` supplies the algebra-only view.

Identical restricted rows aggregate. Coarse grouping is not physical equivalence, symmetry breaking, a global group or an SM-embedding proof. Different interactions/global symmetries can share a full field-content entry.

## Browsing order

Algebra lists use ascending semisimple rank, semisimple dimension, and the canonical Cartan signature (family letters and numeric ranks in canonical factor order). Full algebras then compare their number of U(1) factors.

Within each algebra, matter spectra use the total **real dimension of the recorded Lorentz × gauge field representation**, including multiplicities. This is field-space dimension, not on-shell polarization counting. Gauge connections do not add matter rows. For a row of multiplicity n, complex gauge dimension d_G and complex Lorentz dimension d_L, its contribution is n × d_L × d_G times:

- 1 for `real` or `majorana` fields, imposing the recorded reality condition once;
- 2 for unconstrained `complex` or `none` fields, including independent LH Weyl fields;
- for scalar `real_module` rows, 1 when the full gauge irrep is real type, and 2 when it is complex or pseudoreal type.

In four dimensions d_L is the sum of (2j_L + 1)(2j_R + 1) over the recorded Lorentz irreps. Higher-dimensional Lorentz irreps and all simple gauge families use the exact Weyl dimension formula, in the stored Bourbaki convention. Gauge dimensions multiply across simple factors; each U(1) representation has complex dimension 1. Scalar source counts in symbolic families retain their explicit real/complex convention, so their dimension is computed without choosing a parameter point.

Thus one real singlet contributes 1, a complex Higgs doublet 4, and a LH Weyl field in a gauge representation of complex dimension d contributes 4d. The SM field representation has real dimension 184: 180 from its fermions and 4 from its Higgs. Adding a real singlet, a complex singlet, or a second Higgs doublet gives 185, 186, or 188 respectively. Restricting to the semisimple algebra preserves this dimension while the real-module multiplicities may change.

Dimension ties compare row signatures sorted in ascending order: spacetime dimension, Lorentz scheme and exact numeric Lorentz labels (with the Lorentz irreps sorted in ascending order), then gauge Dynkin labels or charges in canonical factor order, the reality label, and multiplicity. Numerical charges compare as exact numbers. Symbolic charges compare their expanded polynomial exponent/coefficient tuples in canonical parameter coordinates, listing terms in descending lexicographic exponent order; numerical charges precede nonconstant polynomials. Finally the canonical serialization, including symbolic parameters and constraints, distinguishes any remaining ties. This is a deterministic browsing convention, not a claim that equal-dimensional representations or differently constrained families are equivalent. Names, citations and hashes do not decide comparisons between distinct canonical spectra. Ordering affects the derived lists and CSVs, not the source catalogue or identity rules.

## Ingestion and identity

Use `python3 -m bsm_atlas prepare specification.json` for read-only normalization and `python3 -m bsm_atlas lookup specification.json` for duplicate preflight against the built SQLite export. `python3 -m bsm_atlas add candidate.json` validates and normalizes a full entry wrapper; `--write` saves it only after validation and duplicate reconciliation. Exact matches reuse an existing entry and combine paper links; aliases resolve to that entry. A nonmatch is not proof of a new physical theory. For `prepare --values`, use the parameter names of the supplied specification: original source names for a source candidate, or z-names for the standardized entry.

Numerical identity removes row ordering/splitting, factor ordering and permutations of identical factors, primitive common U(1) rescalings/signs, and the stated scalar equivalences. General multi-U(1) mixing, outer automorphisms, cross-regime dualities and symbolic reparameterizations are not exhaustively quotiented.

Public JSON, CSV and SQLite contain complete specifications. Paper references may carry locators and parameter-name mappings; entry aliases are navigation aids, not identity data. The SQL `matter` table stores row identifiers, Lorentz representations, scalar-counting conventions and multiplicities. `matter_representations` supplies the exact gauge components of those same rows.

Run `make build` and `make check`. Checks cover strict ingestion, normalization, typed charge storage, exact duplicate reconciliation, both browsing paths, SQL/JSON agreement and frontend behavior. They do not certify physical consistency or the correctness of a paper's claims.
