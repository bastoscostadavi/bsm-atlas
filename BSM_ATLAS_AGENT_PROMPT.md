# Adding a BSM Atlas entry

Harvest complete gauge–matter specifications from arXiv papers. The atlas records only the gauge algebra, Lorentz and gauge representations, multiplicities, and paper references. Do not create interaction, symmetry-breaking, claim, evidence, review or viability records.

## Read the source

Read the field definitions, equations, tables and surrounding discussion in a versioned paper. Abstracts alone do not establish a complete specification. Choose one definite description: do not combine UV and IR spectra, bulk and brane descriptions, dependent composites and fundamental fields, or incompatible benchmarks.

Establish every gauge factor and every independent matter row. An explicitly inherited SM or MSSM inventory can be expanded using the reference spectra; a partial sector is not permission to invent the missing fields. Gauge connections follow from the algebra and are not additional matter.

A paper without a complete usable BSM specification may remain in the bibliography without a model link. Do not add partial entries, question marks, pending states or an exclusion log.

## Normalize the mathematical input

Read [FIELD_CONTENT_CONVENTIONS.md](atlas/FIELD_CONTENT_CONVENTIONS.md) and use [entry.schema.json](atlas/entry.schema.json).

- Identify simple factors by canonical Cartan family and rank, with consistent factor IDs.
- Supply exact highest-weight Dynkin labels in Bourbaki order, not dimensions alone.
- Supply an explicit Lorentz representation and positive integer multiplicity for every row.
- Rewrite independent 4D Weyl fields as left-handed. Conjugate every non-Abelian factor and negate every U(1) charge when converting a right-handed field.
- For numerical inputs, use `field-content-2`; the normalizer handles rational source units, Dirac splitting and real scalar modules. Stored numerical charges are primitive integers over the entire inventory.
- For source-defined symbolic charge families, use `field-content-3`: declared integer parameters, exact integer polynomials, and source constraints. The normalizer assigns canonical z-names. Do not turn unknown information into a free parameter.
- A source complex scalar and a canonical real-module count are different intake units. Supply the correct source reality; do not guess it from self-conjugacy.

No anomaly-cancellation, viability or embedding certificate is required. Do not add unreported fields to provide one.

## Add references, not a separate evidence graph

Paper records in `atlas/catalogue.json` contain `id`, versioned `arxiv`, `title` and `authors`. Add a missing paper record before ingesting its entry.

A candidate is an entry object:

```json
{
  "id": "a-model-name",
  "name": "A readable model name",
  "specification": {"schema_version": "field-content-2", "inventory_complete": true, "gauge_factors": [], "matter": []},
  "references": [{"paper_id": "P01", "locators": ["Table 1; Eq. (2.3)"]}]
}
```

The empty arrays above illustrate the wrapper only; they are invalid specifications. Start from an [actual numerical](atlas/examples/two-higgs-doublets.json) or [symbolic](atlas/examples/parameterized-charges.json) specification instead. Optional `parameter_names` on a reference maps source parameter names to canonical z-names.

Keep references short and useful. Source locators are optional; extraction transcripts, PDF hashes, agent receipts and run-cost ledgers are not catalogue requirements.

## Validate, reconcile and save

```sh
python3 atlas/prepare_entry.py specification.json
python3 atlas/catalogue.py --add candidate.json
python3 atlas/catalogue.py --add candidate.json --write
make build
make check
```

The first command is a read-only aid. The writer normalizes the specification, validates its complete shape and references, and compares its exact identity with existing entries. An exact match gains references and, when needed, a navigational alias; it does not create a second model. The default is a dry run. All checks must pass before publication.

A different fingerprint does not prove physical novelty. Review nearby specifications for changes of Abelian basis, outer automorphisms, symbolic reparameterizations or alternative descriptions beyond the canonicalizer's stated equivalences. Never silently discard domain constraints to force a match.
