# Can AI predict how groups of air passengers travel on the ground?

An aggregate adaptation of **LLM-PDM** with two distinct tests: national ground-mode co-use on MiD 2023 air journeys, and reported access categories at Munich Airport. We ask whether a model can use a short group description to improve on simply repeating the overall observed rates. No new human survey or reconstructed individual passengers are used.

<!-- SEQUENTIAL_RELEASE_STATUS_START -->
**Completed experiment, 25 November 2026.** Final analysis, independent arithmetic checks, offline replay and workbook preservation validation have passed. Read the [current paper](manuscript/main.pdf) and [technical supplement](manuscript/supplement.pdf) for author review.
<!-- SEQUENTIAL_RELEASE_STATUS_END -->

## What is being compared?

| | MiD 2023 | Munich Airport 2025 |
|---|---|---|
| Observed unit | 9,475 reported overnight journeys with aircraft as the main mode; not unique passengers | Six authorized purpose-by-departing-flight-region aggregates from a co-author's FMG summary |
| Group cards | 23 overlapping groups, each defined by **one** attribute | Business/private × domestic/continental/intercontinental; other attributes unspecified |
| Prediction | Three probabilities: car, local public transport, long-distance rail anywhere on the journey | A distribution over ten reported airport-access categories |
| Outcome scope | Modes may overlap and the three targets do not exhaust all modes | Categories form a composition; parking may include an onward shuttle |
| Numerical hint | Both without and with overall MiD rates | No airport rates supplied to the model |

Four services produce **12 model–task–condition endpoints**. All endpoints remain in the results, including failures. The paper distinguishes:

- **Group/no hint:** the model receives the group description without observed rates.
- **Group/with hint:** MiD additionally supplies overall rates; the specific group's answers remain hidden.
- **No-group model control:** the same task without the group description; any MiD hint is retained.
- **Constant statistical baseline:** overall source rates applied to every group; no model call.

“Out of 100 similar journeys” means probabilities multiplied by 100, not 100 simulated people. Model rationales are possible explanations, not measured human motives. These are aggregate benchmarks, not individual, causal, or independent out-of-sample validation.

## Audited findings

- Six of the 12 conditions reached 16 complete rounds: **one improved on its constant baseline and five performed worse** under the primary rule. Six had no valid inferential checkpoint; their failures or short prefixes remain visible.
- **GPT-4.1 with the MiD hint** had a median round-level gain of **0.93 percentage points**, adjusted interval **[0.79, 1.19]**. Its averaged probabilities scored **2.95 pp MAE**, versus **4.16** for the baseline. These are different estimands, not interchangeable numbers.
- In Munich, GPT-4.1 and GPT-4.1 mini averaged **3.77** and **5.48 pp MAE**, versus the informed baseline's **2.67**. Their no-group controls scored **3.74** and **5.44**; these small control differences are descriptive. Airport prompts received no numerical hint, while the baseline knew the observed overall rates.

