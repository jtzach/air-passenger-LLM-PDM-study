# Public aggregate data and cohort selection

This study uses public MiD 2023 tables from [Mobilität in Tabellen](https://mobilitaet-in-tabellen-2023.bast.de/), retrieved on 24 November 2026. No B1 respondent microdata have been obtained. A row in the processed data is a published conditional percentage, not a person or a simulated individual.

## Population, observation and outcomes

The overnight-journey module describes the latest three journeys with an overnight stay during the preceding three months. The module was allocated to 25% of the survey sample and answered by online or telephone self-respondents aged at least 14; postal and proxy interviews did not answer it. MiD represents residents of Germany, and its fieldwork extends across 2023 and 2024. The 9,475 aircraft-containing journey records are not 9,475 unique people, a census of German airport passengers, or a Munich airport sample.

The query conditions on the public `hvm_r` column labelled `Flugzeug`. Aircraft has highest priority in the official main-mode hierarchy, so this identifies journeys that reported aircraft among their modes. The archived cross-tabs additionally show aircraft mention at 100% within this column. The public table endpoint does not expose a record-level `R_VM_I` filter.

The modes question asks about all modes used for the outward and return journey together. Each outcome below is a separate, overlapping indicator. Their percentages need not sum to 100%.

| Processed outcome | Exact source row | Corresponding questionnaire flag | Interpretation |
|---|---|---|---|
| `car` | Auto | `R_VM_A` | Car reported for the outward or return journey |
| `local_pt` | Bus oder Bahn im Nahverkehr | `R_VM_C` | Local bus or rail reported for the outward or return journey |
| `long_distance_rail` | Fernzug | `R_VM_F` | Long-distance rail reported for the outward or return journey |

These are co-use rates conditional on aircraft-containing overnight journeys. They do not locate a ground mode on a particular stage or identify airport access, airport identity, travel direction, car driver/passenger status, or causal mode-choice effects. Modes used only at the destination are a separate question and are not these outcomes.

## Requests and provenance

`src/prepare_data.py` archives the dataset catalogue, the overnight variable catalogue, an overall table, and one table for each of 14 candidate attributes. Only publicly listed aggregate queries are used. No credentials, private identifiers or restricted records are requested.

- Catalogue endpoints: `GET /api/datasets` and `POST /api/vars` with `{"id":"reise"}`.
- Table endpoint: `POST /api/table/json`.
- Table parameters: dataset `reise`, weight `R_GEW`, column percentages, row set `ms_verkehrsmittel-der-reise-mehrfachantworten-set_e054e270`, column `hvm_r`, and the candidate attribute as `breakdown_by`.
- Each raw table has its exact `.request.json`, unchanged JSON response and `.provenance.json` containing URL, UTC retrieval time, request and response SHA-256 hashes, response size and selected HTTP headers.
- `query_plan_reise.json` inventories all 15 table requests. `category_translations.json` archives the exact source-to-English label mapping used by the pipeline.
- Normalization verifies every response hash and selects the aircraft column by label. Source table positions are one-based; source column positions are zero-based.

The response's top-level `bases` describe all modes and are never used as aircraft denominators. The pipeline reads `Basis (ungewichtet)` and `Basis (gewichtet)` within the aircraft column. It preserves exact returned percentages divided by 100, rounded weighted counts, and rounded weighted bases separately. A rounded zero count can coexist with a positive percentage.

The portal omits the aircraft column for two returned categories (employment: no answer; distance: under 100 km). Those rows remain in the processed inventory with null denominators/rates and `aircraft_column_absent`. No denominator or rate is invented. Other attributes have variable-specific valid-data bases: keeping all returned categories does not recover every original missing record.

## Weights and denominators

`R_GEW` is the overnight-journey weight. Official documentation describes person-weight-based adjustment for the number of reported journeys, with weights normalized to the dataset case count. The overall weighted aircraft base of 9,069 is not a German population total or an independent sample size. Rounded weighted bases are used only to combine published subgroup rates for descriptive screening.

Independently rounded subgroup bases can sum slightly above the rounded overall base (for example 9,070 versus 9,069). The original values are preserved. Survey design variables, individual weights, repeat-person identifiers and cross-cell covariance are unavailable, so no design-based confidence intervals, effective sample sizes, individual regressions or significance tests are inferred from these aggregates.

## Candidate attributes

All 14 attributes and all returned strata remain in `cohort_mode_shares.csv`, including attributes not selected for the LLM experiment.

| Public attribute | Meaning | Screening family |
|---|---|---|
| `alter_gr4` | Age group | Traveller |
| `HP_SEX` | Gender category | Traveller |
| `bildung` | Educational attainment | Traveller |
| `erwerb` | Employment status | Traveller |
| `hheink_gr2` | Monthly net household income | Traveller |
| `anzauto_gr1` | Number of household cars | Traveller |
| `hhgr_gr` | Household size | Traveller |
| `RegioStaR7` | Residential spatial type | Traveller |
| `P_FS_PKW` | Car driving licence held | Traveller |
| `R_ZWECK` | Main journey purpose | Journey |
| `R_ZIEL` | Journey destination region | Journey |
| `entf_gr` | One-way distance from home to the destination | Journey |
| `anzueb_gr` | Number of nights away | Journey |
| `anzbegl_gr` | Number of accompanying household members | Journey |

`anzbegl_gr` does not count every travel companion. The official processing assigns zero to one-person households and marks a companion count greater than or equal to household size as implausible. Zero household companions does not establish that a person travelled alone. The returned aircraft companion table covers 8,897 journeys; its 4-or-more category has only 97 journeys and is excluded from the experimental profiles by the prespecified minimum.

Public category labels are preserved verbatim in German alongside reviewed English labels. The API does not return numerical category codes. Therefore `category_code` is null. `stratum_id` is a reproducible hash identifier for an archived category label, never a survey category code or respondent identifier.

## Frozen descriptive screening

`selection_protocol.json` fixes the rule before these fresh candidate queries and before the study LLM predictions. Earlier public age tables had already been examined. This is a documented analysis decision, not externally registered preregistration and not a protocol written before all exposure to MiD data.

1. Exclude response/design-missing categories, categories with fewer than 100 unweighted aircraft journeys, nonpositive/missing weighted bases, and incomplete three-outcome profiles. Keep substantive negatives such as no household car or not employed.
2. An attribute is eligible if at least two strata survive and their summed rounded weighted bases cover at least 80% of the overall aircraft weighted base.
3. For each outcome, compute the weighted average subgroup probability and its binary entropy. Subtract the weighted average subgroup entropies to obtain Bernoulli information gain, then divide by the pooled entropy. A zero pooled entropy receives a score of zero.
4. Average the three normalized information gains. Rank attributes by this score, breaking ties by ascending attribute identifier.
5. Select the top two eligible traveller attributes and top two eligible journey attributes. Keep every eligible substantive category of these four attributes.

Formally, for eligible strata s with rounded weighted base w_s and published rate p_sm, let a_s = w_s / sum(w_s), p_m = sum(a_s p_sm), and H(p) = -p log2(p) - (1-p) log2(1-p). The attribute score is the mean over the three modes of [H(p_m) - sum(a_s H(p_sm))] / H(p_m).

The result is 23 single-attribute cohort profiles: household cars (5), residential spatial type (7), household companions (4), and nights away (7). `selection_freeze.json` records the selected feature identifiers, input response hashes and the persona JSON fingerprint before LLM execution.

This score describes in-sample separation in the published marginal tables. It is sensitive to category definitions, numbers of categories and correlated attributes. It does not establish causal or independent feature importance. Profiles from different attributes overlap in their underlying journeys; they cannot be concatenated into a respondent sample or multiplied to create joint personas. LLM performance on these selected published cohorts is an aggregate benchmark, not validation on unseen individuals or airports. The public tables may also have been available during model training.

## Processed files and fields

| File | Contents |
|---|---|
| `cohort_mode_shares_raw.json` / `.csv` | 258 mode rows: overall baseline plus 85 returned attribute strata, three outcomes each |
| `cohort_mode_shares.json` / `.csv` | Same rows with eligibility, selection and persona identifiers |
| `feature_selection.csv` | Ranking, coverage, retained sample counts and selected flag for all 14 attributes |
| `feature_selection_details.json` | Outcome-specific information gains and explicit exclusion reasons for each attribute |
| `personas.json` | The 23 frozen single-attribute profiles and observed validation targets |
| `overall_baseline.json` | Overall observed rates, N=9,475, rounded weighted base=9,069 and provenance |
| `selection_summary.json` | Selected features, profile counts and interpretation limits |
| `selection_protocol.json` / `selection_freeze.json` | Dated rule and immutable input/profile fingerprints |
| `data_validation.json` | Hash, scale, category-denominator and returned-base checks |

Key long-table fields:

- `dataset`: `reise` for the primary overnight data.
- `feature_id`, `feature_label_en`, `feature_family`: public attribute identifier, English meaning and traveller/journey family. `__all__` is the baseline.
- `stratum_id`, `category_code`, `stratum_label_de`, `stratum_label_en`: archive identifier, unavailable numerical code, original label and translation.
- `mode_id`, `observed_share`: outcome identifier and weighted proportion in [0,1], or null when unavailable.
- `unweighted_base`: published unweighted number of aircraft-containing journey records in this stratum; repeated across its three outcomes.
- `weighted_base`, `weighted_count`: rounded weighted denominator and numerator. These are not population counts.
- `outcome_status`: observed or explicit unavailable status. Missing values are distinct from zero.
- `source_file`, `source_sha256`, `source_table`, `source_column`, `retrieved_utc`, `weight_variable`: cell-level provenance.
- `eligible`: stratum passes the frozen substantive/N/outcome criteria; `selected`: it also belongs to a selected feature; `persona_id`: assigned only to selected profiles.

Observed targets in `personas.json` are for evaluation, not inputs to an uncalibrated LLM prompt. `description_en` supplies only the single attribute and population scope. All other traveller/journey characteristics remain unspecified.

## Reproduction

With Python 3 and its standard library, from the repository root:

```text
python src/prepare_data.py --offline
python src/select_personas.py
```

The archived translation mapping makes the previous workbook translation files unnecessary. Without `--offline`, existing verified responses are reused; missing requested responses are retrieved from the public API. The scripts refuse silent changes to the frozen rule/profile fingerprint. No new network requests are needed to reconstruct the committed analysis data.

Optional day-journey collection is supported by `--day-selected` but is not part of this experiment. The day module splits local public transport into separate overlapping bus, metro/tram and S-Bahn flags; summing their marginal shares does not identify the combined local-PT outcome. A day local-PT union must remain unavailable without a valid joint table or microdata.

## Official methodological references

- [MiD 2023 publication catalogue](https://www.mobilitaet-in-deutschland.de/publikationen2023.html).
- [Data-use handbook](https://www.mobilitaet-in-deutschland.de/pdf/infas_HandbuchZurDatennutzung_MiD2023_7555.pdf), pp. 11–12 (survey and recall), 23–25 (record structure), 31–32 (weights).
- Supplementary study materials, available through the catalogue: PDF p. 20 (module population, recall and household-companion question), p. 21 (combined outward/return multiple-mode question), p. 164 (companion processing and aircraft-first main-mode hierarchy).

The study archive separately retains downloaded official methodological originals and their provenance. The full public JSON responses in `data/raw/mit` are the authoritative numerical inputs for this benchmark.
