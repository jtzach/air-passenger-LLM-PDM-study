# Fresh MiD and Munich benchmark: frozen design

This design supersedes the exploratory `SEQUENTIAL_PROTOCOL_DRAFT.md`. The previous three-repetition study remains a separate pilot. Fresh results are not yet stated in this protocol. The machine-readable freeze records the timestamp, configuration hash, exact request hashes and executable code hashes before the first call.

## Questions and information supplied

1. MiD: can group descriptions predict three nonexclusive mode mentions on aircraft-main-mode overnight journeys? Does supplying the overall public survey rates help?
2. Munich: can six generic trip-purpose × departing-flight-region descriptions predict the distribution of reported access categories at Munich Airport? No airport rates are supplied to the models.

The MiD cards and full wording are unchanged from the pilot: 23 single-attribute groups, selected from public survey aggregates. The same observations both selected and evaluate the cards. This is an in-sample aggregate benchmark, not a held-out individual prediction test.

The six Munich cards cross business/private purpose with domestic/continental/intercontinental departing flights. These two dimensions were requested before inspection of the uploaded FMG workbook. Other passenger characteristics are unspecified. No residence assumption, trip-duration extension, cross-year geography combination, or synthetic 70-persona distribution is used. The 2025 summary's 30 native groups are aggregated locally to six observed groups, using annual passenger-volume weights. Expanded volumes are not interview sample sizes. The source summary's reported access-category coding is retained; a parking transfer is not reclassified as bus simply because the final vehicle is a shuttle. Original question wording, boundary-country assignments and survey sample design remain unverified.

MiD models receive either a group description only or that description plus the public population-level rates. Both conditions withhold group-specific targets. The Munich condition receives only a generic description and the requested outcome categories. A separate no-group control is queried for every model/panel/condition/round. A deterministic statistical baseline assigns the matched overall observed rates to every group; it is computed locally and is not an LLM.

## Confidential data boundary

The supervisor confirmed on 25 November 2026 that FMG permits publication of derived results, but not external LLM processing of its data. The workbook, row-level extracts and scoring configuration stay outside the public repository. The only Munich material transmitted is independently written generic study questions and commonplace access-option descriptions. No source table, source wording, passenger volume, population weight, conditional rate or numerical airport hint enters an API payload. Public MiD rates are allowed in the MiD hint condition. Tests verify that changing private targets, weights, baselines and descriptions cannot alter a prepared request. The prompt library is reviewable separately from the private configuration.

## Models and repetitions

- Gemma 3 4B: `google/gemma-3-4b-it`, pinned `parasail/bf16`.
- GPT-4.1 mini: `openai/gpt-4.1-mini`, pinned `openai`.
- Qwen3 235B A22B: `qwen/qwen3-235b-a22b-2507`, pinned `deepinfra/fp8`.
- GPT-4.1: `openai/gpt-4.1`, pinned `openai`.

Provider pins were selected using the pilot's working providers and the public endpoint catalogue, before fresh outputs. Fallbacks are disabled and parameter support is required. Model sizes are not a controlled experimental factor; commercial sizes are undisclosed. Temperature is 0.7, maximum completion length 450 tokens, and the round seed is 25112026 + round − 1. Requests are shuffled within each round using the same round-specific seed recipe. Eight concurrent calls are permitted. Different seeds and unique response IDs do not prove independence.

A complete MiD round contains 23 group requests and one no-group control for a given model and condition. A complete Munich round contains six group requests and one control. Across all blocks this is 220 calls per round, at most 14,080 terminal requests before retries. A block is one model × panel × condition. There are 12 blocks: eight MiD and four Munich. Gemma 3 12B is not rerun because it failed operationally in the pilot; this choice precedes fresh outputs.

## Scores and inference

