# Paper extraction pilot

This exploratory study tests whether a paper-isolated language-model worker can recover complete gauge-algebra and matter specifications in the atlas conventions. Each configuration processes the same 20 pinned papers. Source review found errors that structural validation alone cannot detect, including missing fields and incorrect decisions to skip papers. Escalating only jobs marked unresolved would leave these failures uncorrected.

The results below describe this pilot, not accuracy across the BSM literature. They do not evaluate the correctness of the pre-existing atlas catalogue. No pilot result was ingested into that catalogue.

## Corpus and procedure

The papers are the first 20 records of an arXiv query for the newest 1,000 papers cross-listed in `hep-ph`, sorted by original submission date. The feed was retrieved on 22 October 2026 at 22:23 UTC; all 20 papers were submitted on 21 October. This is a consecutive, recent sample, not a BSM-only, random, citation-selected or balanced evaluation set. The planned most-cited-1,000 corpus has not been processed.

Each call receives exactly one full paper, its pinned bibliography, the atlas conventions and schema, SM/MSSM reference inventories and examples. An ephemeral Codex CLI worker returns structured candidates without tools, web access, previous answers or permission to write the catalogue. Code normalizes representations and charges and checks structural validity; a separate coordinating-assistant source audit examines completeness and eligibility. The audit uses five independently reconstructed reference inventories, not an exhaustive list of every eligible description in the corpus. It is not blind expert annotation or an inter-reviewer agreement study.

All configurations use medium reasoning and CLI 0.163.0. One paper is run first, followed by the other 19 with two workers. Every paper has one attempt per configuration; there are no automatic model retries. Download recovery is separate from model retries. The same source text bytes and bibliography are used throughout. Token counts can differ despite identical input text because the usage counters include model-dependent processing and overhead.

Workers return `entries`, `skip` or `retry`. The last means extraction needs another attempt or source/convention review; it is not a scientific property of a model. Job outcomes and review decisions are processing records, separate from the atlas database, which accepts only complete reviewed specifications.

## Prompt versions

- **v1:** the original complete-BSM extraction instructions, used unchanged for GPT-5.6 Terra, GPT-5.6 Sol and GPT-6 Sol.
- **v2:** explicitly requires complete SM extensions, including unified models; excludes standalone toy or calculation-only sectors without inventing missing SM fields; distinguishes a complete low-energy EFT from an incomplete higher-scale setup; and requires a nonempty reason for every outcome. Used unchanged for revised Terra, GPT-6 Luna and GPT-6.1 Sol.

Comparisons within each version keep full prompts identical, not just the paper text. Comparisons across versions confound prompt and model changes. There is only one run per configuration: the prompt revision followed inspection of v1 results, and there is no held-out test or variance estimate. Requested model aliases are recorded; immutable backend snapshots were not captured. The extraction implementation was uncommitted during the tests; export-time code hashes are recorded, but are not an immutable per-run code release.

The complete instruction prefixes are frozen in [v1](prompts/v1.txt) and [v2](prompts/v2.txt). Paper metadata, text hashes and full-prompt hashes in [results.json](results.json) identify the per-paper inputs. Full paper texts and raw worker/event files remain in private `.harvest/` working directories rather than being rehosted here.

## Results

<!-- BEGIN PILOT RESULTS -->

| Model | Prompt | Matched responses | Correct skips | False skips | Scope errors | Faulty responses | Pending |
|---|---|---:|---:|---:|---:|---:|---:|
| 5.6 Terra | v1 | 4 | 12 | 0 | 2 | 0 | 2 |
| 5.6 Sol | v1 | 5 | 13 | 0 | 1 | 1 | 0 |
| 6 Sol | v1 | 5 | 13 | 0 | 1 | 1 | 0 |
| 5.6 Terra | v2 | 4 | 14 | 1 | 0 | 0 | 1 |
| 6 Luna | v2 | 0 | 14 | 3 | 0 | 2 | 1 |
| 6.1 Sol | v2 | 4 | 14 | 1 | 0 | 0 | 1 |

<!-- END PILOT RESULTS -->

Each row accounts for all 20 paper responses in mutually exclusive categories:

- **Matched responses:** every proposed inventory in the paper response matches a source reconstruction. This counts paper responses, not spectra, newly discovered theories or database additions, and does not by itself certify reference locators.
- **Correct skips:** source review found no eligible complete SM-extension inventory for the supplied description.
- **False skips:** the worker returned `skip` for a previously source-validated eligible description.
- **Scope errors:** a structurally valid proposal describes an isolated reduced theory, not a complete SM extension.
- **Faulty responses:** invalid response/intake data or a structurally valid but source-incomplete proposal. A response containing several candidates is counted once here if the response is blocked; individually valid fragments are not silently rescued.
- **Pending:** the worker returned `retry`, or the coordinator deferred source/convention review of a valid proposal. These distinct cases are recorded separately in the data. Pending review is not an incorrect answer or a worker abstention.

