"""Prepare data-only workbook appendices from the independently checked study outputs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results/sequential_20261125'


def main():
    qa = json.loads((RESULTS / 'analysis_qa.json').read_text())
    if qa['status'] != 'PASS':
        raise ValueError('Analysis must pass independent reconstruction before workbook export')
    data = json.loads((RESULTS / 'table_numbers.json').read_text())
    source = ROOT / 'data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx'
    output = ROOT / 'data/workbooks/MiD2023_MUC_LLM_Comprehensive_EN_20261125.xlsx'
    predictions = list(csv.DictReader((RESULTS / 'averaged_predictions.csv').open(encoding='utf8', newline='')))
    modes = {'car': 'Car (driver or passenger)', 'local_pt': 'Local bus or train',
        'long_distance_rail': 'Long-distance train', 'car_dropoff': 'Private car: drop-off',
        'car_airport_parking': 'Private car: airport parking',
        'car_offairport_parking': 'Private car: off-airport parking',
        'car_other_parking': 'Private car: other parking', 'taxi_ridehail': 'Taxi / ride-hail',
        'rental_carsharing': 'Rental car / car-sharing', 'bus_transfer': 'Bus / transfer',
        's_bahn': 'S-Bahn', 'uefex': 'UEFEX regional train', 'other': 'Other'}
    source_url = 'https://github.com/jtzach/air-passenger-LLM-PDM-study/tree/main/results/sequential_20261125'
    def hint(arm):
        return 'Overall MiD rates' if arm == 'overall_rate_anchored' else 'None'
    def num(value):
        return float(value) if value not in ('', None) else None
    metrics = []
    for block in data['blocks']:
        metrics.append([('MiD 2023' if block['panel_id'] == 'mid_2023' else 'Munich FMG 2025'),
            block['model_label'], hint(block['arm']), block['complete_prefix_rounds'],
            block.get('ensemble_mae_pp'), block.get('no_card_ensemble_mae_pp'), block['baseline_mae_pp'],
            block.get('primary_median_gain_pp'), block.get('primary_lower_pp'), block.get('primary_upper_pp'),
            block.get('primary_checkpoint_round'), block.get('primary_decision'), block['halt_reason'],
            block['inference_assumptions_ok'], block['block_id']])
    sheets = [{
        'name': '32_Sequential_results',
        'note': 'New repeated-run study. Errors are percentage points (pp), lower is better. Positive median gain favors the LLM over the constant-rate baseline. Earlier sheets retain the original pilot.',
        'source': source_url + '/block_metrics.csv',
        'headers': ['Dataset', 'Model', 'Hint', 'Complete rounds', 'Mean-prediction MAE (pp)',
            'No-card MAE (pp)', 'Constant baseline MAE (pp)', 'Median round gain (pp)',
            'Adjusted lower limit (pp)', 'Adjusted upper limit (pp)', 'Inference checkpoint',
            'Inference decision', 'Stopping reason', 'Service checks passed', 'Block ID'],
        'rows': metrics, 'widths': [22, 26, 24, 16, 22, 20, 22, 22, 22, 22, 20, 31, 38, 22, 15],
        'formats': {**{c:'0.00' for c in 'EFGHIJ'}, 'D':'0', 'K':'0'}, 'formulas': {}, 'preview': 'A1:H10'}]
    for panel, name, note in [
        ('mid_2023', '33_MiD_new_predictions', 'MiD only: nonexclusive transport co-use during whole outward/return air journeys. Three rates need not total 100%. These are group-level predictions, not simulated individuals.'),
        ('fmg_2025', '34_MUC_new_predictions', 'Munich FMG only: one reported airport-access category per originating departing passenger. Ten shares total 100%. Group targets are approved derived results; private source rows and counts are excluded.')]:
        rows = []
        for row in predictions:
            if row['panel_id'] != panel:
                continue
            rows.append([row['model_label'], hint(row['arm']), row['group'], modes[row['mode']],
                num(row['observed']), num(row['predicted_mean']), None, None, int(row['n_rounds']),
                num(row['predicted_sd']), num(row['predicted_min']), num(row['predicted_max']),
                num(row['card_weight']), row['feature'], row['card_id'], row['block_id']])
        sheets.append({'name': name, 'note': note,
            'source': source_url + '/averaged_predictions.csv; error = 100 × (predicted − observed). SD describes model-run variation.',
            'headers': ['Model', 'Hint', 'Passenger group', 'Transport category', 'Observed share',
                'Mean LLM share', 'Signed error (pp)', 'Absolute error (pp)', 'Complete rounds',
                'Run SD', 'Lowest run', 'Highest run', 'Group weight', 'Attribute', 'Card ID', 'Block ID'],
            'rows': rows, 'widths': [26, 24, 42, 38, 18, 18, 18, 18, 17, 17, 17, 17, 19, 23, 28, 15],
            'formats': {**{c:'0.0%' for c in ['E','F','J','K','L']}, 'M':'0.0000', 'G':'0.00', 'H':'0.00', 'I':'0'},
            'formulas': {'G':'=100*(F{r}-E{r})', 'H':'=ABS(G{r})'}, 'preview':'A1:I10'})
    targets = data['fmg_derived_groups']
    native_modes = list(targets[0]['observed'])
    sheets.append({'name': '35_MUC_derived_targets',
        'note': 'Six approved purpose × flight-region aggregates from the co-author FMG 2025 summary. Direction and journey duration are pooled. Weights describe target-group composition, not survey interview counts.',
        'source': 'FMG_MUC_FILTERDATA_Access_ModalSplit_Overview_final.xlsx, sheet 2_VHG_30_groups; local aggregation documented in docs/FMG_PROVENANCE.md.',
        'headers': ['Munich passenger group', 'Population weight'] + [modes[m] for m in native_modes] + ['Share total'],
        'rows': [[t['group'], t['weight']] + [t['observed'][m] for m in native_modes] + [None] for t in targets],
        'widths': [39, 21] + [27]*len(native_modes) + [18],
        'formats': {c:'0.0%' for c in 'BCDEFGHIJKLM'}, 'formulas': {'M':'=SUM(C{r}:L{r})'}, 'preview':'A1:H11'})
    result = {'source':str(source), 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'output':str(output), 'analysis_plan_sha256':data['plan_sha256'], 'sheets':sheets}
    dest = ROOT / 'data/processed/sequential_workbook_inputs.json'
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'prepared':str(dest), 'sheets':{s['name']:len(s['rows']) for s in sheets}}))


if __name__ == '__main__':
    main()
