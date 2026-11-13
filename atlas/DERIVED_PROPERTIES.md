# Calculated entry properties

The build calculates properties from every stored specification, without
changing identity or imposing a consistency intake gate. Every exported entry
has `properties.fingerprint`, matching its identity; anomaly results also retain
the SHA-256 of the exact specification. Results are regenerated on each build.

Open an entry's **Properties** button, or use
`#entry/ENTRY_ID?panel=properties`. Full JSON, CSV `properties_json` and SQLite
`entry_properties` retain the results. Assess a frozen source without building:

```sh
python3 -B -m bsm_atlas.properties --catalogue atlas/catalogue.json \
  --output output/entry-properties.json
```

The report includes the source-file hash, entry count and status summary.

## Perturbative anomalies

`weyl-anomalies-1` sums exact 4D left-handed spin-1/2 contributions, including
flavor multiplicities and spectator dimensions. It checks every non-Abelian
cubic coefficient, every non-Abelian-squared–U(1) coefficient, every unordered
U(1) triple including repetitions, and each gravitational–U(1) coefficient.
Dimensions use the Weyl formula. Quadratic indices use
`2T(R) = dim(R) (lambda,lambda+2rho) / dim(g)`, with long roots squared 2.
SU(N) cubic indices use the shifted-weight cubic Casimir, normalized to +1 on
the first fundamental. Other simple algebras have no cubic adjoint invariant;
E6's cubic tensor on the 27 is not a local gauge anomaly.

Statuses are `cancels`, `nonzero`, `conditions_not_resolved`, `unsupported`, or
`resource_limit` for bounded symbolic expansions (global tests still run).
For symbolic families, identically vanishing polynomials establish cancellation
throughout the domain. Otherwise, the displayed equations must vanish together
within the stored domain; constraints and domain nonemptiness are not solved.
An unavoidable nonzero constant gives `nonzero` even in a symbolic family.

