# Source reviews, 9 November 2026

This review covers nine erroneous entries at or near the start of the full
Forces and Matter listing. It is not a scientific audit of the entire catalogue.

## Results

| Original record | Source-backed result |
|---|---|
| Scalar leptoquarks S1, R2, S3 from 2211.14172v2 | Restore the complete SM baseline and source hypercharges, then merge with existing complete entries. Total real field dimensions: 190, 196, 202. |
| Vector leptoquarks U1, V2 from 2211.14172v2 | Restore the complete SM baseline, source hypercharges and complex-vector counting, then merge with existing complete entries. Dimensions: 208, 232. No Pati–Salam completion is inferred. |
| U(1)H horizontal model from 2402.12453v1 | Restore the extra gauge factor and quark-family charges of the unbroken phase. Preserve the other aliases, paper links and old annotations for separate re-extraction; they were merged on an erroneous SM-only identity. |
| Deflected AMSB from 1512.06715v3 | Withdraw the incomplete sector pending re-extraction. Its single-generation inventory is not the MSSM. A definite messenger inventory and the source's charge/conjugation conventions must be resolved before restoring it. |
| U(1)I3R × U(1)B-L seesaw from 1703.02471v3 | Restore spectator colour, the complete three-generation fermion inventory, RH-to-LH charge conjugation and scalar multiplicities. Merge with the existing complete model (dimension 198). |
| Scalar leptoquark S1′ from hep-ph/9307324v2 | Eq. (1), bar(uR^c)eR S1′, fixes (bar3,1,Y=1/3). Restore colour and hypercharge and merge with SM+S1 (dimension 190). |

The source locators, verified local TeX hashes, superseded entries, original
paper metadata and detached literature annotations are retained in the two
dated JSON review files. No paper has been deleted from the bibliography.
The obsolete leptoquark and seesaw URLs are retained as aliases of their
corrected complete entries. Incorrect aliases of the horizontal model are
preserved in the review files rather than redirected to an unrelated model.

## Reproduction and publication

The two review scripts are dry runs by default:

```sh
python3 -B scripts/review_leading_entries.py
python3 -B scripts/review_front_page_followup.py
```

`--write` applies each review once, with fingerprint guards and the shared
ingestion lock. They preserve the original records before modifying the working
catalogue and literature store. A second application refuses to overwrite the
saved review or silently alter an already-corrected inventory.

The publication source is an immutable release pinned by `atlas/snapshot.json`.
Repairing the working files does not update that release. A fresh frozen build,
successful checks, and a newly published data snapshot are required to put
these corrections on the website. The validated review snapshot is published as
[atlas-6ab84d764fc1-e83c0c6a-gauge-matter-13](https://github.com/bastoscostadavi/bsm-atlas/releases/tag/atlas-6ab84d764fc1-e83c0c6a-gauge-matter-13)
and pinned by `atlas/snapshot.json`. Its local prepared assets are under
`.build/leading-entry-review/`.
