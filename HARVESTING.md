# Harvesting papers

## Joint Luna extraction

`python3 -m bsm_atlas.joint_harvest launch MANIFEST --run-dir RUN --execute`
runs one fresh `gpt-6-luna` worker per new paper, with medium reasoning and up to
16 workers. A worker returns every eligible complete renormalizable SM extension
specified or explicitly adopted in the paper, plus paper-specific problem and
mechanism associations from the existing fixed vocabularies. The output uses the
same gauge/matter conventions and canonical duplicate reconciliation as ordinary
harvesting. Selective Terra follow-up is described below. The first call without
`--execute` previews the configuration only.

The joint runner reads exact-version, hash-verified TeX from `corpus/hep-ph/`.
It never downloads source text itself. Missing sources go into
`corpus/hep-ph/priority-requests.jsonl`, which the continuous mirror checks
between downloads. The mirror remains the sole source writer and shares the
existing arXiv pacing gate with metadata selection. It checks completed sources
again when returning to chronological work, so a prioritized paper is not
downloaded twice. TeX and paper-specific text dependencies remain in the ignored
corpus after extraction; PDFs and figures are not retained.

Models and bibliography are stored in `atlas/catalogue.json`. Positive
paper–model–problem and paper–model–mechanism links are stored separately in
`atlas/literature_links.json`, with source quotations, locators, coverage and
extractor provenance. `addresses` and `implements` preserve the meanings of the
current Problems and Mechanisms pages; a problem association is not a claim of
a demonstrated viable solution. Unclear/background assessments do not become
positive links, and missing links do not mean the model cannot have that use.
Mechanical source-check failures are flagged rather than silently certified.
The preview exporters merge new links with the existing frozen annotations.

All accepted local model IDs are remapped to canonical catalogue IDs before
their links are stored. Intake writes a recoverable validated delta before
updating the two source files; resumption replays an interrupted write without
another model call. Raw model responses and prompts are removed after durable
intake; source metadata, metrics and compact receipts remain. Terminal invalid,
failed or unavailable papers are recorded and are not automatically retried.
Quota/authentication failures stop new dispatch and drain active workers.

### Luna, Terra and deferred Sol checks

The production entry-review policy is Luna first, Terra second, and Sol later
only for completed model-inventory disagreements. Launch the second pass with:

```sh
python3 -m bsm_atlas.entry_review launch --run-dir .harvest/terra-entry-review --follow --execute
python3 -m bsm_atlas.entry_review status --run-dir .harvest/terra-entry-review --queue
```

Terra uses `gpt-6.1-terra`, medium reasoning and sixteen workers by default. Each
worker independently reads one exact-version local paper, without Luna's answer,
and extracts only its complete model inventory. Terra receives no problem or
mechanism vocabularies, annotation instructions or annotation output fields.
The full paper and gauge/matter conventions remain its source of evidence.
Problems and mechanisms remain Luna's layer.
Selection covers all model-positive papers attributed to Luna; `--follow` also
picks up newly ingested Luna papers. Skipped papers require an explicit selection.

An authorized first review of Luna's no-entry decisions with Medium, Low, or
unreported confidence can be frozen with:

```sh
python3 -B -m bsm_atlas.entry_review queue-confidence --run-dir .harvest/terra-entry-review
python3 -B -m bsm_atlas.entry_review queue-confidence --run-dir .harvest/terra-entry-review --execute
```

This selects current Luna no-entry papers with retained Luna receipts and no
prior Terra attempt. The manifest archives the exact Luna receipt and its hash.
It shares the existing sixteen-worker pool and original `jobs/` directory;
new arrivals require another explicit selection. Changed receipts are withheld,
and completed or terminal attempts are never repeated automatically. Status
includes these papers in `awaiting_first_review` and reports their subset as
`awaiting_confidence_review`. Terra still reads only the paper and inventory
conventions. A conclusive no-entry agreement can check the paper; an inventory
found by Terra replaces the empty inventory, stays unchecked, and enters Sol.
Partial or inconclusive outcomes remain separate unresolved work.