These claims concern repeated outputs under the stated model-service assumptions, not survey-population uncertainty. All figures and tables derive from [the new study's numerical record](results/sequential_20261125/table_numbers.json), not the pilot.

## Start here

- **Paper and exact prompts:** [paper](manuscript/main.pdf) and [technical supplement](manuscript/supplement.pdf). The main paper contains three figures, three tables, the exact overall-rate hint in a grey box, and a grey-box appendix of actual prompt text and all group descriptions.
- **Excel:** [revised inspection workbook](data/workbooks/MiD2023_MUC_LLM_Comprehensive_EN_20261125.xlsx): 31 preserved earlier sheets plus four new sequential-study sheets, **35 in total**. [Excel provenance](docs/EXCEL_PROVENANCE.md) explains the source files and preservation checks. JSON/CSV remain the computational record.
- **Continue the work:** [CONTINUE_HERE](docs/CONTINUE_HERE.md) records the boundaries, file map, and reproduction steps. [Author checklist](docs/REVIEW_CHECKLIST.md) lists scientific and publication decisions.
- **Earlier pilot:** [archived paper](manuscript/archive/20261124/main.pdf), [archived supplement](manuscript/archive/20261124/supplement.pdf), `results/processed/`, and the original figure names belong to the separate November 24 three-repeat MiD pilot. Its results must not be substituted for the new experiment. The [plain-language walkthrough](docs/PLAIN_LANGUAGE_WALKTHROUGH.md) also describes that pilot and its worked example.

## Reproduce the new study without API charges

Use Python 3.11+ and the pinned dependencies. These commands analyze archived outputs; they make no model calls and require no confidential source workbook.

```sh
python -m pip install -r requirements.txt
python -m zipfile -e results/sequential_20261125/request_archive.zip outputs/sequential_replay
python src/analyse_sequential_results.py --config results/sequential_20261125/evaluation_config.json --run-dir outputs/sequential_replay --output outputs/sequential_replay_analysis
python src/write_revised_results.py --source outputs/sequential_replay_analysis --output manuscript/generated
python src/make_revised_figures.py --data outputs/sequential_replay_analysis/figure_data.json
python -m unittest discover -s tests
```

Keep `evaluation_config.json` unchanged: its hash identifies the frozen settings. Its historical local catalogue path is unused by the offline analyzer. `request_archive.zip` retains the run and administrative-resumption evidence. A paused incomplete round was replaced as a whole under a documented amendment; original records remain in the audit and cost accounting.

The primary inference concerns **median round-level improvement** at registered looks of 16, 32, and 64 complete rounds. Errors of probabilities averaged across rounds are separate descriptive scores. A secondary mean confidence sequence has its own error allowance. No-group and hint contrasts are descriptive. None of these intervals measures survey-population uncertainty.

Compile the final canonical paper from `manuscript/` with `tectonic main.tex` and `tectonic supplement.tex`. Generating a workbook additionally requires `@oai/artifact-tool`; see the workbook provenance and builder scripts. New paid model experiments require a new versioned protocol and output directory, not the offline commands above. Credentials belong only in the process environment.

## Files and permissions

| Path | Role |
|---|---|
| `data/raw/mit/`, `data/processed/` | Public MiD requests, responses, normalization, group screening and frozen cards |
| `results/sequential_20261125/` | New 12-endpoint metrics, complete-prefix predictions, approved derived airport targets, exact-hash evaluation config and request archive |
| `manuscript/generated/` | Reproducible results tables/text and exact prompt appendix |
| `figures/revised_*` | The new paper's three figures, vector formats and numerical manifests |
| `results/processed/`, `results/raw/` | Preserved earlier pilot, not the new inferential sample |
| `data/workbooks/`, `docs/` | Inspection workbooks, provenance, protocols and continuation notes |

Confidential FMG originals, underlying source rows and interview counts are not released or sent to model services. Publication permission covers the six derived group aggregates and derived study results. The exact approved rates and weights permit offline score reproduction; they do not expose individual passenger records. MiD and airport targets have different populations and mode definitions, so their MAEs are not a common scale of task difficulty.

MiD is credited to infas, DLR, IVT and infas 360 for the German Federal Ministry of Transport; the public tabulation service is supplied by BASt. Original data terms still apply. The method builds on Tzachristas, Narayanan and Antoniou's [LLM-PDM](https://doi.org/10.26599/COMMTR.2026.9640004). The Findings layout is adapted from David Levinson's CC BY 4.0 template, retained with attribution in `manuscript/template_original/`.

This is an author-review project, not a journal submission or accepted article. [GitHub](https://github.com/jtzach/air-passenger-LLM-PDM-study) is the replication record; [Overleaf](https://www.overleaf.com/project/6af39782e40c0117353a9820) is the editable writing copy. Authorship, affiliations and final declarations remain author decisions.

Verification records: [analysis](results/sequential_20261125/analysis_qa.json), [independent arithmetic](results/sequential_20261125/independent_publication_audit.json), [offline replay](results/sequential_20261125/offline_replay_qa.json), [figures](results/sequential_figures_qa.json), and [35-sheet workbook preservation](results/sequential_workbook_validation.json).
