"""Read-only diagnostic calculations; writes only diagnostic JSON."""
import csv, json, hashlib, statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

root = Path.cwd()
MODES = ['car', 'local_pt', 'long_distance_rail']
def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
numbers = json.loads((root/'results/processed/paper_numbers.json').read_text())
active = set(numbers['active_model_ids'])
preds = []
for r in rows(root/'results/processed/prediction_summary.csv'):
    if r['model_id'] not in active:
        continue
    p = {k:r[k] for k in ['model_id','model_label','arm','persona_id','feature','category_label','mode_id']}
    for k in ['observed_share','predicted_mean','predicted_sd','predicted_min','predicted_max','weighted_base','unweighted_n']:
        p[k] = float(r[k])
    p['bias_pp'] = 100*(p['predicted_mean']-p['observed_share'])
    p['absolute_error_pp'] = abs(p['bias_pp'])
    preds.append(p)
byfm = defaultdict(list)
for p in preds:
    byfm[(p['model_id'],p['arm'],p['feature'],p['mode_id'])].append(p)
feature_mode = []
for (m,a,f,mode),rs in byfm.items():
    total = sum(r['weighted_base'] for r in rs)
    def wm(k):
        return sum(r['weighted_base']*r[k] for r in rs)/total
    feature_mode.append({'model_id':m,'model_label':rs[0]['model_label'],'arm':a,'feature':f,'mode_id':mode,
        'cohorts':len(rs),'weighted_base_sum_within_feature':total,'weighted_mae_pp':wm('absolute_error_pp'),
        'weighted_bias_pp':wm('bias_pp'),'weighted_observed_share':wm('observed_share'),
        'weighted_predicted_share':wm('predicted_mean'),'overpredicted_cells':sum(r['bias_pp']>1e-9 for r in rs),
        'underpredicted_cells':sum(r['bias_pp']<-1e-9 for r in rs)})
by_mode = defaultdict(list)
for r in feature_mode:
    by_mode[(r['model_id'],r['arm'],r['mode_id'])].append(r)
mode_metrics = []
for (m,a,mode),rs in by_mode.items():
    mode_metrics.append({'model_id':m,'model_label':rs[0]['model_label'],'arm':a,'mode_id':mode,
        'feature_equal_mean_mae_pp':statistics.mean(r['weighted_mae_pp'] for r in rs),
        'feature_equal_mean_bias_pp':statistics.mean(r['weighted_bias_pp'] for r in rs),
        'overpredicted_cells':sum(r['overpredicted_cells'] for r in rs),
        'underpredicted_cells':sum(r['underpredicted_cells'] for r in rs),'cells':sum(r['cohorts'] for r in rs)})
contrasts = []
for m in sorted(active):
    for a in ['unanchored','overall_rate_anchored']:
        for mode in MODES:
            low = next(r for r in preds if r['model_id']==m and r['arm']==a and r['feature']=='anzauto_gr1' and r['category_label']=='No car' and r['mode_id']==mode)
            high = next(r for r in preds if r['model_id']==m and r['arm']==a and r['feature']=='anzauto_gr1' and r['category_label']=='4 or more cars' and r['mode_id']==mode)
            obs = 100*(high['observed_share']-low['observed_share'])
            pred = 100*(high['predicted_mean']-low['predicted_mean'])
            contrasts.append({'model_id':m,'model_label':low['model_label'],'arm':a,'mode_id':mode,
                'contrast':'4 or more household cars minus no household car','observed_difference_pp':obs,
                'predicted_difference_pp':pred,'contrast_error_pp':pred-obs,'same_direction':obs*pred>0,
                'no_car_observed_share':low['observed_share'],'no_car_predicted_share':low['predicted_mean'],
                'four_plus_observed_share':high['observed_share'],'four_plus_predicted_share':high['predicted_mean']})
