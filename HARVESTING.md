# Harvesting papers

The batch coordinator gives each worker one versioned paper and the atlas conventions. Workers extract gauge–matter specifications; code normalizes and validates their output, reconciles exact canonical duplicates, and writes the entries automatically through one serialized catalogue writer. There is no proposal table, second model pass or approval gate.

The existing `papers` records also track extraction progress. Paper text, worker responses, usage and import receipts remain local working files under a run directory, not additional database tables or a published exclusion log.

## New papers and recorded papers

Normal expansion takes only paper versions absent from `papers`. It checks the versioned arXiv identifier before retrieving full text and again before dispatching a prepared paper to a worker. Every recorded version is skipped, including papers whose earlier extraction failed or remained unresolved. A different ranking does not change this rule. The private job state `already_recorded` distinguishes reuse from a worker's scientific `skip` response; it consumes no model call.

`extraction_status` is informational: `not_started` means no completed attempt is established, `complete` means a structurally valid response returned entries or no eligible model, and `unresolved` covers failed calls, unavailable sources and invalid responses. Missing status on a legacy bibliography record means `not_started`. Presence in `papers`, not this status, controls normal admission. A new arXiv version has a separate identity.

After an attempt, the coordinator records bibliography and status and immediately ingests valid entries. Invalid or unresolved output adds no model. Status survives deletion of temporary source files. Old failures are retried only through a separate explicit `prepare ... --resume --retry` / `run ... --retry --execute` operation on their original run, never as a side effect of a new expansion.

Backfill an existing saved run without making model calls or adding model entries:

```sh
python3 -m bsm_atlas harvest sync-status .harvest/pilot --manifest papers.json
python3 -m bsm_atlas harvest sync-status .harvest/pilot --manifest papers.json --write
```

The first command previews changes. The optional original manifest supplies bibliography for papers whose retrieval failed before text was cached. Backfill checks source hashes and entry structure, retains existing paper IDs and writes paper progress atomically. To import the model entries from a saved run, use `harvest ingest ... --write`; this runs code only, not another model. Run `make build` after a batch to refresh the generated SQLite and website data; extraction does not deploy the website.

Harvest only complete SM extensions, including unified models in which the SM is embedded in a larger algebra. A standalone toy theory or calculation-only subset is not an eligible entry, and workers must not invent missing SM fields to complete it. An explicitly specified SM-extension EFT can be harvested in its own regime without requiring a separate UV or cosmological description to be complete.

## Prepare a batch

Create a manifest containing pinned arXiv identifiers:

```json
{
  "papers": [
    {"arxiv": "1905.13729v1"}
  ]
}
```

```sh
python3 -m bsm_atlas harvest prepare papers.json --run-dir .harvest/pilot
```

Preparation makes no model calls. It fetches version-matched metadata and full TeX source, with arXiv HTML as a fallback. Requests are serialized and spaced at least three seconds apart. Run only one fetcher across the machines you control; large arXiv sweeps should use bulk data rather than the per-paper endpoints. An abstract is never substituted for unavailable full text. Source archives are read in memory; no archive paths are extracted and no TeX is executed.

Workers receive cleaned source, not PDFs or figure images. The TeX preparer selects one main document and follows literal local includes, including nonstandard filename extensions. It preserves mathematical definitions, equations, tables, prose, appendices, captions and labels. Comments, bibliography entries, graphic inclusions, drawing code, inactive literal conditional branches and content after the document ends are omitted. Unreferenced source files are not concatenated into the worker input. Necessary local definition files remain available; arbitrary TeX execution, dynamic includes and ambiguous main documents are not guessed. Unsupported sources are flagged for separate handling.

The private `source.raw.txt` cache retains the original text-only source members, without binary figures. `source.json` records the selected main file, included files, omissions, cleaner version and raw/cleaned hashes. `paper.txt` is the cleaned worker input; both texts remain available for optional diagnostics. HTML fallback likewise omits the bibliography while retaining mathematical text and captions. These are run artifacts, not additional atlas tables.

For a local, version-matched full-text file, supply its path and bibliography:

```json
{
  "papers": [{
    "arxiv": "1905.13729v1",
    "title": "General solution to the U(1) anomaly equations",
    "authors": "Davi B. Costa, Bogdan A. Dobrescu, Patrick J. Fox",
    "text": "papers/1905.13729v1.tex"
  }]
}
```

Local paths are relative to the manifest. Supplying local text is an assertion that it matches the stated version; verify that yourself. Existing bibliography records are reused. Otherwise, missing title and authors are retrieved together from arXiv. PDF-only papers require a suitable local text transcription, with tables and equations checked against the PDF.