Canonical fingerprints determine agreement, independently of names. Matching
entries are marked `checked`. Valid full-text Terra corrections replace that
paper's Luna inventory, and new/corrected entries stay
`unchecked`. References from other papers are preserved; entries with no
remaining references are withdrawn. Terra skips also remain in the Sol queue,
so a deletion cannot evade later review. Invalid or incomplete results retain
the working inventory and remain unchecked in a separate Terra retry queue.
An unresolved attempt is not a completed disagreement and does not enter the
Sol queue. Changed baselines also require a fresh Terra check. No retry is
launched automatically. Quality flags prevent certification.

An explicitly authorized Terra retry pass can be queued without deleting old
jobs or routing unresolved work to Sol:

```sh
python3 -B -m bsm_atlas.entry_review queue-retries --run-dir .harvest/terra-entry-review
python3 -B -m bsm_atlas.entry_review queue-retries --run-dir .harvest/terra-entry-review --execute
```

The first command previews the eligible count. `--execute` freezes one request
for each currently unresolved/stale Terra receipt; it does not select completed
disagreements. The running coordinator polls these manifests, prioritizes first
reviews, and shares its existing sixteen slots with retries. Each request permits
one attempt, never an automatic loop. Retry jobs live under `retry-passes/`, retain
`previous-review.json`, and link earlier immutable jobs through `previous_jobs`.
The latest receipt controls checked status and queue routing. Status reports
`awaiting_requested_terra_retry`; `attempt_counts` includes historical attempts,
whereas `reviewed_papers` and the review queues count distinct latest receipts.

The Terra chat has an hourly supervision heartbeat. Its operational instructions
and deduplicated health/restart history live in the active run's `supervisor/`
directory. It checks real ownership and progress, safely resumes already
authorized work with the same sixteen-worker entries-only settings, and respects
STOP/backoff/access limits. Healthy checks and routine bounded recovery stay
quiet. New retry passes and Sol work still require explicit authorization.

`atlas/extraction_reviews.json` stores review flags separately from physics
identity, keyed by paper and entry fingerprint. Problem and mechanism
associations are separate from entry review. Terra neither compares nor certifies
the Luna associations. Original Luna receipts and evidence are preserved;
associations attach only to the same canonical inventory with a current paper
reference. Claims for replaced/withdrawn inventories remain in `detached_models`
for a later Luna annotation pass, rather than transferring to a different model.
Only applied Luna/Terra model-inventory disagreements enter the deferred Sol
queue. Annotation quality flags stay on Luna's layer; an unchecked
flag alone does not imply Sol eligibility. `status --queue` lists `terra_retry_queue` and `sol_queue`
separately, with disjoint membership. `needs_terra_retry`, `needs_sol` and
`next_pass` record this routing independently of the unchecked flag. The private
run retains the previous scientific records,
Terra comparisons, source hashes and metrics. A validated journal recovers an
interrupted write without another worker call. Completed/failed attempts are
never automatically repeated. `RUN/STOP` drains workers. This command does not
launch Sol or publish the working catalogue.

Completed worker rows are journaled immediately, before catalogue application.
An independent writer applies batches while the coordinator refills its sixteen
model slots. Dispatch uses a consistent saved baseline when the shared writer
lock is busy; application rechecks the live paper inventory before replacing it.
At most four times the worker count may be active or awaiting application, so a
blocked writer cannot create an unbounded queue of paid results. The writer loads
the shared catalogue/annotation files once per batch and writes each store once.
Full-catalogue structural validation remains mandatory; successful mathematical
checks are cached by exact specification bytes, and derived export checks run
only for changed spectra. Changed specifications cannot reuse an old check.
Resume restores missing registry receipts from completed jobs and replays saved
application journals without paid retries. Status distinguishes
`model_calls_running`, `results_waiting_apply`, and `awaiting_first_review`;
`pipeline` reports batch size and application time.

### Confidence and legacy selective Terra follow-up

Joint workers return ordinal `confidence` (`high`, `medium`, `low`) and a short
`uncertainty_reason` for every outcome, including skips. Medium/low confidence
requires a concrete reason. These are extraction metadata in compact run
receipts and the literature-link store, never part of the gauge–matter
specification or its fingerprint. Confidence is not a calibrated probability.
Older completed calls retain null confidence with `not_reported`; no confidence
is inferred retroactively. Automatic quality flags also identify invalid model
output, unresolved extraction, partial text, ambiguous attribution and failed
quotation/locator checks. A high self-rating cannot clear those flags.

