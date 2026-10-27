# GPT-6.1 Terra: matched pilot follow-up

On 26 October 2026, GPT-6.1 Terra processed the same 20 versioned papers and
byte-identical v2 prompts as the recorded GPT-6.1 Sol pilot. Both used medium
reasoning, one first-paper call followed by two workers for the remaining 19,
and one attempt per paper. No results were ingested into the atlas. The production
model remains GPT-6.1 Sol.

| Measure | GPT-6.1 Terra | GPT-6.1 Sol |
|---|---:|---:|
| Matched paper responses | 4 | 4 |
| Matched spectra | 4 | 5 |
| Correct skips | 14 | 14 |
| False skips | 1 | 1 |
| Invalid or out-of-scope responses | 0 | 0 |
| Unresolved higher-spin case | 1 | 1 |
| Input tokens | 1,067,834 | 1,069,862 |
| Cached input tokens (included above) | 142,592 | 20,992 |
| Output tokens | 6,377 | 11,377 |
| Extraction wall time | 65.1 s | 193.1 s |
| Illustrative API equivalent | USD 0.964 | USD 2.214 |

Terra recovered the MSSM, the MSSM with three neutrino chiral multiplets and a
dynamical modulus, the Majorana-singlet/charged-scalar portal, and the SM plus
two independent Weyl doublets. Their complete normalized inventories exactly
match the saved reference spectra. Both models falsely skipped the real-singlet
inflaton extension. These are inventory comparisons; they do not independently
certify every source locator.

The response-level counts conceal a coverage difference. In the modular-seesaw
paper, Sol also recovered the explicitly described low-energy EFT obtained after
integrating out the neutrino multiplets. Terra returned only the higher-energy
inventory. Thus Terra recovered four of the five original reference spectra,
as Sol did, but not the additional post-hoc EFT reference. Sol recovered five of
the six known reference spectra in total; Terra recovered four.

The higher-spin case is not an established model error for either run. Terra
returned `retry`; Sol returned a structurally valid MSSM/gravitino candidate whose
source/convention adjudication remains deferred in the original study. These are
different kinds of unresolved outcome, not equivalent answers.

Terra's measured extraction wall time was about three times shorter. Its
illustrative API equivalent was about 56% lower. The calculations use Terra's
[official standard API rates](https://developers.openai.com/api/docs/models/gpt-6.1-terra),
verified on 26 October 2026: USD 1.00 input, 0.05 cached input and 5.00 output per
million tokens, and the Sol rates frozen in the original study. All calls were
below 272,000 input tokens and reported no cache writes. Cached input is a subset
of total input; reasoning tokens are not added to output again. These are not
subscription charges or an invoice, and exclude preparation and source review.

This is one small run, dominated by papers without eligible models, not evidence
that the two models have equal accuracy across arXiv. The extra EFT reference was
constructed after the original Sol run, not independently held out. The replay
retained the frozen prompt and source bytes but used the current worker/validator;
its code hash and CLI version are recorded. Cache hits differed, and production
harvesting was running concurrently, so the latency comparison is observational.
No original pilot measurements or labels were overwritten.

The compact [result snapshot](terra61-results.json) retains the 20 outcomes,
response/input hashes, reference fingerprints, measured usage and protocol.
Raw source, per-paper prompts, responses and worker event logs have been deleted.
The private run directory retains only compact bookkeeping. To verify this
snapshot without model calls or catalogue writes:

```sh
python3 -B experiments/extraction-pilot/compare_terra61.py
```
