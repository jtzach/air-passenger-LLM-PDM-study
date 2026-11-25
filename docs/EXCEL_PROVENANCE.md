# How the Excel was made

The original research workbook was assembled on 18 November 2026. Public MiD cross-tabulations and the first LLM pilot were added on 24 November. The 25 November revision appends the repeated-run MiD experiment and a separate Munich Airport case. No individual B1 survey records have been received, created or inferred.

## Which workbook to use

- `data/workbooks/MiD2023_MUC_LLM_Comprehensive_EN_20261125.xlsx`: current 35-sheet English archive, including the new repeated-run experiment and separately labelled Munich derivatives.
- `MiD2023_Comprehensive_Data_and_LLM_EN.xlsx`: preserved 31-sheet archive with the original three-repeat pilot, not the fresh sequential results.
- `MiD2023_Comprehensive_Data_EN.xlsx`: unchanged 27-sheet English archive from 18 November.
- `MiD2023_Comprehensive_Data.xlsx`: unchanged source-language archive.
- `workbook_provenance_20261118.zip`: frozen rendering input, original production scripts, translation patches, archived public queries, source manifests and validation reports.

These workbooks are not person-level datasets. A row may be a published aggregate, a question, a code definition, an airport statistic or a model prediction. The row type and source must be respected.

## Original sources and their roles

