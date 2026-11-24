# Continue this project

## Current state (24 November 2026)

The journal manuscript, technical supplement, three publication figures, archived public data, complete model-run record and expanded English workbook are ready for author review. No journal submission has been made. No B1 individual records or new human responses have been obtained.

- Canonical replication repository: https://github.com/jtzach/air-passenger-LLM-PDM-study
- Editable writing project: https://www.overleaf.com/project/6af39782e40c0117353a9820
- Start with the [plain-language walkthrough and sketch](PLAIN_LANGUAGE_WALKTHROUGH.md), then `manuscript/main.pdf` and `manuscript/supplement.pdf`.
- Inspect `data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx`; its four appended sheets separate selection, observed rates, predictions and model results.
- Read `docs/EXCEL_PROVENANCE.md` for the original workbook, translations, source files, preservation checks and appended experiment tables.

## What can and cannot be claimed

The observed population is **9,475 reported overnight journeys with recorded main mode aircraft**, made by residents of Germany covered by the MiD journey module. These are journeys, not unique air passengers. Modes refer to outward and return travel together and can overlap. They are not isolated airport-access choices.

The 23 personas are **single-attribute cohort descriptions**, not joint synthetic individuals. Public marginal tables cannot establish the joint age/income/car/region distribution. Screening and evaluation use the same aggregates; no individual or independent out-of-sample validation is claimed. Household companions are not the complete travel party. No Munich-specific result follows from these national tables.

The method is an aggregate adaptation of LLM-PDM. It directly elicits three probabilities, without fine-tuning or iterative matching of cohort targets. Conditional observed rates are withheld from model prompts. The anchored arm receives only overall population rates. LLM explanations are hypotheses, not respondents' reported motives.

When explaining the study, use the walkthrough's one-clue group cards and its verified no-household-car GPT-4.1 example. “Out of 100 journeys” displays a probability multiplied by 100; it does not describe 100 sampled or simulated people. Keep the two-traveller-plus-two-journey selection rule explicit: age ranked third among traveller attributes and was not selected under that design. The example illustrates one card; the benchmark evaluates all 23 overlapping groups.

## Frozen experiment and results

- `data/processed/selection_protocol.json`, `selection_freeze.json` and `personas.json` record the selection rule and 23 profiles.
- Four chosen dimensions: household car count, residential spatial type, accompanying household members, nights away. Selection ranks normalized Bernoulli information gain, requires minimum base/coverage, and takes two traveller and two journey dimensions.
- `config/experiment.json` and `results/experiment_plan.json` specify five models, two arms, three repeats and no-persona controls: 720 planned terminal calls.
- Four models completed all 144 calls each. Gemma 3 12B returned 11 valid, 35 invalid and 98 failed responses. The primary complete-model comparison was defined before comparative MAEs were calculated; see `PROTOCOL_DEVIATIONS.md`.
- All four complete models improved with overall-rate guidance. Only anchored GPT-4.1 personas beat the observed-rate constant baseline (2.9283 vs 4.1620 percentage points MAE). Its no-persona control scored 4.1037. The other anchored persona models did worse than their no-persona controls.
- `results/processed/paper_numbers.json` is the numerical reporting source. Costs were approximately US$0.2744 including smoke checks.
- `results/account_metadata_redaction.json` documents redaction of private account IDs. No API authentication is archived. Scientific values were unchanged.

## Reproduction and editing

Run from the repository root, after installing `requirements.txt`:

```sh
python src/prepare_data.py --offline
python src/select_personas.py
python src/analyse_results.py
python src/make_figures.py
```

The first three scripts require only Python's standard library. Figure dependencies are listed in `requirements.txt`. The workbook uses `@oai/artifact-tool`; consult `src/prepare_workbook_appendix.py`, `src/append_benchmark_workbook.mjs`, `src/validate_benchmark_workbook.py` and `EXCEL_PROVENANCE.md`.

Compile `manuscript/main.tex` and `manuscript/supplement.tex` from the `manuscript` directory. The Overleaf root has adjusted relative paths; it retains the previous project document as `project_notes.tex`. Prefer editing canonical sources here and intentionally synchronizing the writing copy.

Do not purchase new model calls just to reproduce figures or tables: archived outputs are sufficient. A new model study requires a separately versioned protocol and output directory; do not overwrite this frozen experiment. Credentials belong only in the process environment, never in the repository or manuscript.

## Next scientific steps

1. Authors review scope, interpretation, authorship and disclosure before submission.
2. If B1 microdata arrive, first verify access rights, journey/person linkage, available weights and ground-mode definitions. Treat individual/joint-persona validation as a new study with a separate protocol.
3. For Munich airport-access claims, obtain identified access-leg outcomes and relevant airport covariates. Keep Munich sources separate from MiD evidence.
4. A new robustness study could test truly held-out outcomes, survey-wave transfer, additional independent endpoints or individual records; it must not retroactively be called preregistered.

The paper does not claim that no similar research exists. `docs/literature.md` records verified related work and the narrower contribution actually tested.