raw = defaultdict(list)
raw_count = 0
for p in (root/'results/raw').glob('*.json'):
    if p.name.endswith('.request.json'):
        continue
    rec = json.loads(p.read_text(encoding='utf-8-sig'))
    raw_count += 1
    if rec.get('model_id') in active and rec.get('status')=='valid' and rec.get('persona_id')!='no_persona':
        for mode in MODES:
            raw[(rec['model_id'],rec['arm'],rec['persona_id'],mode)].append(float(rec['prediction'][mode]))
maxdiff = 0
for r in preds:
    v = raw[(r['model_id'],r['arm'],r['persona_id'],r['mode_id'])]
    assert len(v)==3
    maxdiff = max(maxdiff,abs(statistics.mean(v)-r['predicted_mean']))
assert maxdiff < 1e-12
maxmetric = 0
for r in rows(root/'results/processed/model_metrics.csv'):
    if r['model_id'] not in active:
        continue
    fm = [x for x in feature_mode if x['model_id']==r['model_id'] and x['arm']==r['arm']]
    maxmetric = max(maxmetric,abs(statistics.mean(x['weighted_mae_pp'] for x in fm)-float(r['mae'])))
assert maxmetric < 1e-10
sources = ['results/processed/prediction_summary.csv','results/processed/model_metrics.csv','results/processed/feature_metrics.csv','data/processed/cohort_mode_shares.csv','data/processed/feature_selection.csv','config/experiment.json']
result = {'audit_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'Post hoc descriptive diagnostics of the completed MiD benchmark. No new experiments, no causal or person-level interpretation, no FMG target claims.',
    'unit':'Aircraft-containing journeys with at least one overnight stay; nonexclusive additional modes anywhere on that journey.',
    'error_definition':'Prediction minus observed weighted share, in percentage points. Within each feature and mode weight by its rounded survey cohort base; average equally across features when reporting mode summaries. Never pool overlapping cohort counts.',
    'sources':[{'path':p,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest()} for p in sources],
    'validation':{'terminal_raw_records':raw_count,'primary_prediction_rows':len(preds),'raw_three_repeat_mean_max_abs_diff':maxdiff,'overall_weighted_mae_max_abs_diff_pp':maxmetric,'source_files_changed':False},
    'mode_diagnostics':mode_metrics,'feature_mode_diagnostics':feature_mode,
    'household_car_extreme_contrasts':contrasts,'cohort_predictions':preds,
    'largest_anchored_errors':sorted([r for r in preds if r['arm']=='overall_rate_anchored'],key=lambda r:r['absolute_error_pp'],reverse=True)[:24]}
(root/'results/diagnostics_initial.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('MODE DIAGNOSTICS')
for r in mode_metrics:
    print(r['model_label'],r['arm'],r['mode_id'],'MAE',round(r['feature_equal_mean_mae_pp'],2),'bias',round(r['feature_equal_mean_bias_pp'],2),'over/under',r['overpredicted_cells'],r['underpredicted_cells'])
print('EXTREME HOUSEHOLD-CAR CONTRASTS')
for r in contrasts:
    print(r['model_label'],r['arm'],r['mode_id'],'observed',round(r['observed_difference_pp'],2),'predicted',round(r['predicted_difference_pp'],2),'error',round(r['contrast_error_pp'],2))
print('GPT4.1 ANCHORED REGION MODES')
for r in preds:
    if r['model_id']=='openai/gpt-4.1' and r['arm']=='overall_rate_anchored' and r['feature']=='RegioStaR7':
        print(r['category_label'],r['mode_id'],'observed',round(100*r['observed_share'],2),'pred',round(100*r['predicted_mean'],2),'bias',round(r['bias_pp'],2),'n',r['unweighted_n'])
print('ANCHOR TOP ERRORS')
for r in result['largest_anchored_errors'][:12]:
    print(r['model_label'],r['feature'],r['category_label'],r['mode_id'],round(100*r['observed_share'],2),round(100*r['predicted_mean'],2),round(r['bias_pp'],2))
print('VALIDATION',result['validation'])
