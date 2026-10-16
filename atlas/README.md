# Atlas data and conventions

The active atlas records gauge algebras, Lorentz and gauge representations, multiplicities and source-paper associations. Start with [FIELD_CONTENT_CONVENTIONS.md](FIELD_CONTENT_CONVENTIONS.md), the [entry schema](entry.schema.json) and the [extraction instructions](../BSM_ATLAS_AGENT_PROMPT.md).

## Current catalogue

- `catalogue_identity.py`, `scalar_conventions.py`, `nonabelian_core.py`: numerical normalization, exact field-content identity and the two non-Abelian projections.
- `parameterized_entry.py`, `charge_expressions.py`: declared symbolic U(1) charge families and exact specialization.
- `prepare_entry.py`, `check_entry.py`: read-only preflight and duplicate reconciliation.
- `field_content_curations.json`: explicit presentation, baseline and source-correction decisions.
- `FIELD_CONTENT_CATALOGUE.json`: generated catalogue, identical to the website JSON; never hand-edit it.
- `examples/`: numerical and symbolic input examples, not accepted source models.

The machine key `copies` means representation multiplicity. It is retained to avoid changing frozen payloads and canonical fingerprints. `catalogue_identity_v1.py` is also still required: the current implementation imports its common validation helpers, and historical evidence uses its original counting convention. It is not an unused script.

## Extraction and review

`reextraction/` contains versioned source checks, original/normalized candidates, source-field mappings, receipts and coverage reports. Frozen hashes protect historical evidence. These records are not disposable build output.

- `accepted.json`: frozen pilot acceptance decisions.
- `accepted-followup.json`: separately pinned current accepted candidates.
- `accepted-so10.json`: two source-reconciled P19 spectra, with independent mathematics review and frozen evidence in `so10-resolution-20261016/`.
- `followup-20261016/handoff.json`: followup results and the distinction between accepted and staged work.
- `followup-20261016/remaining-work-by-paper.json`: historical remaining-work assessment across the original 50-paper corpus; the later SO(10) review supersedes its two P19 dispositions.

A successful preflight is not scientific review or automatic ingestion. Symbolic-family validation exists; the public exporter currently accepts numerical candidates plus explicitly labelled pending source records. `extraction_cost/` describes optional measurement tooling; missing inference telemetry is not estimated from CPU timings.

Saved extraction runners reproduce those historical runs; they are not part of the website runtime. The optional `reextraction/test_corpus.py` also checks locally cached source PDFs, which are not published and are not required by the normal build/CI checks.

## Immutable historical snapshot

`atlas.sqlite`, `atlas.sql`, `schema.sql` and `source_snapshot.json` preserve the original 34-table DSI extraction. The builder reads this snapshot and applies reviewed corrections separately. Do not write new entries or reset review states in it.

`DATABASE_DESIGN.md`, `DATA_DICTIONARY.md`, `SCHEMA.md` and `REVIEW.md` document that historical rich schema and its limitations. They are provenance, not the current minimal-catalogue specification. The obsolete full-snapshot website and duplicate public downloads have been removed; Git history preserves those implementations.

Run `make build` and `make check` from the repository root. The focused relational export is `website/downloads/field-catalogue.sqlite`, not the immutable source snapshot.
