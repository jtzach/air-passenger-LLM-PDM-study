"""Prepare typed JSON for the authorised four-sheet Excel appendix."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def number(value):
    return float(value) if value not in ('', None) else None


def main():
    source = ROOT/'data/workbooks/MiD2023_Comprehensive_Data_EN.xlsx'
    features = read_json(ROOT/'data/processed/feature_selection_details.json')
    cohorts = read_json(ROOT/'data/processed/cohort_mode_shares.json')
    predictions = read_csv(ROOT/'results/processed/prediction_summary.csv')
    metrics = read_csv(ROOT/'results/processed/model_metrics.csv')
    paper = read_json(ROOT/'results/processed/paper_numbers.json')
    records = []
    for r in cohorts:
        if r['mode_id'] != 'car':
            continue
        group = [x for x in cohorts if x['stratum_id'] == r['stratum_id']]
        rates = {x['mode_id']:x['observed_share'] for x in group}
        records.append([r['feature_label_en'], r['stratum_label_en'], 'Yes' if r['selected'] else 'No',
                        r['unweighted_base'], r['weighted_base'], rates['car'], rates['local_pt'], rates['long_distance_rail'],
                        'Yes' if r['eligible'] else ('Baseline' if r['feature_id']=='__all__' else 'No'),
                        r['feature_id'], r['stratum_id'], r['persona_id'], r['source_file'], r['source_table'],
                        r['source_sha256'], r['outcome_status'], r['stratum_label_de']])
    sheets = [
        {'name':'Persona feature screening',
         'note':'Descriptive in-sample screening: two traveller and two journey attributes. Minimum stratum N=100; minimum weighted coverage=80%.',
         'source':'Source: MiT public tables, retrieved 24 November 2026. Frozen selection rule in docs/data_dictionary.md. Score is mean normalized Bernoulli information gain.',
         'headers':['Overall rank','Attribute','Public variable','Family','Eligible strata','Retained journeys (N)','Weighted coverage','Normalized information gain','Information gain (bits)','Selected','Family rank','Retained weighted base'],
         'rows':[[r['rank'],r['feature_label_en'],r['feature_id'],r['family'],r['eligible_strata'],r['eligible_unweighted_n'],r['weighted_coverage'],r['score_mean_normalized_ig'],r['score_mean_ig_bits'],'Yes' if r['selected'] else 'No',r['rank_within_eligible_family'],r['eligible_weighted_base']] for r in features],
         'widths':[13,34,19,13,15,18,18,22,20,13,15,19], 'formats':{'F':'#,##0','G':'0.00%','H':'0.0000','I':'0.0000','L':'#,##0'},
         'preview':'A1:J19'},
        {'name':'Aircraft cohort rates',
         'note':'OBSERVED SURVEY AGGREGATES. Outward/return ground-mode co-use within aircraft-containing overnight journeys. Overlapping outcomes; not airport access.',
         'source':'Source: https://mobilitaet-in-tabellen-2023.bast.de/ . All candidate strata retained. Exact source files, table positions and response hashes appear to the right.',
         'headers':['Attribute','Category','Selected profile','Unweighted journeys (N)','Rounded weighted base','Car co-use','Local PT co-use','Long-distance rail co-use','Eligible stratum','Public variable','Stratum identifier','Persona identifier','Archived source file','Source table (1-based)','Response SHA-256','Outcome status','Original German category'],
         'rows':records,'widths':[32,52,16,19,20,15,17,23,18,19,39,44,68,20,68,32,59],
         'formats':{'D':'#,##0','E':'#,##0','F':'0.0%','G':'0.0%','H':'0.0%'},'preview':'A1:H14'},
        {'name':'LLM predictions',
         'note':'MODEL OUTPUTS AND EVALUATION TARGETS. Probabilities are means across repeated prompts. Controls repeat constant predictions across cohorts; no individual synthetic passengers.',
         'source':'Source: recorded OpenRouter calls; results/processed/prediction_summary.csv. Min, max and SD describe prompt variation, not survey uncertainty. Observed rates remain separate.',
         'headers':['Model','Prompt arm','Attribute','Category','Outcome','Observed survey rate','Predicted mean','Prompt SD','Prompt minimum','Prompt maximum','Repeats','Journey N','Weighted base','Model group','Model identifier','Persona identifier'],
         'rows':[[r['model_label'],r['arm'],r['feature'],r['category_label'],r['mode_id'],number(r['observed_share']),number(r['predicted_mean']),number(r['predicted_sd']),number(r['predicted_min']),number(r['predicted_max']),number(r['n_repeats']),number(r['unweighted_n']),number(r['weighted_base']),r['model_group'],r['model_id'],r['persona_id']] for r in predictions],
         'widths':[32,29,20,52,24,20,18,16,18,18,12,15,18,25,43,45],
         'formats':{'F':'0.0%','G':'0.0%','H':'0.0%','I':'0.0%','J':'0.0%','K':'0','L':'#,##0','M':'#,##0'},'preview':'A1:H13'},
        {'name':'LLM model results',
         'note':f"EVALUATION RESULTS. {paper['n_personas_common_panel']} cohort profiles; {paper['n_models']} complete models, {paper['n_arms']} arms, {paper['n_repeats']} repeats. Gemma 3 12B excluded: 11/144 valid calls. Full call availability below. Smaller error is better.",
         'source':'Source: results/processed/model_metrics.csv. Weight strata within each feature/mode, then average equally across features and modes. Percentage-point errors; JSD in bits.',
         'headers':['Model','Prompt arm','Model group','MAE (pp)','RMSE (pp)','Signed bias (pp)','Centred MAE (pp)','Bernoulli JSD (bits)','Maximum error (pp)','Equal-stratum MAE (pp)','Repeat MAE minimum (pp)','Repeat MAE maximum (pp)','Cohort-mode cells','Features','Model identifier'],
         'rows':[[r['model_label'],r['arm'],r['model_group'],number(r['mae']),number(r['rmse']),number(r['bias_pp']),number(r['centred_mae_pp']),number(r['bernoulli_jsd_bits']),number(r['max_absolute_error_pp']),number(r['equal_stratum_mae_pp']),number(r['repeat_mae_min_pp']),number(r['repeat_mae_max_pp']),number(r['n_cohort_mode_cells']),number(r['n_features']),r['model_id']] for r in metrics],
         'widths':[33,29,25,15,16,19,20,23,22,24,24,24,20,14,44],
         'formats':{**{c:'0.00' for c in 'DEFGIJKL'},'H':'0.0000','M':'0','N':'0'},'preview':'A1:H16',
         'extra_table':{'title':'Call availability for all attempted models',
                        'headers':['Model','Planned calls','Valid calls','Invalid output','Failed calls','Primary comparison'],
                        'rows':[[r['model_label'],r['planned_calls'],r['valid_calls'],r['invalid_output_calls'],r['failed_calls'],'Included' if r['primary_panel'] else 'Excluded'] for r in paper['model_availability']]}}
    ]
    payload = {'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sheets':sheets}
    out=ROOT/'data/processed/workbook_appendix_inputs.json'
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({s['name']:len(s['rows']) for s in sheets}))


if __name__=='__main__':
    main()
