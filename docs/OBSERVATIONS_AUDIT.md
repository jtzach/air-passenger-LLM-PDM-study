# Audit of observations from the initial MiD benchmark

This is a **post hoc descriptive audit** of the completed MiD experiment, prepared for the extended paper. It does not report a new experiment. It records useful examples, including failures of the best overall model, without treating the examples as prespecified tests.

The machine-readable companion is [`results/diagnostics_initial.json`](../results/diagnostics_initial.json). It retains exact values, source hashes, all 552 primary cohort-mode predictions, 96 feature-mode diagnostics, 24 mode-level diagnostics, and 24 household-car contrasts. Tables below round percentages and percentage-point gaps to two decimals.

Reproduce the calculations from the repository root with `python src/audit_initial_results.py`. The script reads the archived experiment and writes only the diagnostic JSON; it does not call an API or alter source records.

## What is being compared

- **Unit:** a MiD 2023 journey with at least one overnight stay that included an aircraft. These are journey records, not unique air passengers.
- **Outcome:** whether a car, local public transport, or long-distance rail was also reported anywhere on that journey. The three outcomes can co-occur.
- **Groups:** 23 overlapping groups, each defined by one attribute. They do not describe joint synthetic individuals.
- **Prediction:** the mean of three saved model probabilities. The survey conditional rates were withheld from the prompts; the anchored condition supplied only the three overall rates.
- **Signed error:** predicted percentage minus observed weighted percentage. Positive values indicate overprediction.
- **Weighting:** within each feature and mode, weight cohort errors by the published rounded weighted cohort base; average equally across the four features when reporting a mode-level result. Average equally across modes for the overall result. Never add group counts across different features.
- **Uncertainty:** the published aggregate tables cannot support respondent-level confidence intervals here. Three-run variation is model-output variation, not survey sampling uncertainty.

The raw-response check reconstructed all **552 primary mean predictions** from their three archived responses with maximum absolute difference **0**. Recalculating the eight overall model/condition MAEs from the feature-mode diagnostics differed by at most **3.55 × 10⁻¹⁵ percentage points**. No original data, prompts, or results were changed.

## 1. Car availability is associated with different mode combinations

These are survey observations, independent of what the models predicted:

| Cars in the household | Unweighted journeys | Car also used | Local public transport also used | Long-distance rail also used |
|---|---:|---:|---:|---:|
| No car | 936 | 15.00% | 40.06% | 16.76% |
| 1 car | 3,788 | 36.41% | 23.41% | 11.76% |
| 2 cars | 3,689 | 46.23% | 13.89% | 10.97% |
| 3 cars | 783 | 50.29% | 9.70% | 12.17% |
| 4 or more cars | 279 | 58.43% | 9.33% | 12.98% |

- From no car to four or more cars, reported car use rises **43.44 pp** and local public transport falls **30.73 pp**.
- The long-distance-rail difference is much smaller: **−3.78 pp**. Its observed rate is not monotonically decreasing across all five car categories.
- A defensible version of “car owners used trains” is: **journeys made by people in car-owning households still included long-distance rail in about 11–13% of records, depending on the car category.** Household car availability does not establish that the individual owned or drove a car.
- These tables cannot establish that the train was used to reach an airport, that the respondent chose rail instead of a household car, or why the modes were combined.

## 2. Matching one contrast does not mean matching all three outcomes

For GPT-4.1 with the overall-rate hint:

| Mode | Observed no-car → 4+ car rate | Predicted no-car → 4+ car rate | Observed contrast | Predicted contrast |
|---|---:|---:|---:|---:|
| Car | 15.00% → 58.43% | 16.33% → 59.67% | +43.44 pp | +43.33 pp |
| Local public transport | 40.06% → 9.33% | 35.00% → 15.00% | −30.73 pp | −20.00 pp |
| Long-distance rail | 16.76% → 12.98% | 19.00% → 7.67% | −3.78 pp | −11.33 pp |