| Source | What entered the workbook | Important boundary |
|---|---|---|
| Official [MiT 2023 public tabulator](https://mobilitaet-in-tabellen-2023.bast.de/) | 120 public queries, 136 returned matrices; 608 aircraft-conditioned aggregate cells; age-by-ground-mode table | Query cells are not respondents. Full matrix sheets intentionally include comparison populations. |
| [MiD supplementary study materials](https://www.mobilitaet-in-deutschland.de/publikationen2023.html) | 125 question blocks and 574 response, item or open-format entries from the published CATI/CAWI overview | The question overview is not the complete routing master. |
| [Released B1 v1.1 codebook](https://mobilithek.info/offers/897527161045086208) | 926 table-variable entries and 6,027 value-code entries | Documentation only; codes can differ from the questionnaire and earlier releases. |
| MiD small-area estimate workbooks | 1,593 municipality and 400 district modelled mobility records | These concern all residents, not aircraft users. No B1 municipality join is possible with the standard release. |
| Official RegioStaR reference | 10,978 municipality/municipality-free-area records, 117 definitions and geographical field descriptions | Boundary reference: 31 December 2023; a geographic reference is not evidence of airport use. |
| ADV 2023 airport statistics | 28 reporting airports plus a labelled total, passenger movements and operations | Traffic movements are not unique passengers. |
| Munich Airport 2025 report and public PIP source inventory | 29 selected published Munich quantities, plus a separate inventory of public PIP source descriptions | Different population and year from MiD; not used to fit or score this paper. |
| Airport-provided dataset availability catalogue | 14 descriptions of potentially available datasets | Metadata only. Underlying observations were not supplied. |

Full URLs, retrieval timestamps and SHA-256 hashes are retained in the workbook's Query catalogue and Sources sheets, and in the provenance ZIP. The official [MiD publication catalogue](https://www.mobilitaet-in-deutschland.de/publikationen2023.html) identifies the reports and documentation.

## Processing, step by step

1. Download and preserve official source files. Keep raw JSON responses separate from cleaned tables. Record the exact public POST request, source URL, UTC retrieval time, byte count and SHA-256 hash.
2. Query overnight journeys (`reise`), day journeys (`tage`), people (`p`) and diary trips (`w`) separately. Use the corresponding official weight variable. Do not combine recall periods or sampling units.
3. For aircraft profiles, select the column labelled `Flugzeug` in overnight/day main-mode tables. Check that reported aircraft use is 100% in that column and 0% elsewhere in the returned mode cross-tabulations. The source's main-mode hierarchy prioritises aircraft.
4. Preserve published category labels, blanks and missing categories. Extract each column's weighted and unweighted bases. Use the aircraft-column base rather than the all-mode table base. No imputation, synthetic records or fabricated confidence intervals were introduced.
5. Convert returned percentages from 0–100 to Excel numeric fractions from 0–1. Preserve underlying numeric precision; apply display formatting separately. Weighted cell counts and weighted bases returned by MiT are rounded. A rounded zero count can coexist with a positive percentage.
6. Construct the compact age-by-mode matrix by matching dataset, mode and age category. Mode mentions are nonexclusive and need not sum to 100%. Outward and return travel are combined; airport access direction and airport identity are unknown.
7. Retain all returned matrices in four complete-table sheets so the original comparison categories remain inspectable. Preserve exact queries and response hashes in Query catalogue.
8. Extract the full B1 v1.1 dictionary and the published questionnaire overview into separate sheets. Retain source sheet/row or PDF page references. Do not treat a dictionary entry as an observed value for a person.
9. Import geographical reference and small-area data with original identifiers and units. Keep their all-resident/modelled status explicit. No respondent-to-city or respondent-to-airport linkage was invented.
10. Keep Munich, ADV and airport catalogue material in separate named sheets. The one side-by-side MiD/Munich sheet labels both sources and comparability restrictions. None of these contextual quantities enter the LLM experiment.
11. Assemble a typed JSON rendering input (`comprehensive_data.json`) and use `@oai/artifact-tool` to build the workbook, its tables, frozen headers and number formats. That frozen JSON and the original builder are in the provenance ZIP.
12. Translate explanatory text, questions, answer labels and codebook descriptions into English. Preserve variable names, codes, proper names, URLs, units, numbers and formulas. Apply 35,574 explicit cell edits. Synchronise native Excel table-column metadata with translated header cells.

## Original validation

The final English readback checked 27 sheets and 23 Excel tables. It preserved 101,383 numeric cells and the existing formula, checked 35,574 translated cells and 323,914 unchanged cells, and reported zero issues. Sheet layouts were visually inspected. These checks concern the 18 November files; the updated workbook has its own additional validation.

The provenance ZIP includes the machine-readable validation report. `provenance_manifest.json` records the delivered original and English workbook hashes. Byte-for-byte XLSX regeneration can differ across rendering-engine versions even when content is identical; compare cell values, identifiers, formulas and structure as well as file hashes.

## New study tables

`src/prepare_data.py` retrieves 15 public overnight tables: one overall table and 14 candidate feature breakdowns. Each table crosses the multiple-response mode set with main mode, optionally broken down by one attribute. The new long table retains every returned cohort, eligibility flag and source reference. The main analysis uses only car, local public transport and long-distance train mentions in the aircraft-main-mode column.

`src/select_personas.py` screens attributes by descriptive normalised Bernoulli information gain, retaining substantive strata with at least 100 unweighted journeys and features covering at least 80% of the overall weighted aircraft base. The two highest-scoring traveller and two highest-scoring journey attributes are selected. This yields single-attribute group profiles, not joint people. The rule, source hashes and selected profile hashes were frozen before study LLM calls.

LLM predictions are stored separately from observed rates, with model, prompt arm, repetition, request/response provenance and validation status. They are model outputs, never new survey responses. `src/analyse_results.py` computes the paper's aggregate errors without treating overlapping cohorts as independent passengers.

## Updated workbook validation

The delivered [31-sheet English workbook](../data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx) retains all 27 original sheets and appends four study sheets: Persona feature screening, Aircraft cohort rates, LLM predictions and LLM model results. The results sheet also records call availability for all five attempted models, including the excluded incomplete Gemma 3 12B run.

The [machine-readable preservation report](../results/workbook_validation.json), completed on 24 November 2026, reports zero issues. It checked 359,488 original cells, including 101,383 numeric values, all 23 original native tables, the original formula and its cached result, formatting, column widths, row dimensions and frozen panes. It also checked 20,749 appended cells against the typed analysis input. The four new sheets and the model-availability table were visually inspected.

The final workbook SHA-256 is `58eff4edd14599abd439a8eb8bc241421275a20027b9542b3d222fb28be723af`. Its unchanged 27-sheet English input has SHA-256 `449253601da5793dba9384ecf739b15516d089783cb3b9b2e9f433a0513e2bd7`.

The appendix can be reproduced with `src/prepare_workbook_appendix.py`, `src/append_benchmark_workbook.mjs` and the read-only `src/validate_benchmark_workbook.py`. The Python preparation reads committed observations and analysis results; Artifact Tool imports the English original and appends the new sheets. Validation compares the exported file with the original workbook and the typed appendix input. Weighted coverage can marginally exceed 100% because independently rounded weighted subgroup bases are preserved.

## Repeated-run and Munich extension: 25 November 2026

The new file `MiD2023_MUC_LLM_Comprehensive_EN_20261125.xlsx` preserves the complete 31-sheet pilot workbook and appends four data sheets. Original data, geographical reference material, questionnaire entries and earlier predictions remain intact. The previous experiment is not overwritten or pooled with the new runs.

| New sheet | Records and units | Source |
|---|---|---|
| `32_Sequential_results` | All 12 planned model/task/condition comparisons, complete-round counts, errors in percentage points, adjusted median-gain intervals and stopping reasons | Audited `block_metrics.csv` and `table_numbers.json` |
| `33_MiD_new_predictions` | Each available model/condition/group/mode combination, observed and predicted shares, repeated-output spread, group weight and errors | `averaged_predictions.csv`, MiD rows only |
| `34_MUC_new_predictions` | The same prediction fields for six Munich purpose-by-flight-region groups and ten native access categories | `averaged_predictions.csv`, FMG rows only |
| `35_MUC_derived_targets` | Six approved derived Munich groups, their population weights and ten observed shares | Locally aggregated 2025 FMG summary, released as `derived_fmg_targets.json` |

The Munich sheets are **FMG-derived, not MiD data**. They contain neither individual records nor the airport workbook's original 10/30-row extracts or expanded annual passenger counts. The six groups pool direction and duration within business/private purpose crossed with domestic/continental/intercontinental departing flight. The original workbook remains restricted. Derivation is documented in `FMG_PROVENANCE.md`; original survey definitions and interview sample sizes still require source verification.

The extension follows this reproducible sequence:

1. Audit the completed frozen experiment with `src/analyse_sequential_results.py`. Reconstruct each complete logical round from its recorded responses; preserve failed and interrupted requests in availability and cost accounting. Exclude the original administratively interrupted partial round from scoring, as recorded in `ADMINISTRATIVE_RESUMPTION_20261125.md`.
2. Run `src/prepare_sequential_workbook.py`. It requires a passing analysis report, reads typed analysis outputs, separates MiD from FMG, assigns readable category labels and records the input workbook hash. It does not query an API or infer missing responses.
3. Run `src/append_sequential_workbook.mjs` using `@oai/artifact-tool`. Import the existing English workbook, append the four sheets, retain numeric probabilities on a 0–1 scale and display them as percentages. Errors use Excel formulas `100 × (prediction − observation)` and its absolute value. The Munich share-total column sums the ten observed categories.
4. Recalculate formulas, scan for Excel errors, inspect rendered sheet excerpts and export the new workbook. Statistical intervals remain audited Python outputs; model-run variation must not be read as survey-sampling uncertainty.
5. Run `src/validate_sequential_workbook.py` in read-only mode. It checks every original cell and formula cache, native tables, styles, dimensions, frozen panes, appended values and the independently recomputed formula results. Exact counts and file hashes are in `results/sequential_workbook_validation.json`.

For MiD, the three outcomes are overlapping mentions across whole outward/return journeys and need not sum to 100%. For FMG, the ten reported airport-access shares form one composition. Group weights in the MiD analysis include equal weighting across attributes; Munich weights describe the composition of the six target groups. Neither is an unweighted interview count. Missing inference for a failed block is left unavailable rather than encoded as zero. All complete-response prefixes, including short prefixes without a scheduled statistical check, remain explicitly labelled.

## Reproducing the files

The current study can be reproduced offline from committed raw tables with the preparation, selection and analysis scripts described in the repository README. API reruns require an OpenRouter key in an environment variable and incur a bounded cost. Paid-run requests and model outputs are archived without credentials. Account-related metadata was redacted from response records as documented in [the redaction report](../results/account_metadata_redaction.json); scientific prediction values were unchanged.

To inspect the original workbook production, extract `workbook_provenance_20261118.zip`. Its `REBUILD.txt` explains the archived builders. Rebuilding the English version requires the frozen original workbook, the explicit text patches and an `@oai/artifact-tool` installation. Large original PDFs and geographical workbooks are referenced by source URL/hash rather than unnecessarily duplicated in this repository.