For each complete round calculate one mean absolute error (MAE), in percentage points, across all fixed group/mode cells. MiD uses equal weights for its four attributes and three outcomes, with population weights among groups within each attribute. Munich uses six group population weights and equal weights for ten access categories. These are different tasks; raw MAE levels across the two panels do not measure relative task difficulty on a common scale.

Let B be the deterministic baseline's panel MAE and L(r) the fresh round's MAE. The primary quantity is the median of B − L(r) over repeated service calls. Positive means improvement. This is not the MAE of the average prediction vector; that ensemble score is reported descriptively and separately. Group cells are not independent experimental repetitions.

Scheduled inspections are at **16, 32 and 64 complete rounds**. Exact binomial order-statistic median intervals receive alpha 0.04 / (12 × 3), with the divisor unchanged after failures or early stops. The practical margin is **0.5 percentage points** of panel MAE. Stop a block when its interval establishes improvement above +0.5, degradation below −0.5, or median equivalence inside [−0.5,+0.5]. An interval of width at most 0.5 that still crosses a decision boundary permits a precision stop, explicitly inconclusive. Otherwise continue to the next scheduled inspection, with an inconclusive report at 64 if necessary. Adjusted directional p-values account for both directions, all 12 endpoints and all three looks, and are compared with 0.04.

Secondary bounded-mean betting confidence sequences receive alpha 0.01 / 12, one per baseline-improvement endpoint. These estimate mean rather than median gain and can remain wide. They are not substituted for the primary intervals. No-card comparisons, hint comparisons, cell differences, model rankings and behavioral interpretations are descriptive; no additional significance claims are attached to them. The two formal families have a combined nominal error allowance of 0.05 under their respective assumptions. See the tested `sequential_inference.py` and the detailed draft for the formulas and primary references.

The median analysis assumes independent, identically configured, stable rounds. The mean confidence sequence assumes a constant conditional mean. Provider/model drift, a reused response generation ID or missing service identity blocks formal inference and halts the affected stream. Numeric repetition alone neither establishes independence nor proves caching. These intervals concern API generation variation against fixed table targets. They do not quantify human survey uncertainty or prove causality, generalization, or respondents' motives.

## Output validity, failures and caps

MiD probabilities must each lie in [0,1] and need not sum to one. Munich's ten probabilities must each lie in [0,1] and sum to one within 0.005; within that tolerance they are rescaled to sum exactly to one, retaining the raw answer and normalization factor. No accuracy-driven repair or retry is allowed. Rationale text is retained as an unverified explanation, not evidence of motives.

At most three transport attempts are permitted for transient network failures or HTTP 408/429/5xx errors. Malformed model content is retained without retry. The first unresolved incomplete round halts that block; preceding complete rounds are retained and the failed round is not replaced or silently skipped. In-flight results are archived. Failures in the no-group control also halt the block. Partial round records are retained but do not receive a full-panel score or create a new inspection opportunity.

The hard administrative caps are **US$10** accounted cost and **7,200 seconds** from the first execution start, including resumptions. Conservative reservations use frozen catalogue prices and maximum output length. An interruption between registered looks does not authorize a new primary p-value. A saved request is never silently repurchased after an uncertain interrupted outcome. Credentials remain process-local, account identifiers are redacted, and all terminal responses, attempts and cost estimates are retained.

## Reporting and reproducibility

Report all 12 registered blocks, including operational failures, early stops and inconclusive results. Save every scheduled decision and retain original requests. Include the exact public MiD hint in a gray main-text box, explain that it does not reveal any group's answer, and distinguish no hint from no group description. Provide actual prompt text in gray appendix boxes and the complete request archive. Keep the paper within three figures and three tables; use an extended author-review draft because the requested explanation exceeds the journal's short format.

The public repository may contain code, generic prompts, model outputs, public MiD data and authorized derived FMG findings. It must not contain the airport workbook, its original row extracts or the private scoring configuration. Those remain in the authorized local/private Overleaf workflow. The co-author workbook is a secondary summary; upstream source-level verification and the survey-definition questions remain author-review limitations.
