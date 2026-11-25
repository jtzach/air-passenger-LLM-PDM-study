# Draft protocol for fresh sequential model runs

**Status: design for review, not a completed experiment or preregistration.** Freeze the final endpoint registry, source targets, prompts, model/provider settings, thresholds, looks, budget, and this code's hash before reading any new outputs. The original three-repeat experiment is pilot evidence and must remain separate. No new API calls were made to prepare this module.

## Recommended decision

- Use four fixed models: Gemma 3 4B, GPT-4.1 mini, Qwen3 235B A22B, and GPT-4.1. Keep both prompt conditions and no-group-card controls.
- Inspect at **16, 32, and 64 complete rounds**. Retire a model/panel block only at those looks when all its registered primary decisions are resolved; otherwise stop at the maximum or the hard cost/time cap and report unresolved results.
- Primary quantity: the **median single-round improvement in panel MAE over the fixed survey-rate baseline**, in percentage points. Positive values are better. Set a practical margin of **0.5 percentage points**. This asks about a typical fresh run, not average passenger behavior.
- Use exact, noninterpolated median confidence intervals with a fixed Bonferroni correction across **all registered primary endpoints and all three looks**. A favorable result is not a reason to discard an unfavorable or unresolved endpoint.
- Keep **MAE of the average predicted probabilities** as a descriptive result. Its absolute value operation makes it a different quantity from mean or median single-round MAE.
- Report a separate bounded-mean confidence sequence if desired. It may remain wide or inconclusive. Do not substitute a median result for a mean claim.

## What is one observation?

For panel d, model a, condition b, and round r, obtain a fresh prediction for **every fixed group card**. Calculate one full-panel loss:

`L[d,a,b,r] = 100 × sum_cell weight[cell] × abs(prediction[cell] − survey_target[cell])`.

Weights are frozen, nonnegative, and sum to one. For MiD they retain the existing equal-attribute/equal-mode aggregation, with survey-weighted groups within each attribute. The 23 overlapping groups and 69 cells are not independent observations. One complete round contributes **one** primary observation. Reusing one no-card answer across the panel does not multiply its sample size.

Let B[d] be the fixed panel loss of the overall-rate baseline and `D[r] = B[d] − L[r]`. The primary quantity is a median of the distribution of D across fresh, identically configured rounds. For a model-versus-model or card-versus-no-card contrast, pair losses by the preassigned round identifier; a median of paired differences is not generally the difference between two medians. Such contrasts require their own frozen endpoint/error allocation.

There are three distinct outputs:

| Output | Meaning | Role |
|---|---|---|
| Median of round improvements | Typical-run improvement; directional test asks whether more than half of runs exceed the margin | Primary sequential inference |
| Mean of round improvements | Expected improvement over repeated service calls, including tail behavior | Secondary bounded-mean inference |
| MAE after averaging predictions across rounds | Accuracy of the ensemble of probability answers | Descriptive benchmark; not the primary inference target |

## Panels and error allocation

Only panels with comparable observed conditional targets support prediction-error claims. MiD and a separately specified historical Munich Airport panel must retain distinct populations, years, outcomes, and denominators. A 2025 group forecast with no observed group target is **not validated** by a historical or unconditional percentage.

Proposed primary registry, if both panels pass source validation:

- 4 models × 2 conditions × 2 validated panels = **16 baseline-improvement endpoints**.
- Primary family error allowance 0.04, divided by 16 endpoints and 3 looks. Each two-sided interval uses `alpha = 0.04 / (16 × 3) = 0.0008333333`.
- Reserve 0.01 for a separately frozen secondary family. For example, 40 bounded-mean contrasts (16 against baseline, 16 against no-card control, 8 paired condition contrasts) each receive `0.01/40`; their confidence sequences need no additional look correction.
- These two families together have a maximum nominal familywise error allowance of 0.05, under their stated assumptions. Dependence between endpoints does not invalidate the union-bound allocation.
- If the historical panel cannot be validated, freeze the changed registry **before** fresh outputs. Do not shrink the multiplicity divisor because a model fails, a panel stops early, or a result is uninteresting.
- No formal cell-by-cell significance claims are covered by these panel allocations. A new group/mode family requires an additional preallocated budget or must be labeled descriptive. Unvalidated forecasts can have model-repeat precision summaries, but no claims of agreement with human behavior.

The 0.5-point margin and 0.25-point precision half-width are study-design choices, not source-derived universal standards. They must be finalized before the new run. They refer to panel MAE differences, not a 0.5-point change in every group's transport share.

## Exact median intervals and symmetric stopping

For n sorted improvements, choose the largest integer k satisfying

`P{Binomial(n, 1/2) ≤ k−1} ≤ alpha/2`.

The interval is `[D_(k), D_(n−k+1)]`; if no k qualifies, use the full prespecified support. No interpolation or normal approximation is used. The order-statistic construction also gives conservative coverage with tied/discrete outcomes. NIST's technical treatment gives this quantile construction and its discrete-distribution coverage bound ([NIST TN 2119, section on quantiles, pp. 32–33](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2119.pdf)).

At a registered look classify each primary interval:

1. Lower endpoint > +0.5: **meaningful median improvement**.
2. Upper endpoint < −0.5: **meaningful median degradation**.
3. Entire interval inside [−0.5,+0.5]: **median practically equivalent within the chosen margin**.
4. Width ≤ 0.5 but still straddling a decision boundary: **precise but inconclusive**.
5. Otherwise continue; at round 64 report **maximum reached, inconclusive**.

Items 1–3 are confidence statements about the median. Item 4 is a precision stop, not a directional significance claim. Median equivalence does not establish small variance, safe tails, or that every run is close. It can coexist with rare very poor outputs.

