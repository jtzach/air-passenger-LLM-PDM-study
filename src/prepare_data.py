"""Archive and normalize public MiT cross-tabulations; never obtain microdata.

Run: python src/prepare_data.py --translations-dir ../outputs/mid2023_english_20261118
Then: python src/select_personas.py
Optional after selection: python src/prepare_data.py --day-selected
Cached raw files and the archived translation lookup permit offline reproduction.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/mit'
PROCESSED = ROOT / 'data/processed'
BASE = 'https://mobilitaet-in-tabellen-2023.bast.de'
FEATURES = [
    ('alter_gr4', 'Age group', 'traveller', 'alter_gr4'),
    ('HP_SEX', 'Gender category', 'traveller', 'HP_SEX'),
    ('bildung', 'Educational attainment', 'traveller', 'bildung'),
    ('erwerb', 'Employment status', 'traveller', 'erwerb'),
    ('hheink_gr2', 'Monthly net household income', 'traveller', 'hheink_gr2'),
    ('anzauto_gr1', 'Number of household cars', 'traveller', 'anzauto_gr1'),
    ('hhgr_gr', 'Household size', 'traveller', 'hhgr_gr'),
    ('RegioStaR7', 'Residential spatial type', 'traveller', 'RegioStaR7'),
    ('P_FS_PKW', 'Car driving licence held', 'traveller', 'P_FS_PKW'),
    ('R_ZWECK', 'Main journey purpose', 'journey', 'TR_ZWECK'),
    ('R_ZIEL', 'Journey destination region', 'journey', 'TR_ZIEL'),
    ('entf_gr', 'One-way journey distance', 'journey', 'tr_entf_gr'),
    ('anzueb_gr', 'Number of nights away', 'journey', None),
    ('anzbegl_gr', 'Number of household companions', 'journey', 'tr_anzbegl_gr'),
]
FEATURE_INFO = {f[0]: {'label': f[1], 'family': f[2], 'day_feature': f[3]} for f in FEATURES}
MODE_LABELS = {'car': 'Auto', 'local_pt': 'Bus oder Bahn im Nahverkehr', 'long_distance_rail': 'Fernzug'}
PROTOCOL = {
    'version': '1.0',
    'primary_dataset': 'reise',
    'candidate_features': [dict(feature_id=f[0], label=f[1], family=f[2]) for f in FEATURES],
    'outcomes': list(MODE_LABELS),
    'minimum_unweighted_stratum_n': 100,
    'minimum_feature_weighted_coverage': 0.80,
    'minimum_eligible_strata': 2,
    'selected_features_per_family': {'traveller': 2, 'journey': 2},
    'feature_score': 'Arithmetic mean across outcomes of weighted Bernoulli information gain divided by entropy of the eligible-strata pooled prevalence.',
    'tie_break': 'Feature identifier in ascending lexical order.',
    'stratum_selection': 'All eligible substantive strata of each selected feature; no post-selection preference for large contrasts.',
    'missing_category_rule': 'Exclude response/design-missing categories; preserve substantive negative categories, such as not employed or no household car.',
    'scope': 'Single-attribute cohort profiles, never joint personas or pseudoindividual records.',
    'interpretation': 'Descriptive in-sample separation, not causal importance, independent validation, or statistical significance.',
    'disclosure': 'Protocol specified after earlier exploratory public age tables were inspected, but before fresh candidate-feature queries and before any study LLM predictions. This is not an externally registered preregistration.',
}

def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()

def freeze_protocol():
    path = PROCESSED / 'selection_protocol.json'
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        assert old['protocol'] == PROTOCOL, 'Selection protocol changed; use an explicit new version.'
        return
    content = json.dumps(PROTOCOL, sort_keys=True, ensure_ascii=False).encode()
    dump(path, {'specified_utc': datetime.now(timezone.utc).isoformat(), 'sha256': sha(content), 'protocol': PROTOCOL})

def fetch(path: str, filename: str, payload=None):
    target = RAW / filename
    metadata_path = RAW / (filename + '.provenance.json')
    request_path = RAW / (filename + '.request.json')
    if target.exists() and metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding='utf-8'))
        assert meta['request'] == payload
        assert sha(target.read_bytes()) == meta['sha256']
        return json.loads(target.read_text(encoding='utf-8'))
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8') if payload is not None else None
    headers = {'Accept': 'application/json', 'User-Agent': 'MiD2023 aggregate research reproducibility archive'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
        dump(request_path, payload)
    error = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(BASE + path, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=55) as response:
                data = response.read()
                response_headers = {k: response.headers[k] for k in ['Content-Type', 'Date', 'ETag', 'Last-Modified'] if k in response.headers}
            parsed = json.loads(data)
            target.write_bytes(data)
            dump(metadata_path, {'url': BASE + path, 'method': 'POST' if body else 'GET',
                                 'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'bytes': len(data),
                                 'sha256': sha(data), 'request_sha256': sha(body) if body else None,
                                 'request': payload, 'response_headers': response_headers})
            return parsed
        except Exception as exc:
            error = repr(exc)
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f'{filename}: {error}')

def translation_lookup(directory: Path | None):
    cached = RAW / 'category_translations.json'
    lookup = json.loads(cached.read_text(encoding='utf-8')) if cached.exists() else {}
    if directory:
        for stem in ['context', 'codebook', 'questions']:
            ip = directory / f'inventory_{stem}.json'
            tp = directory / f'translations_{stem}.json'
            if ip.exists() and tp.exists():
                mapping = json.loads(tp.read_text(encoding='utf-8'))
                for row in json.loads(ip.read_text(encoding='utf-8')):
                    if row['id'] in mapping:
                        lookup[row['source'].strip()] = mapping[row['id']]
    # Fixed wording for category labels which have different phrasing in the portal.
    lookup.update({'__all__': 'All aircraft-containing journeys', 'ja': 'Yes', 'nein': 'No',
                   'erwerbstätig': 'Employed', 'nicht erwerbstätig': 'Not employed',
                   'männlich': 'Male', 'weiblich': 'Female', 'divers': 'Diverse',
                   '(noch) ohne Abschluss': 'No qualification (yet)', 'anderer Abschluss': 'Other qualification',
                   'innerhalb Deutschlands': 'Within Germany',
                   'Urlaub, Kurzurlaub oder Ähnliches': 'Holiday, short holiday or similar',
                   'Einkauf / Versorgung': 'Shopping / obtaining supplies',
                   'Besuch von Familie / Verwandten / Freunden/Freundinnen / Bekannten': 'Visiting family / relatives / friends / acquaintances',
                   'andere Privatreise': 'Other private journey',
                   'dienstlich / geschäftlich': 'Business', 'anderes': 'Other'})
    return lookup

def normalize(filename, dataset, feature_id, lookup):
    raw = RAW / filename
    tables = json.loads(raw.read_text(encoding='utf-8'))
    metadata = json.loads((RAW / (filename + '.provenance.json')).read_text(encoding='utf-8'))
    assert sha(raw.read_bytes()) == metadata['sha256'], f'Archived response changed: {filename}'
    rows, needed = [], {}
    for number, table in enumerate(tables, 1):
        aircraft = [i for i, c in enumerate(table['columns']) if c['label'].strip() == 'Flugzeug']
        assert len(aircraft) <= 1, (filename, number)
        # The portal omits a main-mode column when there are no observed cases.
        # Preserve its category with missing outcomes and no invented denominator.
        col = aircraft[0] if aircraft else None
        source_rows = {r['label'].strip(): r for r in table['rows']}
        n = source_rows['Basis (ungewichtet)']['cells'][col].get('text') if col is not None else None
        weighted = source_rows['Basis (gewichtet)']['cells'][col].get('text') if col is not None else None
        breakdown = table['meta'].get('breakdown_info')
        label = str(breakdown['value']).strip() if breakdown else '__all__'
        if label not in lookup:
            raise ValueError(f'English category translation required: {feature_id}: {label!r}')
        english = lookup[label]
        needed[label] = english
        stratum_id = feature_id + '__' + sha(label.encode('utf-8'))[:12]
        info = FEATURE_INFO.get(feature_id, {'label': 'Overall baseline', 'family': 'baseline'})
        for mode, mode_label in MODE_LABELS.items():
            # Day-journey local PT is split into three overlapping indicators. Its
            # union is not available from these marginal tables; never sum them.
            available = mode_label in source_rows and col is not None
            cell = source_rows[mode_label]['cells'][col] if available else {}
            percent = cell.get('percent')
            if percent is not None:
                assert 0 <= percent <= 100
            rows.append({'dataset': dataset, 'feature_id': feature_id, 'feature_label_en': info['label'],
                         'feature_family': info['family'], 'stratum_id': stratum_id,
                         'category_code': None, 'stratum_label_de': label, 'stratum_label_en': english,
                         'mode_id': mode, 'observed_share': percent / 100 if percent is not None else None,
                         'unweighted_base': n, 'weighted_base': weighted,
                         'weighted_count': cell.get('text'),
                         'outcome_status': 'aircraft_column_absent' if col is None else ('observed' if percent is not None else 'not_identifiable_from_published_marginals'),
                         'source_file': str(raw.relative_to(ROOT)).replace('\\', '/'),
                         'source_sha256': metadata['sha256'], 'source_table': number,
                         'source_column': col, 'retrieved_utc': metadata['retrieved_utc'],
                         'weight_variable': table['meta']['weight_var']})
        if col is not None:
            air_share = source_rows['Flugzeug']['cells'][col].get('percent')
            assert air_share in (100, 100.0) or not n, (filename, number, air_share)
    return rows, needed

def write_csv(path, rows):
    assert rows
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_normalized(rows, dataset):
    """Check source integrity and cross-tab consistency without inventing cases."""
    baseline = next(r for r in rows if r['feature_id'] == '__all__')
    report = {'dataset': dataset, 'response_hashes_verified': True,
              'percentage_scale_valid': True, 'denominator_scope': 'aircraft column only',
              'feature_checks': []}
    for feature in dict.fromkeys(r['feature_id'] for r in rows):
        subset = [r for r in rows if r['feature_id'] == feature]
        categories = [r for r in subset if r['mode_id'] == 'car']
        for category in categories:
            group = [r for r in subset if r['stratum_id'] == category['stratum_id']]
            assert {r['mode_id'] for r in group} == set(MODE_LABELS)
            assert len(group) == len(MODE_LABELS)
            assert len({(r['unweighted_base'], r['weighted_base']) for r in group}) == 1
        n = sum(r['unweighted_base'] or 0 for r in categories)
        mass = sum(r['weighted_base'] or 0 for r in categories)
        assert n <= baseline['unweighted_base'], (feature, n)
        # Variable-specific valid bases may be lower. Independently rounded
        # category bases can add to slightly more than the rounded total.
        assert mass <= baseline['weighted_base'] + (len(categories)+1)/2, (feature, mass)
        report['feature_checks'].append({'feature_id': feature, 'returned_strata': len(categories),
                                        'summed_returned_unweighted_n': n,
                                        'summed_returned_weighted_base': mass,
                                        'absent_aircraft_columns': sum(r['source_column'] is None for r in categories),
                                        'note': 'Returned categories may omit variable-specific invalid/missing cases.'})
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--translations-dir', type=Path)
    parser.add_argument('--day-selected', action='store_true')
    parser.add_argument('--offline', action='store_true', help='Require all requested archived responses to exist.')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    freeze_protocol()
    lookup = translation_lookup(args.translations_dir)
    dataset = 'tage' if args.day_selected else 'reise'
    if args.offline:
        catalog = json.loads((RAW / f'vars_{dataset}.json').read_text(encoding='utf-8'))
    else:
        fetch('/api/datasets', 'datasets.json')
        catalog = fetch('/api/vars', f'vars_{dataset}.json', {'id': dataset})
    mode_set = next(v['name'] for v in catalog['rows'] if v['dtype'] == 'virtual_set' and ('verkehrsmittel-der-reise-' in v['name'] if dataset == 'reise' else 'verkehrsmittel-der-tagesreise-' in v['name']))
    variables = {v['name'] for v in catalog['breakdowns']}
    selected = [f[0] for f in FEATURES]
    if args.day_selected:
        selection = json.loads((PROCESSED / 'selection_summary.json').read_text(encoding='utf-8'))
        selected = selection['selected_features']
    queries = [('__all__', None)]
    for feature in selected:
        api_feature = FEATURE_INFO[feature]['day_feature'] if dataset == 'tage' else feature
        if api_feature is not None:
            assert api_feature in variables, api_feature
            queries.append((feature, api_feature))
    specs = []
    for feature, api_feature in queries:
        payload = {'dataset': {'id': dataset}, 'weight_var': 'TR_GEW' if dataset == 'tage' else 'R_GEW',
                   'mean_of': None, 'percent': 'col', 'row': mode_set,
                   'col': 'hvm_tr' if dataset == 'tage' else 'hvm_r', 'breakdown_by': api_feature}
        specs.append((feature, f'{dataset}_modes_by_main_mode__{feature}.json', payload))
    dump(RAW / f'query_plan_{dataset}.json', [{'feature_id': a, 'filename': b, 'request': c} for a,b,c in specs])
    def collect(spec):
        feature, filename, payload = spec
        if args.offline:
            assert (RAW / filename).exists(), filename
        else:
            fetch('/api/table/json', filename, payload)
        print('Archived', filename, flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(collect, specs))
    rows, used = [], {}
    for feature, filename, payload in specs:
        normalized, translations = normalize(filename, dataset, feature, lookup)
        rows.extend(normalized)
        used.update(translations)
    validation = validate_normalized(rows, dataset)
    dump(PROCESSED / ('day_data_validation.json' if dataset == 'tage' else 'data_validation.json'), validation)
    cached_lookup = RAW / 'category_translations.json'
    existing = json.loads(cached_lookup.read_text(encoding='utf-8')) if cached_lookup.exists() else {}
    existing.update(used)
    dump(cached_lookup, existing)
    dump(PROCESSED / ('day_cohort_mode_shares_raw.json' if dataset == 'tage' else 'cohort_mode_shares_raw.json'), rows)
    write_csv(PROCESSED / ('day_cohort_mode_shares_raw.csv' if dataset == 'tage' else 'cohort_mode_shares_raw.csv'), rows)
    baseline = [r for r in rows if r['feature_id'] == '__all__']
    dump(PROCESSED / ('day_overall_baseline.json' if dataset == 'tage' else 'overall_baseline.json'),
         {'dataset': dataset, 'unweighted_n': baseline[0]['unweighted_base'],
          'weighted_base': baseline[0]['weighted_base'], 'observed': {r['mode_id']: r['observed_share'] for r in baseline},
          'provenance': [{'source_file': r['source_file'], 'sha256': r['source_sha256'], 'table': r['source_table']} for r in baseline[:1]],
          'local_pt_note': 'For day journeys the combined local-PT union cannot be recovered from separate overlapping marginal indicators.' if dataset == 'tage' else None})
    print(json.dumps({'dataset': dataset, 'queries': len(specs), 'mode_rows': len(rows),
                      'strata': len(rows)//3, 'baseline_n': baseline[0]['unweighted_base']}), flush=True)

if __name__ == '__main__':
    main()