The three v1 runs proposed 6, 8 and 8 raw entries, respectively. Sol's two proposals in the higher-spin paper remain in the denominator of response-level reporting even though the whole response is blocked. No single accuracy percentage is reported, since these categories mix selection, mathematical inventory and output-contract failures, and the source reconstruction is not exhaustive. A scope error or faulty proposal can also conceal a missed eligible description in the same paper.

GPT-6.1 Sol proposed six spectra across five papers. Four paper responses, containing five spectra, passed source comparison: four of the five original reference inventories and one additional modular seesaw EFT. The inflaton description was falsely skipped. Its sixth spectrum, an MSSM/gravitino proposal, passes intake validation but remains pending higher-spin source/convention review; it is not counted as a model error or a worker retry.

The additional EFT in [additional-spectra.json](additional-spectra.json) was reconstructed after inspecting the GPT-6.1 output, not included in a held-out reference set. Section 4.1 explicitly integrates out the three neutrino chiral multiplets, leaving MSSM matter and the dynamical modulus chiral multiplet. Its gauge–matter inventory matches the existing NMSSM structural class, although its interactions and interpretation differ. This is an additional source-supported description, not evidence of physical novelty or exhaustive recall. The original five reference inventories remain unchanged.

## Observed failure modes

The [pseudo-Dirac doublet paper](https://arxiv.org/abs/2610.29335v1) distinguishes model selection from representation arithmetic. Original Terra accurately extracted the reduced electroweak theory in Appendix D, but missed the eligible Section 2.1 EFT: inherited SM matter plus independent LH Weyl doublets `(1,2,+1/2)` and `(1,2,-1/2)`, with charges `+3,-3` under `q=6Y`. The three Sol runs and revised Terra recovered that EFT. Luna instead combined the doublets with three neutrinos from the cosmological setup without establishing an intermediate description that omits its inflaton; its entry ID also failed the URL-slug rule.

The [Fricke modular model](https://arxiv.org/abs/2610.29754v1) shows why schema validity is insufficient. Luna omitted the three sneutrino complex scalars and the dynamical modulus chiral multiplet. In atlas units the deficit is eight real scalar singlets and one LH neutral Weyl field. Its remaining inventory passed the mathematical validator. Removing exactly those components from the independently reconstructed inventory reproduces the proposed specification.

The stricter prompt eliminated Terra's reduced-sector scope proposals but caused it to skip the [real-inflaton extension](https://arxiv.org/abs/2610.29967v1), recovered under v1. The adopted Higgs-portal interaction fixes the real inflaton to be an SM singlet. Luna also skipped this description, the explicitly adopted [MSSM low-energy EFT](https://arxiv.org/abs/2610.29978v1), and the [Majorana-singlet/charged-scalar portal](https://arxiv.org/abs/2610.29543v1). These three false skips would not enter a queue restricted to `retry` outcomes.

The [spin-3/2 paper](https://arxiv.org/abs/2610.29598v1) requires further review of the constrained gravitino representation and the selected description. Terra and Luna abstained. Sol 5.6's response used scalar-only `real_module` on a Lorentz vector in its electromagnetic toy candidate. Sol 6 avoided that error, but supplied an empty response reason, blocking the envelope. Its individual mathematical specifications validate; that is not source approval or a resolution of the higher-spin convention. The electromagnetic toy remains outside the chosen SM-extension scope.

Sol 5.6 and Sol 6 recovered the real-inflaton spectrum but refer to its Bremsstrahlung and scattering subsections as 4.2/4.3, while the supplied main source places them in the fifth section. Publication needs corrected locators even though the inventory match is exact. Sol 6.1 instead skipped this source-supported inventory, as revised Terra did.

## Tokens runtime and illustrative cost

<!-- BEGIN PILOT USAGE -->

| Model | Prompt | Input tokens | Cached input | Output tokens | Wall seconds | API equivalent USD |
|---|---|---:|---:|---:|---:|---:|
| 5.6 Terra | v1 | 1,062,142 | 165,888 | 6,780 | 86.8 | 1.907 |
| 5.6 Sol | v1 | 1,040,206 | 81,152 | 15,765 | 200.2 | 4.184 |
| 6 Sol | v1 | 1,048,790 | 103,680 | 14,024 | 160.3 | 2.051 |
| 5.6 Terra | v2 | 1,067,706 | 172,288 | 6,802 | 57.6 | 1.907 |
| 6 Luna | v2 | 1,055,982 | 78,848 | 5,535 | 70.6 | 0.101 |
| 6.1 Sol | v2 | 1,069,862 | 20,992 | 11,377 | 193.1 | 2.214 |

<!-- END PILOT USAGE -->

Cached input is included in input tokens. Separately reported reasoning-output counters are retained in the machine-readable record and are not added to output a second time. Wall time is the sum of the first-paper and remaining-19 invocation measurements, not a sum of concurrent worker times. It excludes preparation, download recovery and source review; it is not end-to-end curation throughput.

For input `I`, cached input `C` and output `O`, the illustrative API equivalent is `((I-C)*p_input + C*p_cached + O*p_output)/1e6`. Standard short-context USD rates per million tokens, verified on 23 October 2026, are:

| Model | Input | Cached input | Output | Source |
|---|---:|---:|---:|---|
| GPT-5.6 Terra | 2.00 | 0.20 | 12.00 | [Official model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra) |
| GPT-5.6 Sol | 4.00 | 0.40 | 20.00 | [Official model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |
| GPT-6 Sol | 2.00 | 0.20 | 10.00 | [Official model page](https://developers.openai.com/api/docs/models/gpt-6-sol) |
| GPT-6 Luna | 0.10 | 0.01 | 0.50 | [Official model page](https://developers.openai.com/api/docs/models/gpt-6-luna) |
| GPT-6.1 Sol | 2.00 | 0.10 | 10.00 | [Official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |

All calls were below 272,000 input tokens; cache-write counters were zero. These are frozen rate assumptions, not an actual invoice. The tests used existing ChatGPT authentication, whose account-wide rounded quota percentages do not isolate per-model consumption. Review, orchestration, infrastructure and future retry costs are excluded.

<!-- BEGIN PILOT TOTALS -->

The 6 runs (120 calls) total 6,344,688 input and 60,283 output tokens, 768.6 extraction-wall seconds, and approximately USD 12.36 at the frozen illustrative API rates.

<!-- END PILOT TOTALS -->

This is not a budget forecast for longer, older or citation-selected papers. Sol 6.1's lower per-token rates than Terra do not imply a lower cost for every run: its observed API equivalent was about $2.21 versus revised Terra's $1.91, with more output and much less cached input. GPT-6.1 Sol is now the configured extraction default; source review remains required.

## Implications for extraction

A cheap-first-pass design must check more than whether a worker reports uncertainty. Proposed inventories need source review; invalid and unresolved outputs need correction; skipped papers need an independent coverage check. Luna's one `retry` would escalate only one of the six source-flagged papers in this pilot, leaving three false skips and two faulty proposal responses. No stronger-model fallback has yet been tested, so this study does not establish the cost or recovery rate of such a cascade.

The observed results motivate a broader, independently reviewed evaluation with separate prompt-development and held-out papers, repeated runs and explicit eligibility labels. They do not establish a general ranking of model capabilities. In particular, the pilot is dominated by papers outside the atlas's model-inventory scope; headline success rates would be misleading.

## Reproduce and extend the record

From the repository root, check the portable snapshot and both manuscript/report tables without model calls or access to private paper texts:

```sh
python3 -B experiments/extraction-pilot/summarize.py
```

The frozen bundle contains the 20 versioned bibliography records and text hashes, all per-paper structured worker responses and outcome/usage records, prompt versions and hashes, the response schema, the original five reference spectra and the explicitly post-hoc additional EFT reference, validator/source-audit notes and rates used in the calculation. Response payloads include the proposed mathematical inventories so their failures can be inspected. It stores no API keys, account identifiers, full article texts or chain-of-thought traces. It is research documentation, not an atlas exclusion table.

To rebuild the bundle from the existing private run files and refresh only the marked numeric rows:

```sh
python3 -B experiments/extraction-pilot/summarize.py --import-local --refresh-tables
```

This importer makes no model calls and never writes the scientific catalogue. Adding a new experiment requires a new immutable run directory and an explicit addition to the run registry in `summarize.py`; existing measurements should not be overwritten by a retuned prompt. A future public release should also pin the tested workflow code and model snapshots, obtain independent source review and archive the exact allowed inputs. Hashes document the current inputs but cannot reproduce a nondeterministic hosted model's output bit for bit.