Scalars and ordinary vectors do not contribute to these chiral fermion checks.
Higher-spin/tensor formulations and non-4D spectra are unsupported. Extra
Green–Schwarz, Wess–Zumino, inflow or other cancellation sectors are not inferred.
A nonzero coefficient concerns the recorded spectrum, not every completion of
the cited paper. All arithmetic is integer or rational.
Reference: [Bilal](https://arxiv.org/abs/0802.0634).

## Global anomalies

The separate global result always has `complete: false`. Implemented tests are
the ordinary Witten mod-2 sums for SU(2) and Sp factors on the simply connected
semisimple cover on spin manifolds. They use arbitrary representations through
2T(R) with spectator dimensions, rather than just counting doublets.
`cover_tests_pass` means these tests pass or no relevant factor occurs;
`witten_anomaly` means an odd index sum under these assumptions.

The stored Lie algebra does not specify the global gauge group, centre quotient
or allowed bundles. Arbitrary global forms, generalized spin structures, the
new non-spin SU(2) anomaly and a complete global-anomaly classification are not
certified. References: [Wang–Wen–Witten](https://arxiv.org/abs/1810.00844),
[Davighi–Lohitsiri](https://arxiv.org/abs/2001.07731).

## Total renormalizable parameters

`renormalizable-characters-1` counts **real coefficient components** in the most
general nongravitating 4D scalar/Weyl component theory with canonical kinetic
terms. No paper-specific Z2, CP, flavor constraint, SUSY relation or special
coupling values are imposed. Even for an entry named supersymmetric, the count
describes the unrestricted component theory of its spectrum.

For S, the complexification of the full real scalar module, and F, all
left-handed Weyl representations including flavors, the matter count is:

* Real potential coefficients: singlets in Sym^k(S), for k=1,2,3,4.
* Complex mass coefficients: singlets in Sym^2(F).
* Complex Yukawa coefficients: singlets in S tensor Sym^2(F).

Complex counts contribute twice to the real total. The symmetric fermion
product accounts for the antisymmetric spin contraction; pseudoreal gauge
irreps consequently have antisymmetric flavor masses. A real-type scalar
module contributes R to S; complex and pseudoreal modules contribute R plus
its conjugate. These rules respect `real_module` counting.

The total includes one gauge kinetic coefficient per simple factor, n(n+1)/2
for n U(1) factors (including kinetic mixing in the fixed generator basis),
and one theta angle per simple factor. Vacuum energy, gravity and Abelian theta
terms are excluded under the usual flat-space convention without monopole or
extra global-structure input. Scalar tadpoles are included.

Freudenthal recursion constructs exact irrep characters and checks their Weyl
dimensions. Newton identities give symmetric powers; the finite Weyl
denominator sum projects onto singlets with exact U(1) charge matching. This
counts coefficients without constructing explicit invariant tensors or printing
the full Lagrangian. Interaction enumeration is also deterministic; see
[Sym2Int](https://renatofonseca.net/sym2int/).

Resource limits on dimensions, weights, Weyl groups, character storage and
multiplication operations give `resource_limit` with a null count, never a
partial number. Symbolic charge families need separate counts on charge loci;
they are `not_computed`. Non-4D, vector and higher-spin matter are unsupported.

## Physical parameters

The generic dimension equals the full coefficient count minus the generic
field-redefinition orbit rank, including scalar translations and anomalous
theta shifts. Subtracting flavor-group dimension alone is incorrect when
continuous stabilizers survive. Enhanced-symmetry strata require separate
counts. `certified` is used only for justified quotient dimensions; the rest
are `not_computed`. Detected nonzero perturbative gauge anomalies instead give
`anomalous_spectrum` and no quantum physical count without a specified
cancellation mechanism. Auxiliary cover tests do not gate these Lie-algebra
component-theory counts; neither a count nor perturbative cancellation certifies
the consistency of a global completion.

The gauge conventions are flat space without monopoles, with the charge basis
fixed on the charged span. If n Abelian generators have matter-charge rank r,
the n-r free Maxwell directions can have kinetic mixing and normalizations
removed by basis changes preserving all charges. Subtract
`n(n+1)/2 - r(r+1)/2` from the raw kinetic count. A neutral singlet plus a free
U(1), for example, has 5 raw coefficients but 3 generic physical parameters:
one scalar translation and one free-field normalization are redundant.

### Generic coupling-space solver

`bsm_atlas/physical_parameters.py` implements `schur-mass-slice-orbit-2`.
It uses the specification, never the model name, references or an imposed
flavor, discrete, CP or supersymmetry constraint. Its result is the generic
continuous dimension; special symmetry-enhanced coupling loci have their own
quotient dimensions. Discrete basis identifications do not change the count.

1. Merge identical gauge irreps separately for scalar and Weyl matter. The
   scalar commutants are O(n), U(n) or Sp(n) for real, complex or quaternionic
   real modules. Weyl multiplicities initially admit U(n).
2. Take an exact generic tensor slice. Distinct real-scalar masses fix O(n)
   rotations. Complex-scalar masses leave U(1)^n; the allowed quartics
   `(phi_1^dagger phi_j)^2` fix relative phases, leaving the common U(1).
   Quaternionic scalar masses leave Sp(1)^n. For n>=2, each pair has four real
   gauge-invariant cross-bilinears; a generic quadratic form in these bilinears
   fixes its Sp(1)xSp(1), so pairs (1,j) fix all scalar Sp(n). For n=1 the full
   residual Sp(1) is explicitly retained and tested for accidental custodial
   symmetry. Takagi masses fix real-irrep Weyl rotations. Ordinary and skew
   singular values leave vectorlike pair phases, massless U(n) blocks or Sp(1)
   blocks. If a neutral scalar exists, its generic Yukawa on a massive Dirac
   square subblock fixes relative pair phases. These chosen additional tensors
   are invariant under the remaining group, so their fixed coordinates cannot
   spuriously change its orbit rank. Record the removed orbit dimension.
   Generic neutral-scalar quartics also fix their rotations and translations:
   unequal nonzero diagonal fourth powers force rotations to zero, and their
   cubic variations force all infinitesimal translations to zero.
3. Construct the remaining coupling representations using the Cauchy identity
   `Sym^k(R tensor V) = direct_sum_lambda Schur_lambda(R) tensor Schur_lambda(V)`.
   Jacobi-Trudi characters and exact gauge-singlet projection give the number
   of copies. Young symmetrizers give integer flavor-module bases. Flavor spaces
   on which the remaining group acts trivially, or by a common phase, are
   compressed using exact hook-content dimensions, rather than expanded into
   separate fields or tensor components. The action
   is constructed in the ambient tensor space, which preserves rank without
   requiring explicit gauge Clebsch-Gordan coefficients. Real potentials are
   complexified; complex Yukawas are paired with their duals. This has complex
   dimension equal to the original real coefficient dimension. These real
   compact-group modules have invariant inner products, identifying operator
   and dual coefficient representations without changing orbit rank. The code checks
   that every constructed dimension matches the independent coefficient count.
4. Add the residual Weyl trace actions on non-Abelian theta coordinates. There
   is no inference of an additional cancellation sector. These are changes of
   field basis and theta coordinates, separate from global gauge anomalies.
5. Construct the matrix `delta c = M(c) epsilon`. Its entries are linear in
   independent coupling coordinates, with constant theta rows. The exact
   kernel of the full representation supplies an orbit-rank upper bound.
   For an isolated n-by-m Yukawa matrix and its dual, generic singular values
   guarantee additional traceless stabilizers of dimension
   `min(n,m)-1 + max(0,(n-m)^2-1)`. These survive the theta rows. This rule
   applies to arbitrary isolated bifundamental sectors, without an SM matcher.
6. Evaluate three explicitly deterministic coupling points modulo the prime
   1000000007. A nonzero minor over this prime field proves a nonzero minor
   polynomial over characteristic zero: it is an exact lower bound, not a
   floating-point rank estimate. A count is certified only if it saturates the
   proven upper bound. Otherwise use exact fraction-free polynomial elimination
   in a separately bounded SymPy worker. A failed bound, missing dependency or
   exhausted budget produces no number. Repeated samples alone are not proof.
   For a large multiplicity of an identical module, the test point can use a
   selected coupling subspace. Its nonzero minor is still a lower bound for the
   full coupling space; the upper bound uses the full representation. Such a
   selected-subspace result is accepted only on saturation, never on a rank
   inferred from samples or a symbolic calculation of the restricted space.

The final orbit rank combines the fixed mass/singlet slice, the certified
remaining rank and the free Abelian kinetic normalization rank. The output
retains these ranks, the residual stabilizer dimension, method, prime, point
hash and certificate type. The entry's property fingerprint pins the spectrum.
The SM-family closed form, mass-only decomposition, real-singlet formula and
portable E6 certificate remain independently justified fast paths/fallbacks.

The ordinary exact-bound path uses the Python standard library. Install the
optional symbolic-elimination fallback with:

```sh
python3 -m pip install -r requirements-properties.txt
python3 -B -m unittest tests.test_physical_parameters tests.test_properties
python3 -B scripts/validate_physical_parameters.py
python3 -B -m bsm_atlas.properties --catalogue atlas/catalogue.json \
  --output output/entry-properties.json --workers 4
```

The parallel report retains deterministic input order and the source-file hash.
It does not mutate the source. The interface displays exact physical counts
when available and a brief stopping reason otherwise. A computational limit
does not establish that the quotient is mathematically uncomputable. The
nonzero-anomaly status is a separate assignment policy, not a solver failure.

Independent validation covers:

| Theory | Raw real coefficients | Generic physical parameters |
| --- | ---: | ---: |
| Standard Model | 61 | 19 |
| SM + one real scalar singlet | 67 | 24 |
| SM + three sterile Weyl fermions | 91 | 37 |
| SM + a second Higgs doublet, general Yukawas | 127 | 80 |
| General 2HDM scalar potential only | 14 | 11 |
| General 3HDM scalar potential only | 54 | 46 |
| General 4HDM scalar potential only | 152 | 137 |
| General 5HDM scalar potential only | 350 | 326 |
| Isolated real singlet potential | 4 | 3 |
| Two real singlets, general potential | 14 | 11 |
| One SU(2) scalar doublet without hypercharge, including gauge/theta | 4 | 4 |

Tests disable the earlier SM spectrum matcher and certificate table when
checking the new solver. They also test quaternionic custodial stabilizers,
antisymmetric color contractions, Schur hook dimensions, charge rescaling,
factor renaming/reordering, split multiplicity rows, exact symbolic rank and
resource limits, plus unexpanded 100-flavor singlet and Higgs examples. The
standalone validation script writes a machine-readable report with expected
counts, calculated ranks and the solver hash. The old independent integer-tensor benchmarks and E6
certificate tests remain. References: [flavor parameter counting](https://arxiv.org/abs/1504.07549),
[multi-Higgs invariant space](https://arxiv.org/abs/2102.13120),
[SymPy fraction-free elimination](https://docs.sympy.org/latest/modules/polys/domainmatrix.html).

### SM component family

An exact spectrum matcher recognizes three SM generations, h>=1 Higgs doublets,
n sterile Weyl singlets and s neutral real scalar singlets. It matches full
representations and multiplicities, not names. The connected redefinition
dimension is `45 + h^2 + n^2 + s(s-1)/2 + s` (the final term is translations).

Generic distinct singlet masses fix scalar rotations; independent quartics
break translations through cubic variations. A generic Higgs potential fixes
U(h) mixing through distinct masses, and relative phases through allowed
(H_i^dagger H_j)^2 quartics, leaving a common Higgs phase.

For h=1,n=0, generic SM Yukawas leave hypercharge, baryon number and three
lepton-family phases: classical stabilizer dimension 5. For h>=2,n=0, two
generic charged-lepton Yukawa matrices leave only hypercharge, baryon and total
lepton number: dimension 3. For n>=1, distinct sterile Majorana masses and a
neutrino Yukawa matrix nonzero in all charged-lepton rows remove the continuous
lepton phases: dimension 2. Generic quark Yukawas leave baryon number and the
shared hypercharge direction. These are generic statements, also for n<3.

Anomalous baryon rephasing adds one orbit direction in theta space. The full
orbit rank is group dimension minus the above stabilizer dimension plus one.
This gives SM 61 total / 19 physical, SM + real singlet 67 / 24, SM + three
sterile fermions 91 / 37, and general two-Higgs matter 127 / 80. No extra symmetry
is imposed. The standalone local exact-matrix benchmark independently
reproduces the three h=1 examples.

### Mass-only fermion theories

Without scalars, the only renormalizable matter interactions are masses. A
complex irrep and its conjugate give min(n,m) singular values; a real irrep
gives n Takagi masses; a pseudoreal irrep gives floor(n/2) skew-Takagi masses.
Surviving rotations of massive pairs have zero anomalous trace. Massless
chiral rotations remove theta combinations; exact rational rank of their
spectator-weighted 2T rows determines how many. Add masses, gauge kinetic
coefficients and unremoved non-Abelian theta angles.

### E6 component certificate

The E6 component benchmark has 317 total, orbit rank 23 and 294 physical
parameters. The portable [certificate](parameter_certificates.json) pins the
full spectrum, 18 interaction types summing to 315 real matter coefficients,
and a selected integer coupling point. Its potential counts by scalar degree
are 0,12,38,183; mass and Yukawa counts are 3 and 38 complex coefficients.

The connected group U(3)_phi × U(3)_psi × SO(2)_A × U(2)_xi has dimension 23.
Four allowed tensors suffice: a diagonal phi-cubed tensor with unequal nonzero
entries, a nonzero A A coefficient, a distinct diagonal xi xi mass, and a
phi_1 psi psi tensor with distinct diagonal entries. Tests reconstruct the
infinitesimal tensor variations directly and establish exact rank 23. This
saturates the full group dimension, proving generic maximal rank; including
theta cannot increase it. The source experiment script hash is retained as
provenance, without requiring that experiment or Mathematica at build/test time.

Pure real-singlet quartic potentials are also certified, with orbit rank
s(s-1)/2+s.