Use `prepare ... --resume --retry` for an explicit retry of old failed downloads. Cached paper text and instructions are hashed: changing the manifest, source text or conventions requires a new run directory. The complete assembled prompt is checked against a conservative 1,040,000-character/UTF-8-byte guard before a model call. An oversized paper is marked `retry` with category `input_size`, without truncation or a model call. Use `.harvest/` or another private directory outside `website/`; full papers are not published by the atlas.

## Run one worker per paper

Preview the jobs first:

```sh
python3 -m bsm_atlas harvest run .harvest/pilot --limit 10
python3 -m bsm_atlas harvest run .harvest/pilot --limit 10 --workers 2 --execute
python3 -m bsm_atlas harvest status .harvest/pilot
```

The default model is `gpt-6.1-sol`, with medium reasoning. `--model`, `--reasoning`, `--workers`, `--limit`, `--timeout` and `--codex /path/to/codex` are explicit controls. GPT-6.1 Sol supports low through max reasoning, not none; unsupported settings fail before workers launch. Other models remain available as explicit overrides. `--execute` is required for model calls. The CLI uses its existing authentication and may consume subscription usage or incur API charges, depending on how it is authenticated.

Workers use fresh ephemeral contexts, a read-only sandbox and structured JSON output. User configuration is not loaded; shell, app, hook, nested-agent and plugin features are disabled, and web search is disabled. They receive the full supplied paper, conventions, specification schema and examples—not the parent chat or other papers. A capability check rejects older CLIs missing the required flags before launching any worker. Selecting a model does not guarantee account access to it.

A worker returns one of the following outcomes, always with a nonempty reason identifying the source basis, exclusion or unresolved issue:

- `entries`: one or more complete, source-supported specifications, with useful equation/table/section locators.
- `skip`: no complete usable BSM specification is established in the supplied paper.
- `retry`: text or assignments remain unresolved. Network errors, timeouts and process failures are also retriable, not scientific exclusions.

A paper studying an existing model is useful: ingestion attaches its reference to that model. Workers retain exact rational source charges or source-named integer-polynomial families; normalization is done by code. The working output encodes each specification as `specification_json` so structured output can accommodate factor and parameter dictionaries; it is parsed and strictly validated before automatic ingestion.

Recorded papers are not rerun automatically, regardless of whether extraction succeeded. Use `run ... --retry --execute` for a deliberate follow-up of failed or invalid attempts in their original run. Retry missing downloads with `prepare ... --resume --retry` first. There are no automatic model retries that could silently multiply usage.

Each `attempt-*` directory holds the raw response, event stream, stderr and metrics. `status` aggregates elapsed time and reported input, cached-input and output tokens. Missing usage is reported as unknown, not zero. These are usage measurements, not a dollar invoice; no hard-coded pricing estimate is applied.

The [20-paper extraction pilot](experiments/extraction-pilot/README.md) freezes the observed model/prompt comparisons and their evaluation audits. Its offline summary command checks per-paper totals and manuscript tables without launching workers. Those audits measure extraction errors; they are not an approval requirement for production ingestion. Schema checks enforce conventions but cannot guarantee that a paper was interpreted correctly.

## Citation-ranked expansion

For age/era-adjusted ordering of new papers, use:

```sh
python3 -m bsm_atlas harvest select --ranking year-normalized --output-dir .harvest/year-normalized-hepph --count 1000
```

The score is a paper's current citation count divided by the mean current citation count of hep-ph works first posted to arXiv in the same year. The denominator uses the complete INSPIRE hep-ph population, including uncited and previously harvested works, not only the top-cited sample. An INSPIRE work counts once; multiple eprints use their earliest arXiv posting year. Zero-citation cohorts receive zero scores. Exact rational scores are sorted with arXiv identifiers as the tie-breaker. Known works are excluded before pinning the next 1,000 new papers. The raw metadata, cohort totals, catalogue digest and selected versions are frozen privately for resume; retrieval makes no model calls. This ordering is a sampling heuristic: within-year ages, citation noise in recent cohorts and differing research communities remain relevant.

Freeze the most-cited hep-ph arXiv works across all years, including cross-listed papers:

```sh
python3 -m bsm_atlas harvest select --output-dir .harvest/most-cited-hepph --count 1000
python3 -m bsm_atlas harvest expand .harvest/most-cited-hepph/papers-1000.json --run-dir .harvest/most-cited-hepph/run
# Add --execute to start retrieval and model calls; --codex can select the current CLI.
```