The older selective-audit policy remains available for reproducing its runs:
`python3 -m bsm_atlas.quality_followup RUN1 RUN2 --run-dir FOLLOWUP --execute`
uses `gpt-6.1-terra` at medium effort for flagged papers, plus a seeded 2% audit
of both accepted inventories and skips. The initial diagnostic panel contains
up to ten papers from each of the flagged, inventory and skip strata; this panel
is reported separately from the random audit. Source failures wait for repair
instead of consuming another model call on the same missing source. Terra gets
the paper and conventions independently, without Luna's answer. Every selected
paper gets at most one Terra attempt; terminal outcomes are preserved on resume.

Compact comparisons record model fingerprints, problem/mechanism link sets,
measured tokens and the reason for selection. Agreement measures agreement,
not accuracy against an expert reference. A high-confidence Terra result that
passes the same checks can recover a failed extraction or a model missed by a
skip. Disagreement with an existing inventory or its applications is flagged
for reconciliation; conflicting spectra are not silently combined. Both model
attempts remain traceable, and raw provider responses are removed after the
comparison or recovery is durable. Retained corpus TeX is never removed.

An existing drained Luna run can adopt this protocol using
`--resume --upgrade-quality --execute`. The old configuration is saved before
the new response schema is installed. The manifest, model, effort, completed
calls and previous failures are unchanged; only future calls request confidence.

Use `python3 -m bsm_atlas.joint_harvest status RUN` for progress. A `RUN/STOP`
marker drains workers and prevents automatic relaunch. `--resume --execute`
keeps completed attempts. A bounded `--max-papers 3` smoke run can be continued
in the same directory with `--resume` and without that bound; its paid attempts
are reused. No source file, model or ranking is changed by this continuation.

## Codex and Claude batches

Both providers use one paper per fresh worker context, the same atlas prompt and
response schema, and the same deterministic normalizer and ingester. There is
no second-model approval pass. Claude Code workers run with customizations,
tools, MCP connections and session persistence disabled. They receive cleaned
paper text through stdin and return schema-constrained JSON. Use an explicit
`claude-*` model identifier; no floating alias, model fallback or automatic retry
is selected. The configured effort is recorded, not assumed equivalent between
providers. Claude prompts exceeding 300,000 characters or UTF-8 bytes are flagged
without truncation or a model call.

Paper assignments are immutable private reservations under `.harvest/allocations/`.
Every new production expansion registers its manifest. Before introducing a
second provider, register any batch already running under older code:

```sh
python3 -m bsm_atlas harvest register .harvest/existing/papers-1000.json --provider codex
python3 -m bsm_atlas harvest reserve --output-dir .harvest/claude --provider claude --count 1000 --ranking citations --population-cache .harvest/existing
```

Reservation excludes all recorded arXiv base identifiers and all papers allocated
to either provider, including papers not yet processed. It verifies primary hep-ph
classification before freezing the manifest and makes no model calls. An exact
repeat reuses the reservation; overlapping or modified manifests are rejected.
A temporary bibliography-only selection snapshot is removed after reservation.

Launch a reserved batch (replace the model placeholder with the chosen full ID):

```sh
python3 -m bsm_atlas harvest launch .harvest/claude/papers-1000.json --run-dir .harvest/claude/run --provider claude --model claude-MODEL-ID --reasoning medium --workers 1
# The preceding command is a dry run. Add --execute to launch.
python3 -m bsm_atlas harvest status .harvest/claude/run
```

The launcher detaches the coordinator, records its PID and status path, and on
macOS prevents idle sleep while it runs. Duplicate launches are rejected. Use
`--resume --execute` only after inspecting a stopped run. It does not repeat
completed or failed paper attempts, purchase credits, change models or publish.
ArXiv connections across cooperating processes share one paced request gate;
production catalogue writes wait for the shared source lock and update atomically.
Only code writes the catalogue: extraction workers have no tools or write access.

## Extractor provenance

Each measured extraction records `extractor: {provider, model, reasoning}` on
the paper, independently of its gauge–matter identity. Providers are `openai`
and `anthropic`; reasoning may be null when an older record does not establish
it. Claude's reported model identifier is used when available; the requested
identifier is also retained in private metrics. Metrics, provenance and compact
receipts survive removal of paper text, prompts and raw responses. The generated
SQLite `papers` table exposes the three fields as nullable `extractor_*` columns.
No model is attributed to a retrieval failure or unmeasured failed call.

