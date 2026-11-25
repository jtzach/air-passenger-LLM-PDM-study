# Continue this project

## Release state and entry points

<!-- SEQUENTIAL_RELEASE_STATUS_START -->
**25 November 2026: completed experiment for author review.** The 12-endpoint experiment, independent arithmetic audit, offline replay and 35-sheet workbook preservation checks have passed. Canonical `manuscript/main.tex` and `supplement.tex`, with their PDFs, describe the two-task study. No journal submission has been made.
<!-- SEQUENTIAL_RELEASE_STATUS_END -->

- Replication record: <https://github.com/jtzach/air-passenger-LLM-PDM-study>.
- Editable writing project: <https://www.overleaf.com/project/6af39782e40c0117353a9820>.
- Paper entry points: [main paper](../manuscript/main.pdf) and [technical supplement](../manuscript/supplement.pdf).
- Revised workbook: `data/workbooks/MiD2023_MUC_LLM_Comprehensive_EN_20261125.xlsx`, 35 sheets: all 31 earlier sheets plus four new-study sheets. Consult [EXCEL_PROVENANCE](EXCEL_PROVENANCE.md) and the preservation report before claiming validation.
- [README](../README.md) explains the two tasks. The [plain-language walkthrough](PLAIN_LANGUAGE_WALKTHROUGH.md) remains an explanation of the **earlier pilot**; its example is not a new sequential result.
- New-study checks: `results/sequential_20261125/analysis_qa.json`, `independent_publication_audit.json`, `publication_writer_qa.json` and `offline_replay_qa.json`; figure validation is `results/sequential_figures_qa.json`, and workbook validation is `results/sequential_workbook_validation.json`.

## Two tasks, not interchangeable outcomes

**National MiD task.** The public journey module contains 9,475 reported overnight journeys whose recorded main mode is aircraft, made by residents covered by MiD. These are journeys, not unique air passengers. Mode reports cover outward and return travel together. Car, local public transport and long-distance rail are nonexclusive co-use targets, not identified airport-access legs. The three rates neither exhaust all recorded modes nor sum as mutually exclusive shares. A displayed total of 71.9% therefore does not identify an “other” category of 28.1%. Walking and taxi are not separate rows of this particular public mode table.

The 23 group cards come from household car count, residential spatial type, accompanying household members and nights away. Each card contains **one** attribute. The fixed screen considered 14 attributes and selected two traveller and two journey dimensions; age ranked third among traveller dimensions and was outside that quota. Groups overlap. No joint age/income/car/region people were reconstructed. Household companions are not the complete travel party. Screening and scoring use the same aggregates, so this is not independent out-of-sample validation.

**Munich Airport task.** The co-author's FMG 2025 summary is reduced locally to six purpose-by-departing-flight-region groups: business/private × domestic/continental/intercontinental. Direction and journey duration are pooled. The model receives only those generic descriptors and no airport-rate hint. It predicts ten reported airport-access categories. This is not necessarily the literal final vehicle: off-airport parking may include a shuttle classified as parking. Expanded passenger counts are not interview sample sizes; original upstream workbooks and interview Ns have not been independently verified.

Permission covers the six **derived** target groups, their weights/baseline and derived study outputs. Confidential originals, underlying source rows/counts, and private identifiers remain outside the public repository and model requests. Do not expand this permission to new private data or arbitrary source excerpts.

## Four comparisons to keep distinct

1. **Group/no hint:** each card still identifies its group; the model receives no observed rates.
2. **Group/with hint:** MiD adds the exact overall-rate paragraph, not the conditional group answers.
3. **No-group model control:** an actual model response to the same task after replacing the card; a MiD hint remains if that condition uses it.
4. **Constant baseline:** overall source rates applied to every group without calling a model.

The no-household-car card's actual car-use rate is about 15%; that target is withheld. The hinted model receives the overall car rate of about 37.68% and must adjust it using the card. Comparing against the constant baseline asks whether that adjustment helps. Comparing the two group arms asks whether the overall hint helps; comparing with the no-group response asks whether the card helps. These are different comparisons.

The exact hint appears in a grey box in the main Methods section. `manuscript/generated/exact_prompts_appendix.tex` records the full prompt templates, exact insertion/control text, 23 MiD descriptions and six airport descriptions. Actual request payloads are archived. “Out of 100” is a percentage display, not 100 simulated respondents. LLM explanations are hypotheses, not validated human motives.

## New experiment and preserved pilot