- The car-use contrast is reproduced closely: contrast error **−0.10 pp**.
- The local-public-transport decline is too small by **10.73 pp**.
- The long-distance-rail decline is too large by **7.56 pp**.
- Without the hint, GPT-4.1 predicts a **68.00 pp** car-use contrast, **24.56 pp** larger than observed.
- Qwen with the hint happens to predict the same three extreme-category contrasts as anchored GPT-4.1, but its overall MAE is much worse (**6.80 vs 2.93 pp**). A single accurate contrast does not establish accurate levels or accurate predictions elsewhere.

## 3. One model reverses the local-public-transport contrast

- **Gemma 3 4B without the hint:** predicts local public transport at **30.00%** for the no-car group and **40.00%** for the 4+ car group. Its predicted contrast is **+10.00 pp**, opposite to the observed **−30.73 pp**.
- **Gemma 3 4B with the hint:** predicts **16.00% → 27.67%**, still the opposite direction (**+11.67 pp**).
- The anchored model underpredicts the no-car group's local-public-transport rate by **24.06 pp** and overpredicts the 4+ car group's rate by **18.34 pp**.
- This is an observable prediction error. It does not establish an internal model belief, a psychological mechanism, or a reason for passenger behaviour.

## 4. All four anchored models miss one high rail-use group

In **urban regions, small-town and village areas**, observed long-distance-rail co-use is **23.25%** among **419 unweighted journeys**. The rounded weighted base is retained in the JSON.

| Model | No-hint rail prediction | With-hint rail prediction | With-hint signed error |
|---|---:|---:|---:|
| Gemma 3 4B | 10.00% | 13.00% | −10.25 pp |
| GPT-4.1 mini | 23.33% | 10.00% | −13.25 pp |
| Qwen3 235B A22B | 20.00% | 8.00% | −15.25 pp |
| GPT-4.1 | 16.00% | 8.33% | −14.92 pp |

- The hint improves aggregate MAE for every complete model, but this particular rail group becomes less accurate for three of the four models.
- The observed rail rate in this group is higher than the **10.70%** observed for metropolitan residents. Anchored GPT-4.1 predicts **8.33%** and **15.33%**, respectively, reversing that comparison.
- This is GPT-4.1's largest absolute error among the 69 anchored cohort-mode cells. Its regional rail weighted MAE is nevertheless **3.26 pp**, illustrating how an average can conceal a substantial group-specific miss.
- Do not generalise this one group to all small towns, all rural areas, or all airport-access trips. “Urban-region small-town and village area” is a specific RegioStaR category; it is not the rural-region category.

## 5. Overall-rate hints correct large level errors, with uneven residual bias

Below, each mode's MAE uses the same within-feature weighting and equal-feature average as the primary analysis. Signed biases use the same weights. All quantities are percentage points.

| Model / condition | Car MAE | Local PT MAE | Rail MAE | Car bias | Local PT bias | Rail bias |
|---|---:|---:|---:|---:|---:|---:|
| Gemma 3 4B / no hint | 17.79 | 6.85 | 3.67 | −17.34 | +4.39 | −3.21 |
| Gemma 3 4B / hint | 7.70 | 6.00 | 3.19 | −4.69 | −0.97 | −0.96 |
| GPT-4.1 mini / no hint | 25.02 | 40.39 | 9.85 | +25.02 | +40.39 | +9.85 |
| GPT-4.1 mini / hint | 7.57 | 5.67 | 2.85 | +7.03 | +4.10 | −2.46 |
| Qwen3 235B A22B / no hint | 38.24 | 15.14 | 9.36 | +38.24 | +15.14 | +9.28 |
| Qwen3 235B A22B / hint | 12.79 | 4.66 | 2.94 | +12.71 | −3.88 | −1.94 |
| GPT-4.1 / no hint | 13.56 | 19.56 | 8.60 | +13.47 | +19.56 | +8.28 |
| GPT-4.1 / hint | 3.44 | 2.97 | 2.37 | +1.30 | +1.18 | +0.35 |