```sh
python3 -m bsm_atlas harvest sync-extractors .harvest
python3 -m bsm_atlas harvest sync-extractors .harvest --write
```

Backfill uses actual ingested-call receipts and measured metrics, not the current
default model. Discarded pilot comparisons are not attributed to production
papers. Unestablished provenance remains absent. Do not backfill against a live
older coordinator: drain and reload it first so all writers understand the schema.

## Temporary data and compact completion tracking

**Retained problem-mapping paper cache (29 October 2026):** The user prefers to
keep the papers for now and decide about deletion later. Preserve
`.harvest/problem-mapping-luna-20261029/source-cache/`, including full text,
raw text sources and provenance, until the user explicitly requests deletion.
This cache has no expiration and must not be removed by end-of-run or ordinary
temporary-data cleanup. Its private `paper-retention-policy.json` records the
preference. This exception overrides the paper-deletion guidance below for that
cache; disposable prompts, model responses and event logs can still be compacted.

Retained TeX in `corpus/hep-ph/` is permanent local research input and must not
be deleted by extraction cleanup. Disposable paper-text copies, assembled prompts,
raw extraction responses and worker event logs are temporary. Production expansion
deletes those disposable artifacts after catalogue/progress writes have
succeeded. It retains bibliography, statuses, ingestion targets, hashes, usage and
runtime metrics in small receipts. These receipts are written atomically before
deletion, so an interrupted cleanup is safe to repeat. Ordinary resume neither
needs deleted payloads nor repeats completed or failed paper attempts.

For an older stopped run, preview cleanup and then apply it:

```sh
python3 -m bsm_atlas harvest cleanup .harvest/example/run
python3 -m bsm_atlas harvest cleanup .harvest/example/run --write
```

Cleanup takes the run lock, never removes running or unprocessed jobs, verifies
ingested results against receipts and catalogue references, and does not follow
symlinks. `--discard-uningested` explicitly retires terminal pilot/unimported
outputs without adding models. After payload removal, a deliberate new extraction
requires a fresh run and fresh paper retrieval; it cannot recover the deleted
response. Historical pilot records retain measured outcomes and hashes, not raw
worker payloads. Citation-ranking metadata is separate from paper full text.

The source caches and raw outputs described below exist only during processing;
legacy instructions for inspecting/reimporting them apply before compaction.

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

Harvest only complete SM extensions studied as renormalizable models, including unified models in which the SM is embedded in a larger algebra. Each gauge–matter entry is a discrete slot for constructing a renormalizable Lagrangian and studying its parameters and predictions. Higher-dimensional operator lists, Wilson coefficients and EFT cutoffs do not create additional slots; SM-only operator EFTs are outside the present extraction scope. Extract a separately specified complete renormalizable model when the paper provides one, not its broken-phase parametrization or the EFT remaining after its heavy fields are integrated out. Do not infer missing fields or a UV completion from effective operators. A standalone toy theory or calculation-only subset is not eligible. The word "effective" alone does not exclude an explicitly specified renormalizable model, and no further UV completion above its stated validity range is required. These are extraction instructions, not a new mandatory SM-fingerprint rejection rule.

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

New batches select only papers whose primary arXiv category is `hep-ph`, for
both raw-citation and year-normalized ranking. The selector checks arXiv's
explicit `primary_category` metadata before freezing the extraction manifest;
INSPIRE category order is not used to infer it. Cross-listed-only papers are
passed over and replaced by the next eligible works until the requested count
is reached. Missing or ambiguous primary-category metadata blocks selection
rather than being guessed. These are metadata checks, not additional model calls.
Existing entries and already-running frozen batches are unchanged.

For age/era-adjusted ordering of new papers, use:

```sh
python3 -m bsm_atlas harvest select --ranking year-normalized --output-dir .harvest/year-normalized-hepph --count 1000
```

The score is a paper's current citation count divided by the mean current citation count of hep-ph works first posted to arXiv in the same year. The denominator uses the complete INSPIRE hep-ph population, including uncited and previously harvested works, not only the top-cited sample. An INSPIRE work counts once; multiple eprints use their earliest arXiv posting year. Zero-citation cohorts receive zero scores. Exact rational scores are sorted with arXiv identifiers as the tie-breaker. Known works are excluded before pinning the next 1,000 new papers. The raw metadata, cohort totals, catalogue digest and selected versions are frozen privately for resume; retrieval makes no model calls. This ordering is a sampling heuristic: within-year ages, citation noise in recent cohorts and differing research communities remain relevant.

