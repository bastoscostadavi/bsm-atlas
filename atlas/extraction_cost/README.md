# Re-extraction effort and cost

The first pilot covers P04, P01, P02, P03 and P05, starting with the incomplete left–right entry. The scientific outputs and per-paper run ledger are staged in `../reextraction/`; the remaining seed papers form a resumable queue. A pilot is not a claim that all 50 papers have been re-read. Neither the original database nor the public website is changed automatically.

`baseline.json` is an intentionally Git-ignored, local-only account snapshot with illustrative pricing assumptions. No per-agent tokens, dollars, or provider GPU hours are currently observable through the available launch/usage tools; these values stay null, not zero. Account-wide percentage differences cannot isolate this extraction from other account activity; personal account allowance details are not published with the scientific atlas.

## Measurements to retain

For each paper, record its pinned version, source URL/local filename, inspected scope, source bytes, start/end timestamps, retrieval attempts and failures, completed/partial/blocked status, number of candidate spectra and preflight outcomes. Separate source access from scientific work where timing supports this. Measure the deterministic preflight's elapsed/CPU time independently of model inference. Do not present document word counts as billed token measurements, or wall time as GPU time.

If actual model telemetry later becomes available, retain every call's model, mode, context tier, input, cached input, output including reasoning, and applicable cache-write usage. Include extraction, retries, review and orchestration. Missing call usage is unknown, not free. Cached input is included in reported input tokens and reasoning is included in output tokens: do not double-count either. Cache-write accounting must follow the applicable provider's definition. [Official usage documentation](https://developers.openai.com/api/docs/guides/agents-api/observability) explains these distinctions; its Agents API trace mechanism is not evidence that our desktop subagent exposes that telemetry.

## Pricing illustration, not an estimate of this run

For a concrete reference, the published Standard short-context GPT-6.1 Sol API rates checked on 2026-10-16 are $2 per million ordinary input tokens, $0.10 cached input, $2.50 cache writes, and $10 output. [Official API pricing](https://developers.openai.com/api/docs/pricing).

With zero cache writes/cached reads assumed, aggregate per-paper usage across all calls of 100,000 ordinary input + 10,000 output tokens would cost **$0.30**, or **$15 for 50 identical papers**. Ten times those token volumes would cost **$3 per paper / $150 for 50**. These are arithmetic scenarios, not measured token volumes or an asserted $15–150 budget. They exclude additional tools, compute, taxes and verification beyond the stated tokens. The current agent inherits this chat's settings; no claim is made here about its exact model or speed tier.

This run uses the existing Codex session, without a separately launched API extraction or DSI compute job. Included-plan allowance and credit billing follow [Codex plan rules](https://learn.chatgpt.com/docs/pricing), not the API calculation above. No credits or additional compute have been purchased.

After the pilot, report empirical access time, scientific/validation time when separable, failures, and usable normalized spectra per paper. A small pilot provides a calibration point, not a reliable uniform extrapolation for long reviews, higher-dimensional models or ambiguous representations. Source review and extraction failures must be included in any eventual cost per accepted spectrum.