- GPT-4.1 mini without the hint overpredicts **all 69 cells**, including all 23 local-public-transport rates. Its local-public-transport bias is **+40.39 pp**.
- Qwen without the hint overpredicts every car and local-public-transport cell. Even after anchoring, its car bias remains **+12.71 pp**, with overprediction in **22 of 23** car cells.
- These counts concern overlapping group-mode cells, not independent people. They are descriptive summaries, not significance tests.

## 6. The overall winner does not win on every feature

| Feature | GPT-4.1 with hint: weighted MAE | Overall-rate baseline: weighted MAE |
|---|---:|---:|
| Household cars | 3.16 pp | 5.99 pp |
| Residential spatial type | 4.28 pp | 5.47 pp |
| Household companions | 1.31 pp | 2.72 pp |
| Nights away | 2.95 pp | 2.48 pp |

- GPT-4.1 with the hint improves on the baseline for three of four features.
- For nights away, simply using the overall survey rates performs better.
- Its overall **2.93 pp** MAE is lower than the **4.16 pp** survey-rate baseline and the **4.10 pp** GPT-4.1 no-group-clue control. This supports a bounded claim about these aggregate targets and prompts; it does not establish realistic simulated people or reliable individual choices.

## Proposed extended-paper layout: at most three figures and three tables in total

Count figures and tables across the main text **and any appended material**. Keep the existing technical figures in the repository as supporting assets, but do not insert them as additional numbered or unnumbered graphics in the new PDF.

### Figures

1. **What the model sees and what is checked.** One intuitive workflow with clearly separated MiD and FMG cases: actual source population and units → group/task description → prompt condition → three probabilities or the source-compatible FMG outcome → comparison with withheld group rates. Show what information each hint adds. Do not blend MiD whole-journey modes with Munich airport-access mode shares.
2. **MiD: better average scores can hide specific misses.** A three-panel figure: model MAE with/without the overall hint and baseline; observed versus GPT-4.1 anchored car-availability profiles for the three separate outcomes; the verified regional rail miss. Use consistent percent scales and direct labels. The car-availability panel should show all five categories to avoid an impression of a monotone rail relationship.
3. **FMG purpose/destination case, conditional on source comparability.** If matched published targets exist, compare forecasts with those targets and the declared baseline, marking each prompting step. If targets are unavailable or incompatible, show forecast changes as an explicitly unvalidated scenario exercise; do not label the figure as accuracy or include its values in an accuracy ranking. Use the source audit's actual periods, denominators, categories, and units.

### Tables

1. **Data and task definitions.** MiD and FMG source, period, population, observation unit, available group attributes, target categories, denominator, nonexclusive/exclusive status, and comparability limits. Make airport-access distinctions explicit.
2. **Experiment and performance summary.** Models, completed/planned calls, prompting conditions, and primary scores with units. Include the simple baseline and no-group-clue control; show unavailable FMG scores as “not comparable/not evaluated”, not as zero. Exact settings can be explained in prose to keep the table readable.
3. **Audited examples and practical interpretation.** A small set of observed and predicted values: household-car contrasts, regional rail miss, and a valid FMG example if available. State what each comparison does and does not show. Link the full diagnostic JSON instead of adding more appendix tables.

### Prompt appendix

- Reproduce the actual saved prompts in grey, breakable text boxes, outside `figure` or `table` floats.
- Identify model/task/condition and distinguish fixed instruction text from substituted group data.
- Show the actual requested response schema and the added information at each sequential prompting step.
- Do not replace an actual prompt with the easier “out of 100” explanation. Where the API asked for 0–1 probabilities, keep that exact wording and explain the percentage conversion separately.

## FMG boundary for the next stage

No FMG observation or accuracy result is asserted in this audit. The FMG source audit must establish category definitions, time period, denominator, population, and whether purpose/destination are available jointly or only as separate marginals before forecasts can be scored. Separate marginals must not be converted into invented joint passenger personas. A forecast that cannot be matched to a published target remains an exploratory output.
