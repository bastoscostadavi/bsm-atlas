# Source-backed re-extraction staging

Run `2026-10-16-pilot-1` starts with P04, followed by P01, P02, P03 and P05. The authoritative corpus and bounded review scopes remain `BSM_ATLAS_SEED.md`; `queue.json` is a resumable status projection, not a second bibliography. Unprocessed papers are **queued**, not source omissions.

Each checkpoint separates source statements, declared inherited baselines and mathematical derivations. Original charges/handedness are in `*-source-candidate.json`; `*-normalized-candidate.json` uses exact Dynkin labels, all-LH 4D fermions and a common primitive integer charge unit. Preflight and `--require-normalized` results are saved alongside precise source locators. These are staging artifacts for curator review, not accepted database writes. An old incomplete entry lacking a matching signature is not a newly discovered model.

Pinned PDFs in ignored `sources/` are local reading evidence, not website assets or redistributed copies. The requested PDF URL, local bytes and SHA256 are recorded. Only the specified sections/pages are inspected; downloading an entire PDF is not a claim to have reread all of it.

`pilot.py` reproduces the structured checkpoints and read-only normalization checks from the reviewed extraction decisions. It does not extract new facts automatically. CPU/wall measurements cover deterministic preparation only. Token counts, billed dollars and GPU-hours remain null unless actual telemetry is available. UTC observation windows include waiting/orchestration; they are not model compute time. Source access failures and retries are listed explicitly.

The extraction stage itself made no changes to the immutable source SQLite, generated public catalogue, site or model registry. Scalar realification equivalences are not solved by this pilot.

## Accepted publication

P01–P05 are now accepted through `accepted.json`: six candidate occurrences confirm five existing entries, with a corrected full left–right spectrum. This manifest pins the reviewed checkpoint and attribute-evidence hashes and expected numerical fingerprint. `website/reextraction_reviews.py` validates these decisions during the public build and preserves original fields in `legacyProjection`; it does not ingest unreviewed queue work. The saved checkpoint `database_write_performed: false` records the extraction stage, not the subsequent curator integration. Review states distinguish agent source checks from independent physics validation.

Keep accepted checkpoint/evidence files immutable. Rerunning `pilot.py` can regenerate historical timestamps/lookup results and therefore invalidate the acceptance hashes; a new extraction run needs an explicit review decision, not silent replacement. `python3 atlas/reextraction/pilot.py queue` can reconstruct a 50-paper work queue from the authoritative seed and the checkpoints present locally. The ongoing P06–P50 work has a separate corpus ledger and is not accepted merely by being checkpointed.