The full-population selector also supports raw citation ordering through
`bsm_atlas.relevance.select_population(..., ranking='citations')`. A follow-on
batch can reuse the validated frozen population metadata, exclude all papers in
the catalogue at the end of its predecessor, and select the highest-cited new
works without repeating the population sweep. Raw counts include self-citations;
ties use the lowest arXiv base identifier. The frozen source digest prevents a
changed catalogue from silently altering a resumed selection. This new-only
path is also used by the citation-ranked command below. Primary-category checks
and pinned metadata are cached with hashes for resume. The inclusive population
continues to define the original impact-score cohort means; the primary-category
restriction changes eligibility without redefining that score.

Freeze the highest-cited unrecorded primary-hep-ph works across all years:

```sh
python3 -m bsm_atlas harvest select --output-dir .harvest/most-cited-hepph --count 1000
python3 -m bsm_atlas harvest expand .harvest/most-cited-hepph/papers-1000.json --run-dir .harvest/most-cited-hepph/run
# Add --execute to start retrieval and model calls; --codex can select the current CLI.
```

Selection uses INSPIRE's total citation count, including self-citations, at the saved retrieval dates. It excludes every recorded arXiv base identifier, regardless of extraction status, and requires primary hep-ph classification. It does not pre-filter for BSM relevance. Citation ties are resolved by arXiv identifier. Distinct arXiv records referring to an explicitly identified expanded version of the same published work count once, with the alias and supporting metadata retained. Ambiguous merged records stop selection for review rather than silently changing the sample. Versions, titles and authors are pinned through arXiv metadata. The selection directory stores the original metadata responses and hashes so the same list can be resumed without re-ranking. The Python selectors also default to primary-only selection; `primary_only=False` is retained only to reproduce older frozen inclusive samples.

When INSPIRE groups an original paper with an addendum or erratum, the original represents that record for sampling only if the related arXiv title explicitly names the exact original title, the authors match, and both papers have distinct, nonempty DOIs. The relationship is retained in selection metadata; it does not merge the two papers in the atlas or assert that their contents are identical.

Separate arXiv deposits of the same publication can also share one citation
record. They count once for selection only when their DOI and journal citation
agree and their ordered author names match, allowing initials in place of full
given names. The later deposit is used for retrieval; the arXiv identifiers are
not merged in the atlas. A similar title or citation count alone is insufficient.

Expansion uses a rolling pool of isolated workers: when one finishes, another prepared paper can start without waiting for the others. The default is two concurrent workers; `--workers` accepts up to sixteen. A single fetcher retrieves sources serially, respecting arXiv's request delay, while extraction runs. It prepares papers in batches of five by default and keeps a bounded buffer rather than downloading the entire collection in advance.

Completed workers are ingested together when several results are ready, avoiding
repeated catalogue passes and source writes. Successful intake also records the
paper's completion status and extractor provenance in that same transaction.
Unchanged specifications reuse bounded, process-local calculations for numerical
normalization, identity and presentation; these exact-content caches never persist
paper text or responses and return independent copies to callers. New or changed
inputs still pass the same validation, duplicate detection and full projection
checks before acceptance. The shared writer lock and arXiv pacing remain in force.

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

Single-entry and batch writers use the same OS-backed lock on macOS/Linux. Production expansion serializes competing writes; other commands fail explicitly on a held lock rather than overwriting another process's update. Invalid and retriable results never add model entries. Small private `ingestion.json` receipts record imported result hashes and canonical entry IDs; they are not another database or approval layer. Legacy approval files do not control intake. `--rebuild` regenerates website and SQLite/CSV/JSON exports after writing the source; if export fails, the command reports that the source was saved and asks you to rerun `make build`.

`--source another-catalogue.json` supports isolated rehearsals; it cannot be combined with `--rebuild`. The coordinator never commits, pushes or deploys automatically.

## Local hep-ph TeX corpus

`corpus/hep-ph/` (gitignored) is the working location for a local mirror of
the TeX source of every paper whose primary arXiv category is hep-ph, latest
version only.

