"""Read-only preservation and independent arithmetic checks for the new workbook."""
from collections import Counter
from copy import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter
from validate_benchmark_workbook import equal

ROOT = Path(__file__).resolve().parents[1]


def main():
    payload = json.loads((ROOT/'data/processed/sequential_workbook_inputs.json').read_text(encoding='utf8'))
    source, target = Path(payload['source']), Path(payload['output'])
    before, after = load_workbook(source), load_workbook(target)
    before_values, after_values = load_workbook(source, data_only=True), load_workbook(target, data_only=True)
    counts, issues, styles = Counter(), [], set()
    def check(ok, kind, **detail):
        if not ok:
            issues.append({'kind':kind, **detail})
    check(after.sheetnames == before.sheetnames+[s['name'] for s in payload['sheets']], 'sheet_inventory')
    for old in before:
        new = after[old.title]
        for attr in ['freeze_panes','sheet_state']:
            check(getattr(old,attr) == getattr(new,attr), attr, sheet=old.title)
        check(old.sheet_view.showGridLines == new.sheet_view.showGridLines, 'gridlines', sheet=old.title)
        check(sorted(map(str,old.merged_cells.ranges)) == sorted(map(str,new.merged_cells.ranges)), 'merges', sheet=old.title)
        check(set(old.tables) == set(new.tables), 'table_inventory', sheet=old.title)
        for name in old.tables:
            table = new.tables.get(name)
            check(table is not None and table.ref == old.tables[name].ref, 'table_range', sheet=old.title, table=name)
            if table is not None:
                check([c.name for c in table.tableColumns] == [c.name for c in old.tables[name].tableColumns], 'table_headers', sheet=old.title, table=name)
            counts['preserved_tables'] += 1
        for attr in ['conditional_formatting','data_validations']:
            left = getattr(old,attr); right = getattr(new,attr)
            check(len(left) == len(right), attr, sheet=old.title)
        check(len(old._charts) == len(new._charts) and len(old._images) == len(new._images), 'drawings', sheet=old.title)
        for row in old:
            for cell in row:
                other = new[cell.coordinate]
                check(equal(cell.value,other.value), 'original_value', sheet=old.title, cell=cell.coordinate)
                counts['original_cells_checked'] += 1
                if cell.value is None:
                    continue
                counts['original_nonempty_cells'] += 1
                check(cell.data_type == other.data_type, 'original_type', sheet=old.title, cell=cell.coordinate)
                check(cell.hyperlink == other.hyperlink, 'hyperlink', sheet=old.title, cell=cell.coordinate)
                pair = (cell.style_id, other.style_id)
                if pair not in styles:
                    styles.add(pair)
                    for attr in ['font','fill','border','alignment','number_format','protection']:
                        check(copy(getattr(cell,attr)) == copy(getattr(other,attr)), 'original_style', sheet=old.title, cell=cell.coordinate, attribute=attr)
                if cell.data_type == 'f':
                    check(equal(before_values[old.title][cell.coordinate].value, after_values[old.title][cell.coordinate].value), 'original_formula_cache', sheet=old.title, cell=cell.coordinate)
                    counts['original_formula_caches'] += 1
        for key,dim in old.column_dimensions.items():
            other = new.column_dimensions[key]
            check(abs(dim.width-other.width)<.001 and dim.hidden == other.hidden, 'column_dimension', sheet=old.title, column=key)
        for key,dim in old.row_dimensions.items():
            other = new.row_dimensions[key]
            check(dim.height == other.height and dim.hidden == other.hidden, 'row_dimension', sheet=old.title, row=key)
    for spec in payload['sheets']:
        sheet, cached = after[spec['name']], after_values[spec['name']]
        check(sheet.freeze_panes == 'A6', 'new_freeze', sheet=sheet.title)
        check(len(sheet.tables) == 1, 'new_table', sheet=sheet.title)
        check(sheet['A2'].value == spec['note'], 'new_note', sheet=sheet.title)
        check(sheet['A3'].value == spec['source'], 'new_source', sheet=sheet.title)
        if len(sheet.tables) == 1:
            table = next(iter(sheet.tables.values()))
            expected_ref = f"A5:{get_column_letter(len(spec['headers']))}{len(spec['rows'])+5}"
            check(table.ref == expected_ref, 'new_table_range', sheet=sheet.title)
            check([c.name for c in table.tableColumns] == spec['headers'], 'new_table_headers', sheet=sheet.title)
        for ri,row in enumerate([spec['headers']]+spec['rows'],5):
            for ci,value in enumerate(row,1):
                cell = sheet.cell(ri,ci)
                expected = spec['formulas'].get(cell.column_letter) if ri >= 6 else None
                expected = expected.replace('{r}',str(ri)) if expected else value
                check(equal(expected,cell.value), 'new_cell', sheet=sheet.title, cell=cell.coordinate)
                check(cell.data_type != 'e' and cached[cell.coordinate].data_type != 'e', 'excel_error', sheet=sheet.title, cell=cell.coordinate)
                counts['new_cells_checked'] += 1
        for column in spec['formulas']:
            for ri,row in enumerate(spec['rows'],6):
                ci = column_index_from_string(column)
                expected = (100*(row[5]-row[4]) if column == 'G' else abs(100*(row[5]-row[4]))) if sheet.title.endswith('predictions') else sum(row[2:12])
                value = cached.cell(ri,ci).value
                check(isinstance(value,(int,float)) and abs(value-expected)<1e-10, 'new_formula_cache', sheet=sheet.title, cell=cached.cell(ri,ci).coordinate, expected=expected, actual=value)
                counts['new_formulas_checked'] += 1
        counts['new_tables'] += 1
    result = {'status':'PASS' if not issues else 'FAIL','checked_utc':datetime.now(timezone.utc).isoformat(),
        'original_sheets':len(before.sheetnames),'total_sheets':len(after.sheetnames),'checks':dict(counts),
        'issue_count':len(issues),'issues':issues,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (ROOT/'results/sequential_workbook_validation.json').write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='issues'}))
    if issues:
        print(json.dumps(issues[:10],default=str))
    raise SystemExit(bool(issues))


if __name__ == '__main__':
    main()