The new study has four services and 12 registered endpoints: two MiD arms and one airport arm per service. All blocks are reported, even when no complete round exists. Primary inference is the median of **round-level baseline gains**, using fixed looks at 16, 32 and 64 rounds, a 0.5-pp practical margin, and a family allowance of 0.04 divided across all endpoints and looks. Separate mean confidence sequences use 0.01/12 per endpoint. No-group and hint contrasts are descriptive, not extra confirmatory tests. Independent seeds and provider pins do not prove IID; model-output intervals are not survey uncertainty.

An invalid or unresolved service response halts its block. The user-requested administrative pause interrupted round 7. A documented amendment replaces that entire partial round with new seeds and retains all original attempts in the archive/accounting; it does not rescue previously failed blocks or selectively keep favorable responses. See `docs/SEQUENTIAL_PROTOCOL_20261125.md`, the supplement, and the archive's amendment record.

The November 24 pilot remains separate in `results/raw/`, `results/processed/`, `config/experiment.json` and the original figure names. It used five attempted models and three repetitions, not the new sequential protocol. Its anchored GPT-4.1 MAE of 2.9283 pp versus a 4.1620-pp baseline is **historical exploratory evidence**. Never copy it into the new results, combine its calls with fresh rounds, or claim that its selected-model availability decision was the new protocol. Earlier manuscript PDFs are preserved in `manuscript/archive/20261124/`.

## Offline reproduction

Authoritative new numbers are in `results/sequential_20261125/table_numbers.json`, with `block_details.json`, `findings.json`, `averaged_predictions.csv` and `analysis_qa.json`. The exact-hash `evaluation_config.json` includes only public MiD and approved derived FMG values, generic prompts, weights and settings. Its historical local catalogue path is unused by the analyzer. Do not edit it: that breaks freeze validation.

From the repository root, after installing `requirements.txt`:

```sh
python -m zipfile -e results/sequential_20261125/request_archive.zip outputs/sequential_replay
python src/analyse_sequential_results.py --config results/sequential_20261125/evaluation_config.json --run-dir outputs/sequential_replay --output outputs/sequential_replay_analysis
python src/write_revised_results.py --source outputs/sequential_replay_analysis --output manuscript/generated
python src/make_revised_figures.py --data outputs/sequential_replay_analysis/figure_data.json
python -m unittest discover -s tests
```

These steps incur no API charges and need no confidential workbook. The writer fails if final inputs are absent, reports all 12 blocks, and archives fixed Table 3 calculations in `publication_observations.json`. Table 2 separates averaged-prediction MAE from the primary median gain/interval; differing prefix/checkpoint lengths are explicit. Table 3 uses fixed GPT-4.1 illustrations, with unavailable predictions left unavailable rather than replaced by another model.

New figures use `figures/revised_01_dual_framework.*`, `revised_02_mid_contrasts.*` and `revised_03_fmg_results.*`. Figure 3 visually combines some airport categories, but scoring retains all ten. Compile final `main.tex` and `supplement.tex` from `manuscript/`. The main plus supplement must stay within **three figures and three tables in total**; grey prompt boxes are ordinary text, not floats. The previous under-1,000-word preference was superseded by a request for a longer, clearer paper.

The Excel build uses `src/prepare_sequential_workbook.py`, `append_sequential_workbook.mjs` and `validate_sequential_workbook.py`; it additionally needs `@oai/artifact-tool`. The first 31 sheets preserve their original content/style. New sheets 32–35 cover endpoint results, fresh MiD predictions, fresh Munich predictions and the six approved airport targets. Excel is an inspection aid; source JSON/CSV are authoritative.

## Safe continuation

- Read current release status and QA files before claiming completion. A request archive alone does not prove a successful endpoint.
- Use cached outputs for review. New paid calls need a separately versioned protocol/freeze and output directory; never overwrite or silently extend this experiment.
- Keep credentials in the process environment. Do not publish private account IDs, original FMG files, or confidential source rows. Record any redaction while preserving scientific values.
- Edit canonical repository sources, then intentionally synchronize Overleaf. Preserve the pilot archive and do not treat old result prose as the current manuscript.
- If B1 microdata arrive, verify permissions, linkage, weights and mode definitions first. Individual/joint-persona validation is a new study, not a conclusion of these aggregate tests.
- Authors still decide names, affiliations, declarations and journal submission. The project is neither submitted nor accepted. No claim is made that related research does not exist.
