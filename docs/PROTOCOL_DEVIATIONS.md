# Execution and analysis decisions

The feature-selection rule and all 23 cohort descriptions were frozen before study predictions. The original run plan requested 720 calls across 5 models, 2 prompt arms and 3 repetitions, including no-persona controls.

## Endpoint availability

All 144 calls were valid for each of Gemma 3 4B, GPT-4.1 mini, Qwen3 235B A22B and GPT-4.1. Gemma 3 12B produced 11 valid results, 35 outputs that failed the declared schema, and 98 requests that exhausted the bounded retry policy with upstream HTTP 429 rate limits.

The originally coded common panel across all five models therefore contained no complete cohorts. Before computing comparative error metrics, we changed the availability policy: the primary comparison uses every cohort for models with a fully complete response panel. This retains all 23 cohorts and four models. This was a **post hoc operational decision**, not part of the original fixed selection rule or an externally registered protocol.

No model was excluded because of its measured prediction error. No conditional targets were added to prompts. Invalid Gemma 3 12B keys were not repaired post hoc to manufacture comparable responses. All 720 requests and terminal results, including failures, remain archived. The incomplete endpoint is reported separately in the paper, figure and availability table.

## Operational checks and logging

Five generic connectivity/schema checks preceded the study run. They are archived under `results/smoke` and excluded from study metrics. Their prompt wording predates minor terminology clarifications made before the full run: nonexclusive mentions rather than independence, and recorded aircraft main mode. The exact full-run prompts are in `results/raw/*.request.json`.

Authentication headers were never saved. OpenRouter account identifiers returned inside error messages were removed before publication; provider names, HTTP status, error meaning, timestamps and study values were retained. The response archive is therefore exact in scientific content with explicit account-identifier redaction, rather than an unqualified byte-for-byte export of private metadata.

## Statistical interpretation

Feature selection and evaluation use the same published conditional rates. This is an exploratory in-sample aggregate benchmark. The 23 profiles overlap across dimensions; they are not 23 independent people or disjoint population segments. Variation across three model runs is computational variability and is not a survey confidence interval.
