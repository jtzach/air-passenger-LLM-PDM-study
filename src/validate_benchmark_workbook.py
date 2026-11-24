"""Read-only all-cell and native-feature preservation checks after artifact export."""
import hashlib
import json
import math
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from copy import copy
from datetime import datetime, timezone
from pathlib import Path
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]


def equal(a,b):
    if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        return math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-13)
    return type(a)==type(b) and a==b


def main():
    source=ROOT/'data/workbooks/MiD2023_Comprehensive_Data_EN.xlsx'
    target=ROOT/'data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx'
    inputs=json.loads((ROOT/'data/processed/workbook_appendix_inputs.json').read_text(encoding='utf8'))
    a=load_workbook(source,data_only=False); b=load_workbook(target,data_only=False)
    counts=Counter(); issues=[]; style_pairs=set(); formula_cells=[]
    def report(kind,**details):
        issues.append({'kind':kind,**details})
    if b.sheetnames!=a.sheetnames+[s['name'] for s in inputs['sheets']]:
        report('sheet_order_or_names')
    for old in a:
        new=b[old.title]
        if str(old.freeze_panes)!=str(new.freeze_panes): report('freeze_panes',sheet=old.title)
        if old.sheet_view.showGridLines!=new.sheet_view.showGridLines: report('gridlines',sheet=old.title)
        if old.sheet_state!=new.sheet_state: report('sheet_state',sheet=old.title)
        if sorted(map(str,old.merged_cells.ranges))!=sorted(map(str,new.merged_cells.ranges)): report('merged_ranges',sheet=old.title)
        if set(old.tables)!=set(new.tables): report('table_names',sheet=old.title)
        for name in old.tables:
            x=old.tables[name];y=new.tables.get(name)
            if y is None: continue
            if x.ref!=y.ref: report('table_range',sheet=old.title,table=name)
            if [c.name for c in x.tableColumns]!=[c.name for c in y.tableColumns]: report('table_headers',sheet=old.title,table=name)
            counts['preserved_tables']+=1
        if len(old.conditional_formatting)!=len(new.conditional_formatting):report('conditional_formatting',sheet=old.title)
        if len(old.data_validations.dataValidation)!=len(new.data_validations.dataValidation):report('data_validations',sheet=old.title)
        if len(old._charts)!=len(new._charts) or len(old._images)!=len(new._images):report('drawings',sheet=old.title)
        for row in old:
            for x in row:
                y=new[x.coordinate]
                if not equal(x.value,y.value):report('original_cell_changed',sheet=old.title,cell=x.coordinate,expected=x.value,actual=y.value)
                counts['original_cells_checked']+=1
                if isinstance(x.value,(int,float)) and not isinstance(x.value,bool):counts['original_numeric_cells_preserved']+=1
                if x.data_type=='f':
                    counts['original_formulas_preserved']+=1
                    formula_cells.append((a.sheetnames.index(old.title)+1,x.coordinate))
                if x.value is None:continue
                if x.data_type!=y.data_type:report('original_cell_type_changed',sheet=old.title,cell=x.coordinate,expected=x.data_type,actual=y.data_type)
                pair=(x.style_id,y.style_id)
                if pair not in style_pairs:
                    style_pairs.add(pair)
                    for attr in ['font','fill','border','alignment','number_format','protection']:
                        if copy(getattr(x,attr))!=copy(getattr(y,attr)):report('original_style_changed',sheet=old.title,cell=x.coordinate,attribute=attr)
                if x.hyperlink!=y.hyperlink:report('hyperlink_changed',sheet=old.title,cell=x.coordinate)
        for key,x in old.column_dimensions.items():
            y=new.column_dimensions[key]
            if x.width is not None and y.width is not None and not math.isclose(x.width,y.width,abs_tol=.001):report('column_width_changed',sheet=old.title,column=key)
            if x.hidden!=y.hidden:report('column_hidden_changed',sheet=old.title,column=key)
        for key,x in old.row_dimensions.items():
            y=new.row_dimensions[key]
            if x.height!=y.height or x.hidden!=y.hidden:report('row_dimensions_changed',sheet=old.title,row=key)
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(source) as za, zipfile.ZipFile(target) as zb:
        for si,coord in formula_cells:
            values=[]
            for archive in [za,zb]:
                xml=ET.fromstring(archive.read(f'xl/worksheets/sheet{si}.xml'))
                cell=xml.find(f'.//m:c[@r="{coord}"]/m:v',ns)
                value=cell.text if cell is not None else None
                try:value=float(value) if value is not None else None
                except ValueError:pass
                values.append(value)
            if not equal(*values):report('formula_cache_changed',sheet=a.sheetnames[si-1],cell=coord,expected=values[0],actual=values[1])
            counts['formula_caches_preserved']+=1
    for spec in inputs['sheets']:
        sheet=b[spec['name']]
        for ri,row in enumerate([spec['headers']]+spec['rows'],5):
            for ci,expected in enumerate(row,1):
                cell=sheet.cell(ri,ci)
                if not equal(expected,cell.value):report('appendix_value',sheet=sheet.title,cell=cell.coordinate,expected=expected,actual=cell.value)
                if cell.data_type=='e':report('appendix_excel_error',sheet=sheet.title,cell=cell.coordinate)
                counts['appendix_cells_checked']+=1
        if spec.get('extra_table'):
            extra=spec['extra_table']
            for ri,row in enumerate([extra['headers']]+extra['rows'],len(spec['rows'])+9):
                for ci,expected in enumerate(row,1):
                    cell=sheet.cell(ri,ci)
                    if not equal(expected,cell.value):report('availability_value',sheet=sheet.title,cell=cell.coordinate)
                    counts['appendix_cells_checked']+=1
        counts['appendix_tables']+=len(sheet.tables)
    result={'status':'pass' if not issues else 'fail','checked_utc':datetime.now(timezone.utc).isoformat(),
            'sheets_preserved':len(a.sheetnames),'sheets_total':len(b.sheetnames),'checks':dict(counts),
            'issues':issues,'issue_count':len(issues),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    out=ROOT/'results/workbook_validation.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='issues'}))
    if issues:print(json.dumps(issues[:12],ensure_ascii=True,default=str))
    raise SystemExit(bool(issues))


if __name__=='__main__':
    main()