The corresponding positive-direction test counts `D > +0.5`; the negative test counts `D < −0.5`. Values equal to a threshold remain in n as nonsuccesses. The module returns conservative adjusted p-values multiplied by `2 × endpoint_count × look_count`, covering both directions. Do not round gains before applying the thresholds. For the proposed 16-endpoint, 3-look registry, 15 strict improvements among 16 rounds suffice for the positive directional test; fewer successes can require later looks.

Only registered inspections drive primary stopping. The union bound controls the probability that any registered interval misses its target at any scheduled inspection. This remains true when a block is retired early. A budget interruption between looks is reported as an administrative stop; it does not authorize an unregistered primary p-value. Retain the most recent scheduled-look inference and describe any extra partial round separately.

## Assumptions and hosted-service limitations

Exact sign/median inference assumes independent rounds drawn from the same distribution. Unique request IDs, new seeds, and identical settings help define a repeat recipe; **none proves independence**. Record the returned model/provider, request ID, seed, timestamp, request/response hashes, retry history, and cache indicators when available. Randomize request order within each preassigned round, without looking at accuracy. Pin provider routing where feasible and record unsupported seed handling. Do not treat parallel calls, shared seeds, or repeated cells as extra independent replicates.

An identical numeric vector is a diagnostic flag, not proof of independent repeats or proof of caching. A median interval may collapse around a point mass under the IID assumption; that does not prove that the mean has no uncertainty. A repeated generation ID, known response-cache reuse, provider/model switch, or material protocol drift blocks inferential claims for the affected stream. Do not repair dependence by inventing an effective sample size or counting only unique answers. Report the observed stability descriptively; obtain independent service runs only under a newly documented protocol if necessary.

The module requires the runner to explicitly acknowledge the IID assumption before it emits a primary inference decision. This records an assumption, not empirical proof. Findings should say **conditional on independent, stable repeated calls**. They do not quantify survey-sampling uncertainty, identify causes, prove generalization to new passengers, or establish actual human motives. Published survey targets are fixed comparison values; aggregate tables do not supply the design information needed for respondent-level uncertainty.

## Failed or incomplete rounds

Freeze failure handling before calls. Recommended options for the runner to choose explicitly:

- A fixed attempt/retry recipe is part of the modeled service. Never retry based on prediction accuracy. Retain every attempt and final malformed/error response.
- For a purely valid-output accuracy target, halt an affected block at its first unresolved incomplete round; retain its preceding complete prefix. Do not skip the failed round and keep drawing until enough favorable/valid rounds accumulate. Report availability separately. This is operationally conservative and may end a block early.
- If continued operation despite failures is essential, preregister an **end-to-end operational loss** with a fixed failure penalty, such as the known maximum loss for the missing cell. Then every planned round has a score, but the estimand explicitly combines availability and accuracy. Keep valid-output MAE separate.

Do not silently switch between these policies after seeing which models fail. A common fixed complete panel and weights are required for each score; never compare each model on whichever groups happen to return.

## Secondary bounded-mean confidence sequence

The module implements a transparent fixed-mixture betting construction. Normalize a quantity with known support [a,b] into X in [0,1]. For each prespecified fraction c, its positive-direction wealth against candidate mean m multiplies factors `1+c(X/m−1)`; the other direction uses 1−X and 1−m. Average the wealth over the frozen fractions `(0.01,0.03,0.1,0.3,0.5,0.7,0.9,0.99)` and compare each side with `2/alpha`. Nonnegative betting martingales plus Ville's inequality give coverage simultaneously at all times under a constant conditional-mean assumption. This is a simple special case, not a claimed reproduction of the optimized algorithm, in [Waudby-Smith and Ramdas, JRSS-B 2024](https://doi.org/10.1093/jrsssb/qkad009), with the [public full manuscript, sections 2 and 4](https://arxiv.org/pdf/2010.09686). General time-uniform theory is developed by [Howard et al., Annals of Statistics 2021](https://doi.org/10.1214/20-AOS1991).

Use known support bounds, never the observed min/max. A panel's maximum possible MAE is `U = 100 × sum weights × max(p,1−p)`, so baseline improvement lies in [B−U,B]; a paired loss difference lies in [−U,U]. Unlike a t interval, the bounded-mean CS remains nonzero in width after identical answers. With 64 rounds, simultaneous bounds may still be too broad to certify a 0.5-point mean improvement. That is a valid inconclusive outcome, not a reason to narrow the support retrospectively.

## Resources, audit, and integration

For G group cards in a panel, each round costs `4 models × 2 conditions × (G+1)` requests when a separate no-card control is included. With 23 MiD cards, 4 historical cards, and 5 prospective cards, this is **280 requests per full round**, or 17,920 at 64 rounds before retries. Stop retired blocks independently only as permitted by the frozen registry. Actual price and runtime depend on service/provider/output length; the pilot's cost is not a guarantee. Root runner must enforce the approved hard dollar/time/attempt cap and report why each block stopped.

Before the first fresh call, archive a manifest containing the final endpoint IDs, targets/weights and hashes, thresholds, look schedule, alpha allocations, model/provider parameters, seed/order recipe, failure policy, maximum rounds/cost/time, and code hash. After every look, save all intervals, p-values, decisions, counts, cumulative cost, and diagnostics, including unfavorable and inconclusive results. Do not replace the original three-repeat files or reuse them as the first three fresh rounds.

Implementation: `src/sequential_inference.py`. Tests: `python -m unittest discover -s tests -p test_sequential_inference.py -v`. Tests check reference binomial values, ties, order-statistic ranks, exact enumeration of all 4,096 IID sign paths across repeated looks, expected betting wealth, exact anytime coverage on enumerated Bernoulli paths, scaling/boundaries, multiplicity, and symmetric stopping. They validate the implementation, not the independence of a hosted service.