```sh
python3 -m bsm_atlas corpus index    # complete OAI-PMH set -> corpus/hep-ph/index.jsonl
python3 -m bsm_atlas corpus fetch    # serial source requests, at least 3.1 s apart
python3 -m bsm_atlas corpus status
```

`python3 -u scripts/mirror_hepph.py` first downloads papers from hash-verified,
cached arXiv primary-category responses under `.harvest/`, then builds the full
index and downloads its remaining sources. `bootstrap-index.jsonl` is explicitly
an incomplete starting batch; `mirror-state.json` records the active phase.
Rerunning resumes without downloading completed paper versions again.
The continuous runner uses the atlas harvester's existing `papers.ArxivClient`
for source retrieval from `https://arxiv.org/e-print/`, including its 3.1-second
minimum delay, shared request gate, user agent, timeout and version checks.
The corpus writer preserves raw text source members and hashes. HTTP 429 waits
for `Retry-After` when supplied, or 60 seconds otherwise, and retries the same
URL. Source pacing stays at 3.1 seconds; lifetime error counts do not extend
pauses. The previous locally imposed six-hour retry policy is retired. New
cooldown deadlines persist across restarts in `transfer-state.json` and appear
in `corpus status`. Temporary network/server failures retry the same paper
with backoff; access-denied HTTP 401/403 stops the runner. A `corpus/hep-ph/STOP`
file stops requests and cooldowns within 30 seconds (an in-flight request may
take up to its timeout). The computer must remain awake and connected.

The indexer intentionally makes its initial OAI-PMH request without a date
range. arXiv's OAI datestamps are metadata-modification dates, not submission
dates; date-window queries are unsuitable for a complete historical listing.

Each paper lands in `papers/<yymm>/<id>v<n>/` with a `source/` tree and a
`meta.json` (status, kept files with hashes, dropped members). Only text members
are kept: `.tex`, the paper's own `.sty`/`.cls` (author macros carry notation)
and any other plain-text file a document can `\input`. Figures, binaries,
bibliography files (`.bbl`, `.bib`, `.bst`) and widely redistributed journal
classes and generic packages (`STANDARD` in `bsm_atlas/corpus.py`) are dropped. Archives are read in
memory with path checks; nothing is extracted by `tarfile`, executed or compiled.
The hep-ph subset is collected serially using the shared request gate. This is
a resumable local research download.
The plain `corpus fetch` command stops on HTTP 401/403/429; the continuous runner
automatically waits and resumes on HTTP 429. arXiv recommends S3 for downloading the entire arXiv corpus.
The size of that all-category archive is not an estimate of this text-only subset.

## Implementation references