Selection uses INSPIRE's total citation count, including self-citations, at the saved retrieval dates. It does not filter for BSM relevance or remove papers already in the bibliography. Citation ties are resolved by arXiv identifier; cutoff ties are retrieved before selection is frozen. Distinct arXiv records referring to an explicitly identified expanded version of the same published work count once, with the alias and supporting metadata retained. Ambiguous merged records stop selection for review rather than silently changing the sample. Versions, titles and authors are then pinned through arXiv metadata. The selection directory stores the original metadata responses and hashes so the same list can be resumed without re-ranking.

When INSPIRE groups an original paper with an addendum or erratum, the original represents that record for sampling only if the related arXiv title explicitly names the exact original title, the authors match, and both papers have distinct, nonempty DOIs. The relationship is retained in selection metadata; it does not merge the two papers in the atlas or assert that their contents are identical.

Expansion uses a rolling pool of isolated workers: when one finishes, another prepared paper can start without waiting for the others. The default is two concurrent workers; `--workers` accepts up to eight. A single fetcher retrieves sources serially, respecting arXiv's request delay, while extraction runs. It prepares papers in batches of five by default and keeps a bounded buffer rather than downloading the entire collection in advance.

A failed worker execution with missing usage, an authentication/quota error, an arXiv access/rate-limit response or a retrieval batch blocked by connection failures stops new submissions and drains existing calls. Paper-specific size, format and missing-source problems are flagged individually while the batch continues. There are no automatic model retries or purchases. Each valid response is automatically ingested; an exact canonical match gains paper references instead of a duplicate model. Successfully retrieved papers and completed responses survive interruptions, and resume imports valid cached responses left by a previous interruption without making another model call.

```sh
python3 -m bsm_atlas harvest status .harvest/most-cited-hepph/run
python3 -m bsm_atlas harvest expand .harvest/most-cited-hepph/papers-1000.json --run-dir .harvest/most-cited-hepph/run --execute --resume
```

Use the same explicit settings when resuming. To change the worker count, first place a `STOP` file in the run directory and wait until the coordinator reports `stopped` with no running jobs. It finishes active calls without submitting replacements. Remove the marker, then explicitly reconfigure the stopped run, retaining its other settings:

```sh
python3 -m bsm_atlas harvest expand .harvest/most-cited-hepph/papers-1000.json --run-dir .harvest/most-cited-hepph/run --workers 6 --execute --resume --reconfigure
```

Only worker count and fetch-batch size can change this way; the manifest, prompt context, model, reasoning level and other recorded settings remain fixed. Completed responses are not rerun. An interrupted `running` job requires inspection and an explicit retry rather than an automatic duplicate call. Failed downloads can be retried with `harvest prepare ... --resume --retry`; failed or invalid workers with `harvest run ... --retry --execute`. `expansion-status.json` records the current phase, process ID, worker limit, counts and token totals. `extraction_complete` means every selected paper has either been attempted or skipped as already recorded and valid output has been ingested. Failures may remain unresolved. Long runs execute locally and require the computer to remain running.

Progress updates on worker completion and at least every 30 seconds while work is active. Token totals reflect completed calls; a long active call need not have reported usage yet. More concurrent workers can reduce elapsed time, but do not reduce the total extraction tokens. Changes to source preparation do not override the new-only admission rule: revisiting recorded papers is a separate, explicit follow-up, not part of normal expansion.

## Inspect or import saved results

```sh
python3 -m bsm_atlas harvest inspect .harvest/pilot 1905.13729v1
python3 -m bsm_atlas harvest ingest .harvest/pilot
python3 -m bsm_atlas harvest ingest .harvest/pilot --write --rebuild
make check
```

Inspection is optional and read-only. `ingest` previews saved valid results; `--write` imports them without an approval record or another model pass. The writer registers missing papers, merges exact canonical duplicates and validates all four derived views before atomically replacing the source. Existing paper IDs are reused. A colliding model URL slug is disambiguated using its canonical fingerprint; a name never defines mathematical identity. Re-ingestion is idempotent. A failure before source replacement leaves the entire catalogue unchanged.

Single-entry and batch writers use the same OS-backed lock on macOS/Linux. A competing writer fails explicitly rather than overwriting another process's update. Invalid and retriable results never add model entries. Small private `ingestion.json` receipts record imported result hashes and canonical entry IDs; they are not another database or approval layer. Legacy approval files do not control intake. `--rebuild` regenerates website and SQLite/CSV/JSON exports after writing the source; if export fails, the command reports that the source was saved and asks you to rerun `make build`.

`--source another-catalogue.json` supports isolated rehearsals; it cannot be combined with `--rebuild`. The coordinator never commits, pushes or deploys automatically.

## Implementation references

The worker interface follows [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) and its [CLI reference](https://learn.chatgpt.com/docs/cli/reference). Retrieval follows the [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html) and [access limits](https://info.arxiv.org/help/api/tou.html).
