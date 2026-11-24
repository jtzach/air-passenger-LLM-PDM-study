"""Select single-attribute aggregate cohort profiles under the frozen protocol.

Selection is descriptive and in-sample. Published weights are case-normalised,
rounded denominator estimates, not independent sample counts or individual data.
No p-values, synthetic joint records, or inferential intervals are constructed.
"""
from __future__ import annotations
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone

from prepare_data import PROCESSED, RAW, ROOT, PROTOCOL, FEATURE_INFO, MODE_LABELS, dump, freeze_protocol, sha, write_csv


MISSING = re.compile(r"no answer|don't know|refus|not collected|not received|cannot be|cannot classify|cannot.*calculat|no information|without information|unknown|proxy|not applicable|person under|child under|keine angabe|weiß nicht|weiss nicht|verweiger|nicht erhoben|nicht erhalten|nicht zuzuordnen|nicht zu berechnen|ohne info", re.I)

def entropy(probability):
    assert 0 <= probability <= 1
    return -sum(p * math.log2(p) for p in (probability, 1-probability) if p > 0)

def substantive(row):
    return not MISSING.search(row['stratum_label_en'] + ' ' + row['stratum_label_de'])

def score_feature(rows, overall_weighted):
    strata = defaultdict(list)
    for row in rows:
        strata[row['stratum_id']].append(row)
    eligible = []
    excluded = []
    for sid, values in strata.items():
        first = values[0]
        reasons = []
        if not substantive(first):
            reasons.append('response_or_design_missing_category')
        if first['unweighted_base'] is None or first['unweighted_base'] < PROTOCOL['minimum_unweighted_stratum_n']:
            reasons.append('unweighted_n_below_100')
        if first['weighted_base'] is None or first['weighted_base'] <= 0:
            reasons.append('no_positive_weighted_base')
        if len(values) != 3 or any(r['observed_share'] is None for r in values):
            reasons.append('incomplete_three_outcome_profile')
        if reasons:
            excluded.append({'stratum_id': sid, 'label': first['stratum_label_en'], 'reasons': reasons,
                             'unweighted_n': first['unweighted_base'], 'weighted_base': first['weighted_base']})
        else:
            eligible.append(values)
    mass = sum(group[0]['weighted_base'] for group in eligible)
    coverage = mass / overall_weighted
    scores = {}
    if mass:
        for mode in MODE_LABELS:
            pairs = [(g[0]['weighted_base'], next(r['observed_share'] for r in g if r['mode_id'] == mode)) for g in eligible]
            pooled = sum(w*p for w,p in pairs)/mass
            pooled_entropy = entropy(pooled)
            gain = max(0.0, pooled_entropy-sum(w*entropy(p) for w,p in pairs)/mass)
            scores[mode] = {'pooled_share_eligible': pooled, 'entropy_bits': pooled_entropy,
                            'information_gain_bits': gain,
                            'normalized_information_gain': gain/pooled_entropy if pooled_entropy else 0.0}
    eligible_feature = len(eligible) >= PROTOCOL['minimum_eligible_strata'] and coverage >= PROTOCOL['minimum_feature_weighted_coverage']
    return {'eligible_strata': len(eligible), 'weighted_coverage': coverage,
            'eligible_weighted_base': mass,
            'eligible_unweighted_n': sum(g[0]['unweighted_base'] for g in eligible),
            'score_mean_normalized_ig': sum(v['normalized_information_gain'] for v in scores.values())/3 if scores else None,
            'score_mean_ig_bits': sum(v['information_gain_bits'] for v in scores.values())/3 if scores else None,
            'feature_eligible': eligible_feature, 'mode_scores': scores,
            'eligible_stratum_ids': [g[0]['stratum_id'] for g in eligible], 'excluded_strata': excluded}