The worker interface follows [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) and its [CLI reference](https://learn.chatgpt.com/docs/cli/reference). Retrieval follows the [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html) and [access limits](https://info.arxiv.org/help/api/tou.html).


## Automatic ingestion supervision

The active first pass uses two independent supervision layers. A user LaunchAgent runs `python3 -B -m bsm_atlas.supervision --execute --quiet` every minute. A scheduled Codex heartbeat in the ingestion chat checks once an hour and diagnoses unexpected failures. Both use the actual `bsm-atlas` checkout.

The watchdog checks ownership locks, process identity, progress and backoff deadlines. It restarts only recognized stopped routing/source-access or source-transport failures, with at most three automatic restarts per component per hour. It never retries paid paper attempts, substitutes models, changes mathematical conventions, restores stale source data, or overrides STOP markers and access/quota failures. Alive workers suspected of stalling are left to agent diagnosis. A cached or restored source must still contain completed paper records before automatic recovery.

Operational configuration and compact health/events are under the active batch’s `supervisor/`; `RUNBOOK.txt` explains repair locks, maintenance markers, replay of durable results, and verified resumption. Before editing orchestration during supervision, acquire `supervisor/repair.lock` and create an owned `supervisor/MAINTENANCE` marker. Remove only that owned marker after verification. The source and model pipeline remain independent of the watchdog.

The heartbeat stays quiet for healthy or unchanged state and routine bounded restarts. It reports significant tested repairs, confirmed completion, or required user input, with deduplication. It does not start the deferred stronger-model pass or publish data. On confirmed ingestion and mirror completion, both supervision layers are disabled while scientific data and retained TeX remain intact. The Mac must stay awake; the desktop app must remain running for the chat heartbeat.


## Retrying unresolved papers with Luna

A separate recovery queue gives each selected unresolved paper one additional Luna attempt. It uses retained, verified local TeX and the same extraction conventions, validation, canonical duplicate detection, and intake as the first pass. Missing or unreadable sources are deferred without a model call. Original attempts remain intact. Successful recoveries update the paper status and merge references; failed recoveries remain available for later work.

Recovery uses at most two workers, within a shared limit of 16 paid calls. New first-pass work receives dispatch priority. In-flight retries finish normally, so a newly ready first-pass call can briefly wait for a retry to release a slot. Recovery does not download sources or change the mirror queue. Access failures stop the run; an attempt is never automatically repeated. Temporary prompts and responses are removed after durable intake; compact receipts, source hashes and usage remain.

Prepare a separate recovery selection with `python3 -B -m bsm_atlas.luna_recovery prepare`. Inspect its selection and frozen manifest before running `python3 -B -m bsm_atlas.luna_recovery run --execute`. The November 10 queue is `.harvest/luna-recovery-20261110`. The `--probe` option permits one explicitly authorized access check; it cannot be repeated within the queue.


### Catalogue update throughput

Ingestion validates the complete catalogue, merges identical gauge–matter specifications and checks that their presentation can be built. Successful mathematical validation is reused only for an exact, unchanged JSON specification; reference, metadata and duplicate checks run on every write. These bounded caches stay in memory and disappear when the process exits.

The presentation check omits derived anomaly and parameter-count calculations. The website build computes those properties through its default path. This keeps ingestion focused on complete gauge–matter specifications and paper references while preserving the published calculations. The Luna model, reasoning effort, extraction prompt, schema, charge normalization and canonical identities are independent of this scheduling optimization.

### Recovering papers blocked before extraction

After a source-preparation repair, freeze a separate queue of previously blocked
papers with `python3 -B -m bsm_atlas.luna_recovery prepare --source-only
--workers 16 --run-dir RUN`, then start it with `python3 -B -m
bsm_atlas.luna_recovery run --run-dir RUN --execute`. Preparation makes no model
calls or downloads. It checks primary hep-ph scope, surviving historical receipts
across arXiv versions, and readable hash-verified local TeX. Any prior model
attempt excludes the paper. The saved selection records the original failure
receipt and the prepared-source fingerprint; source changes prevent dispatch.
The run retains original attempts, uses Luna at medium effort and shares the
sixteen-call Luna limit. It performs one call per selected paper, reconciles valid
models through the existing canonical intake, and does not retry terminal jobs.

TeX preparation follows literal paper dependencies, preserves local package
definitions as unexecuted source text, and recognizes legacy bibliography
environments. Standard graphics-only inputs do not require a local TeX
distribution. An explicit arXiv top-level declaration can distinguish the paper
from backup drafts; otherwise genuinely different independent documents remain
ambiguous. Missing scientific sections and unresolved dynamic dependencies stay
deferred. Original TeX remains unchanged on disk.

### Additional parser profiles without interrupting a run

An active source-recovery queue keeps its selected preparation profile and exact
source fingerprints. Profile `tex-v3` is opt-in for a separate queue; profile 2
remains available unchanged for reproducible resumes. Select only the earlier
queue's deferred papers and exclude its entire reserved manifest:

```sh
python3 -B -m bsm_atlas.luna_recovery prepare --source-only \
  --preparation-profile tex-v3 --candidates-from PREVIOUS/source-deferred.json \
  --exclude-manifest PREVIOUS/manifest.json --workers 4 --run-dir NEXT
python3 -B -m bsm_atlas.luna_recovery run --run-dir NEXT --execute
```

The queues share the existing sixteen paid-call slots. Historical attempts are
checked by arXiv base ID across versions before selection; a queued paper cannot
enter the additional manifest. Profile 3 supports active-character and one-token
macro definitions, literal include wrappers and filename constants, subimports,
starred includes, literal source listings and substantial plain-TeX documents.
Explicit backups and referee correspondence can be distinguished from the paper;
genuinely competing manuscripts remain ambiguous. Input-only wrappers are
assembled with their preambles and bodies, and a resolved document terminator is
required. Unknown conditionals cannot select an arbitrary filename or loader.
Missing scientific files, unavailable source archives and remaining unsupported
constructs stay deferred. Original source files are never rewritten.
