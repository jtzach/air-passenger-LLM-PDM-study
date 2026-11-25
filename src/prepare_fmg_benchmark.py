"""Prepare a restricted FMG benchmark locally, without network access.

The source is an aggregate co-author workbook, not passenger microdata. This
script contains no observed rates, counts, weights or numerical source summary.
Supply an authorised local workbook and an output directory OUTSIDE this repo:

    python src/prepare_fmg_benchmark.py --workbook PATH --output PRIVATE_DIRECTORY

Outputs contain restricted source-derived targets and must remain private.
The script does not create prompts, call APIs, or decide publication permission.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

REPOSITORY = Path(__file__).resolve().parents[1]
SHEET = '2_VHG_30_groups'
HEADER_ROW = 6
DATA_ROWS = range(7, 37)
PURPOSES = ('Business', 'Private')
FLIGHT_TYPES = ('Domestic', 'Continental', 'Intercontinental')
MODES = (
    ('car_dropoff', 'Car – dropped off'),
    ('car_airport_parking', 'Car – parked at airport'),
    ('car_offairport_parking', 'Car – off-airport park & ride'),
    ('car_other_parking', 'Car – other parking locations'),
    ('taxi_ridehail', 'Taxi & ride-hailing'),
    ('rental_carsharing', 'Rental car & car sharing'),
    ('bus_transfer', 'Bus & transfer services'),
    ('s_bahn', 'S-Bahn'),
    ('uefex', 'ÜFEX regional train'),
    ('other', 'Other'),
)
EXPECTED_HEADERS = (
    'Traveller type', 'Flight type', 'Purpose', 'Trip duration',
    'Passengers 2025', 'Share of all passengers', 'Flag',
    *(label for _, label in MODES), 'Total',
)


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def finite_number(value, location: str, *, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Expected a finite number at {location}.')
    if positive and value <= 0:
        raise ValueError(f'Expected a positive passenger volume at {location}.')
    return float(value)


def within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def aggregate(records: list[dict]) -> tuple[float, dict[str, float]]:
    denominator = math.fsum(x['annual_passenger_volume'] for x in records)
    rates = {
        mode: math.fsum(x['annual_passenger_volume'] * x['observed'][mode] for x in records) / denominator
        for mode, _ in MODES
    }
    if not math.isclose(math.fsum(rates.values()), 1.0, abs_tol=1e-10, rel_tol=0):
        raise ValueError('Aggregated modes do not sum to one; source was not changed.')
    return denominator, rates


def prepare(workbook_path: Path, output: Path) -> dict:
    workbook_path = workbook_path.expanduser().resolve(strict=True)
    output = output.expanduser().resolve()
    if within(output, REPOSITORY):
        raise ValueError('Restricted outputs must be stored outside the public repository.')
    if output == workbook_path or within(workbook_path, output):
        raise ValueError('Use a separate private output directory that does not contain the source workbook.')
    source_hash = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
    book = load_workbook(workbook_path, data_only=False, read_only=True)
    cached = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        if SHEET not in book.sheetnames:
            raise ValueError(f'Required source sheet {SHEET!r} is absent.')
        source, saved = book[SHEET], cached[SHEET]
        headers = tuple(source.cell(HEADER_ROW, col).value for col in range(1, len(EXPECTED_HEADERS) + 1))
        if headers != EXPECTED_HEADERS:
            raise ValueError('Source headers differ from the audited layout; review the workbook before adapting this script.')
        rows = []
        for r in DATA_ROWS:
            purpose = source.cell(r, 3).value
            flight_type = source.cell(r, 2).value
            if purpose not in PURPOSES or flight_type not in FLIGHT_TYPES:
                raise ValueError(f'Unrecognised purpose or flight-type category in row {r}.')
            volume = finite_number(source.cell(r, 5).value, f'{SHEET}!E{r}', positive=True)
            rates = {}
            for col, (mode, _) in enumerate(MODES, start=8):
                cell = source.cell(r, col)
                if cell.data_type == 'f':
                    raise ValueError(f'{SHEET}!{cell.coordinate} is a formula; expected an observed source value.')
                value = finite_number(cell.value, f'{SHEET}!{cell.coordinate}')
                if not 0 <= value <= 1:
                    raise ValueError(f'Invalid observed proportion at {SHEET}!{cell.coordinate}.')
                rates[mode] = value
            row_sum = math.fsum(rates.values())
            if not math.isclose(row_sum, 1.0, abs_tol=1e-10, rel_tol=0):
                raise ValueError(f'Mode proportions do not sum to one in row {r}; no normalisation was applied.')
            cached_sum = finite_number(saved.cell(r, 18).value, f'{SHEET}!R{r} cached total')
            if not math.isclose(cached_sum, row_sum, abs_tol=1e-10, rel_tol=0):
                raise ValueError(f'Cached row sum differs from observations in row {r}.')
            rows.append(dict(source_row=r, purpose=purpose, flight_type=flight_type,
                             annual_passenger_volume=volume, observed=rates))
        groups = defaultdict(list)
        for row in rows:
            groups[(row['purpose'], row['flight_type'])].append(row)
        expected_groups = {(p, f) for p in PURPOSES for f in FLIGHT_TYPES}
        if set(groups) != expected_groups:
            raise ValueError('The full purpose-by-flight-type cross-tabulation is absent.')
        total, overall_rates = aggregate(rows)
        panels = []
        for purpose in PURPOSES:
            for flight_type in FLIGHT_TYPES:
                members = groups[(purpose, flight_type)]
                denominator, rates = aggregate(members)
                panels.append(dict(
                    persona_id=f'fmg2025_{purpose.lower()}_{flight_type.lower()}',
                    purpose=purpose, flight_type=flight_type,
                    description_en=f'Munich Airport originating departing passengers travelling for {purpose.lower()} purposes on a {flight_type.lower()} departing flight.',
                    annual_passenger_volume=denominator,
                    population_weight=denominator / total,
                    unweighted_n=None,
                    observed=rates,
                    source_rows=[x['source_row'] for x in members],
                ))
        # Independent regrouping: recombine six target distributions and confirm
        # the direct all-row weighted result. This does not test population validity.
        max_recombination_error = max(
            abs(math.fsum(p['population_weight'] * p['observed'][mode] for p in panels) - overall_rates[mode])
            for mode, _ in MODES
        )
        if max_recombination_error > 1e-12:
            raise ValueError('Six-group recombination failed.')
        source_unchanged = hashlib.sha256(workbook_path.read_bytes()).hexdigest() == source_hash
        if not source_unchanged:
            raise RuntimeError('Source workbook changed during extraction.')
        target = dict(
            panel_id='fmg_2025', year=2025,
            population='Originating passengers departing MUC; transfers and arrivals/egress excluded, as stated in the supplied summary.',
            outcome='FMG reported airport-access category',
            access_coding_note='Use the reported access arrangement. Off-airport parking with a shuttle remains the off-airport parking category; do not automatically classify it as bus merely because a shuttle is the final physical vehicle. Original questionnaire coding remains to be confirmed.',
            modes=[m for m, _ in MODES], mode_labels=dict(MODES),
            personas=panels,
            overall=dict(annual_passenger_volume=total, unweighted_n=None, observed=overall_rates),
            aggregation='For each purpose-by-flight-type group: sum(source annual passenger volume * source mode share) / sum(source annual passenger volume). Rounded source volumes are retained without correction.',
            interpretation='Aggregate internal-source benchmark, not passenger microdata. Raw interview counts, sampling variances and design weights are unavailable. Annual traffic volumes are aggregation weights, not interview sample sizes.',
            design='Direction and trip duration are marginalised using actual source volumes. No resident/visitor interpretation, synthetic geography-duration join, or individual passenger records are introduced.',
            source=dict(local_file=str(workbook_path), sha256=source_hash, sheet=SHEET, data_rows=list(DATA_ROWS)),
            handling='PRIVATE TARGET FILE. Source and row-level extracts remain restricted. Do not send observations, counts, weights or numerical hints to external model APIs. Publication permission for study findings must be assessed separately.',
        )
        audit = dict(
            created_utc=datetime.now(timezone.utc).isoformat(),
            source_sha256=source_hash, source_unchanged=source_unchanged,
            source_rows=len(rows), target_groups=len(panels), outcome_categories=len(MODES),
            source_mode_sums_pass=True, cached_mode_totals_pass=True,
            population_weights_sum=math.fsum(p['population_weight'] for p in panels),
            max_six_group_recombination_difference=max_recombination_error,
            source_volume_total=total, raw_interview_n_available=False,
            read_only=True, network_requests=0,
            independent_upstream_source_verified=False,
            restriction='Private audit; not for repository or API upload.',
        )
        output.mkdir(parents=True, exist_ok=True)
        save_json(output/'targets.json', target)
        save_json(output/'audit.json', audit)
        with (output/'targets_long.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            fields=('persona_id','purpose','flight_type','mode','observed_share','annual_passenger_volume','population_weight','unweighted_n','source_rows')
            writer=csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader()
            for persona in panels:
                for mode, _ in MODES:
                    writer.writerow({k:persona[k] for k in ('persona_id','purpose','flight_type','annual_passenger_volume','population_weight','unweighted_n')} | dict(mode=mode,observed_share=persona['observed'][mode],source_rows=','.join(map(str,persona['source_rows']))))
        return audit
    finally:
        book.close()
        cached.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, required=True, help='Authorised local aggregate workbook; never uploaded by this script.')
    parser.add_argument('--output', type=Path, required=True, help='Private output directory outside this repository.')
    args=parser.parse_args()
    prepare(args.workbook, args.output)
    # Avoid printing restricted source values to logs.
    print('Private benchmark extraction and source-preservation checks passed. Outputs remain in the requested private directory.')


if __name__ == '__main__':
    main()
