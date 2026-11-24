# Air-passenger LLM-PDM study

An aggregate adaptation of LLM-PDM using public **Mobilität in Deutschland 2023** data. The study tests whether five language models reproduce reported car, local public transport and long-distance rail co-use on overnight journeys whose recorded main mode is aircraft.

**Read the paper first:** [journal manuscript](manuscript/main.pdf), then [technical supplement](manuscript/supplement.pdf). The manuscript uses the official Findings template and is designed for a 10–15 minute review.

## What the evidence represents

- **9,475 reported aircraft-main-mode overnight journeys**, not unique passengers.
- **14 candidate attributes**, screened with a fixed descriptive information-gain rule.
- **23 single-attribute profiles** from household car count, residential area type, household companions and nights away.
- **Five attempted models**, two prompt conditions, three repetitions, plus no-persona controls. Four models completed every call; Gemma 3 12B was operationally incomplete.
- **720 terminal records**: 587 valid responses, 35 invalid outputs and 98 rate-limited failures. Study cost was US$0.2728, plus US$0.0016 for five smoke checks.

**Main result:** overall-rate guidance improved all four complete models. Only anchored GPT-4.1 personas beat the observed population-rate baseline: **2.93 versus 4.16 percentage points MAE**. Its anchored no-persona control scored 4.10. The other three models' anchored personas performed worse than their no-persona controls. See [paper numbers](results/processed/paper_numbers.json) and the transparent [availability decision](docs/PROTOCOL_DEVIATIONS.md).

These are public group-level margins. No B1 microdata, joint synthetic passengers, new human responses or Munich Airport passenger records are used. The outcomes combine outward and return travel and do not isolate airport access. Selection and scoring use the same survey aggregates; the study is a descriptive aggregate benchmark, not individual or out-of-sample validation.

## Review route

1. Read [the paper](manuscript/main.pdf) for the question, design and main results.
2. Inspect the [framework](figures/01_framework.png), [persona selection](figures/02_persona_selection.png) and [model results](figures/03_model_results.png).
3. Open [the updated English workbook](data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx) for the original data archive and new, separately labelled experiment tables.
4. Read [how the Excel was made](docs/EXCEL_PROVENANCE.md) and [the study data dictionary](docs/data_dictionary.md).
5. Use [the supplement](manuscript/supplement.pdf) for formulas, prompts, limits and reproducibility details.

## Repository map

| Directory | Contents |
|---|---|
| `manuscript/` | Findings LaTeX source, bibliography, compiled paper, supplement and archived official template |
| `figures/` | Publication figures in vector PDF/SVG and 300-dpi PNG |
| `data/raw/mit/` | Original public API responses, exact requests and provenance |
| `data/processed/` | Cohort rates, eligibility, feature screening, frozen personas and validation |
| `data/workbooks/` | Updated and original workbooks, hashes and compact historical production archive |
| `config/` | Model selection, run settings and dated public OpenRouter model catalogue |
| `results/raw/` | Paid-run requests and terminal responses; authentication omitted and private account identifiers redacted |
| `results/processed/` | Predictions, error metrics, failure log and machine-readable paper numbers |
| `src/` | Preparation, selection, API runner, evaluation, figures and workbook production |
| `docs/` | Provenance, dictionary, literature, review notes and continuation instructions |

## Reproduce without new API charges

Use Python 3.11 or newer. The data preparation and metric scripts use the Python standard library. Figures require the versions in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python src/prepare_data.py --offline
python src/select_personas.py
python src/analyse_results.py
python src/make_figures.py
```

The frozen selection and run plans are part of the record. Do not alter them while reusing cached predictions. Rebuilding the presentation workbook uses `@oai/artifact-tool`; see the workbook builder and the historical archive instructions. Excel is an inspection format; JSON/CSV and source responses are the computational record.

The updated workbook preserves **all 27 original sheets** and adds four experiment sheets, for **31 sheets** in total. Original values, formulas, tables and formatting were checked for preservation; experiment predictions are separately labelled from observed MiD rates. The comprehensive workbook's Munich/ADV context is separate and was not used to fit or score the experiment.

Compile the journal files with a LaTeX installation containing the official template packages, or Tectonic:

```sh
cd manuscript
tectonic main.tex
tectonic supplement.tex
```

## Rerun the language models

Set `OPENROUTER_API_KEY` **in your process environment**. Do not put it in any file tracked by Git. Then run:

```sh
python src/run_experiment.py --prepare-only
python src/run_experiment.py
python src/analyse_results.py
```

The runner resumes existing matching requests and enforces a conservative US$10 run cap. A clean rerun needs a separately archived results directory and a versioned plan. Merely rerunning the command with the existing responses does not purchase new calls. Hosted models and providers may change; recorded requests, returned model/provider metadata, seeds and timestamps document the actual execution rather than guarantee bitwise repeatability.

## Sources and reuse

- MiD/MiT data: infas, DLR, IVT and infas 360 for the German Federal Ministry of Transport; public tabulation service supplied by BASt. Original source terms continue to apply.
- LLM-PDM: Tzachristas, Narayanan and Antoniou (2026), [DOI 10.26599/COMMTR.2026.9640004](https://doi.org/10.26599/COMMTR.2026.9640004).
- Findings template: David Levinson, CC BY 4.0; unmodified template and provenance are in `manuscript/template_original/`.
- The comprehensive workbook also contains clearly separated public Munich/ADV and geographical context, plus an airport data-availability catalogue. These contextual sheets are not inputs to the paper's experiment.

This is a manuscript for author review, not a journal submission or an accepted publication. Author order, affiliations and final declarations remain author decisions. AI assistance in research code and drafting is disclosed in the manuscript.

The editable writing copy is in [Overleaf](https://www.overleaf.com/project/6af39782e40c0117353a9820). GitHub is the canonical replication record. Start a later working session with [CONTINUE_HERE.md](docs/CONTINUE_HERE.md); use [the review checklist](docs/REVIEW_CHECKLIST.md) for author review.