def main():
    freeze_protocol()
    rows = json.loads((PROCESSED/'cohort_mode_shares_raw.json').read_text(encoding='utf-8'))
    baseline = json.loads((PROCESSED/'overall_baseline.json').read_text(encoding='utf-8'))
    protocol_snapshot = json.loads((PROCESSED/'selection_protocol.json').read_text(encoding='utf-8'))
    by_feature = defaultdict(list)
    for row in rows:
        if row['feature_id'] != '__all__':
            by_feature[row['feature_id']].append(row)
    assert set(by_feature) == set(FEATURE_INFO)
    scores = []
    for feature, values in by_feature.items():
        scores.append({'feature_id': feature, 'feature_label_en': FEATURE_INFO[feature]['label'],
                       'family': FEATURE_INFO[feature]['family'], **score_feature(values, baseline['weighted_base'])})
    ranked = sorted(scores, key=lambda s: (-(s['score_mean_normalized_ig'] or 0), s['feature_id']))
    selected = []
    family_ranks = {}
    for family, count in PROTOCOL['selected_features_per_family'].items():
        candidates = [s for s in ranked if s['family'] == family and s['feature_eligible']]
        assert len(candidates) >= count, (family, len(candidates))
        for rank, score in enumerate(candidates, 1):
            family_ranks[score['feature_id']] = rank
        selected.extend(s['feature_id'] for s in candidates[:count])
    score_by_id = {}
    for rank, score in enumerate(ranked, 1):
        score.update(rank=rank, rank_within_eligible_family=family_ranks.get(score['feature_id']), selected=score['feature_id'] in selected)
        score_by_id[score['feature_id']] = score
    personas = []
    grouped = defaultdict(list)
    for row in rows:
        feature = row['feature_id']
        score = score_by_id.get(feature)
        row['eligible'] = bool(score and row['stratum_id'] in score['eligible_stratum_ids'])
        row['selected'] = bool(row['eligible'] and score['selected'])
        row['persona_id'] = 'reise__' + row['stratum_id'] if row['selected'] else None
        if row['selected']:
            grouped[row['persona_id']].append(row)
    for pid, values in grouped.items():
        first = values[0]
        description = ('Cohort of aircraft-containing overnight journeys reported by Germany-resident self-respondents aged 14 or older. '
                       f"The only supplied cohort attribute is {first['feature_label_en'].lower()}: {first['stratum_label_en']}. "
                       'All other traveller and journey characteristics are unspecified.')
        personas.append({'persona_id': pid, 'feature': first['feature_id'], 'feature_label': first['feature_label_en'],
                         'feature_family': first['feature_family'], 'stratum_id': first['stratum_id'],
                         'category_code': None, 'category_label': first['stratum_label_en'],
                         'category_label_de': first['stratum_label_de'], 'description_en': description,
                         'unweighted_n': first['unweighted_base'], 'weighted_base': first['weighted_base'],
                         'observed': {r['mode_id']: r['observed_share'] for r in values},
                         'scope': 'single_attribute_cohort_not_an_individual_or_joint_persona',
                         'category_code_note': 'Public response provides category labels, not numerical category codes. stratum_id is a derived archive identifier, not a survey code.',
                         'provenance': {'source_file': first['source_file'], 'source_sha256': first['source_sha256'],
                                        'source_table': first['source_table'], 'source_column': first['source_column'],
                                        'weight_variable': first['weight_variable'], 'retrieved_utc': first['retrieved_utc']}})
    personas.sort(key=lambda p: (selected.index(p['feature']), p['stratum_id']))
    hashes = {r['source_file']: r['source_sha256'] for r in rows}
    fingerprint = {'protocol_sha256': protocol_snapshot['sha256'], 'input_hashes': hashes,
                   'selected_features': selected, 'personas_sha256': sha(json.dumps(personas, sort_keys=True, ensure_ascii=False).encode())}
    frozen_path = PROCESSED/'selection_freeze.json'
    if frozen_path.exists():
        frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
        assert frozen['fingerprint'] == fingerprint, 'Frozen selection changed; do not silently alter an experiment.'
    else:
        dump(frozen_path, {'frozen_utc': datetime.now(timezone.utc).isoformat(), 'fingerprint': fingerprint,
                           'note': 'Frozen before study LLM predictions; not before all exploratory inspection of public data.'})
    dump(PROCESSED/'personas.json', personas)
    dump(PROCESSED/'feature_selection_details.json', ranked)
    write_csv(PROCESSED/'feature_selection.csv', [{k:v for k,v in s.items() if k not in ['mode_scores','eligible_stratum_ids','excluded_strata']} for s in ranked])
    write_csv(PROCESSED/'cohort_mode_shares.csv', rows)
    dump(PROCESSED/'cohort_mode_shares.json', rows)
    summary = {'selected_features': selected, 'persona_count': len(personas), 'candidate_feature_count': len(scores),
               'selected_counts_by_feature': {f:sum(p['feature']==f for p in personas) for f in selected},
               'overall_baseline': baseline,
               'limitations': ['In-sample descriptive selection; no p-values or causal effects.',
                               'Correlated feature families are screened separately; no claim of independent variable importance.',
                               'Marginal strata overlap across different features and must not be counted as independent passengers.',
                               'Information-gain weighting uses rounded weighted subgroup bases; tiny rounding differences are retained.',
                               'Performance on selected cohorts is not generalization to unseen respondents or airports.',
                               'B1 microdata have not been obtained; no individual records are present.']}
    dump(PROCESSED/'selection_summary.json', summary)
    print(json.dumps({'selected_features': selected, 'persona_count': len(personas),
                      'selected_counts_by_feature': summary['selected_counts_by_feature']},ensure_ascii=False),flush=True)

if __name__ == '__main__':
    main()
