import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const input=JSON.parse(await fs.readFile(path.join(root,'data/processed/workbook_appendix_inputs.json'),'utf8'));
const digest=createHash('sha256').update(await fs.readFile(input.source)).digest('hex');
if(digest!==input.source_sha256)throw new Error('Source workbook changed after appendix preparation');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(input.source));
const before=await wb.inspect({kind:'sheet',include:'id,name',maxChars:7000});
const previewDir=path.join(root,'outputs/workbook_previews');
await fs.mkdir(previewDir,{recursive:true});
await fs.writeFile(path.join(previewDir,'source_sheet_inventory.ndjson'),before.ndjson);
const col=i=>{let s='';for(let n=i+1;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const added=[];
for(const spec of input.sheets){
  const s=wb.worksheets.add(spec.name),last=col(spec.headers.length-1),end=spec.rows.length+5;
  added.push(spec.name);
  s.showGridLines=false;
  s.getRange(`A1:${last}${end}`).format.font={name:'Arial',size:11,color:'#17364A'};
  s.getRange(`A1:${last}${end}`).format.verticalAlignment='center';
  // Opening bands match the supplied 27-sheet research workbook.
  s.mergeCells('A1:H1');s.getRange('A1').values=[[spec.name]];
  s.getRange('A1:H1').format={fill:'#193C55',font:{name:'Arial',size:17,bold:true,color:'#FFFFFF'},rowHeight:34};
  s.mergeCells('A2:H2');s.getRange('A2').values=[[spec.note]];
  s.getRange('A2:H2').format={fill:'#E7F1F5',font:{name:'Arial',size:11,color:'#17364A'},wrapText:true,rowHeight:42};
  s.mergeCells('A3:H3');s.getRange('A3').values=[[spec.source]];
  s.getRange('A3:H3').format={fill:'#F3F6FA',font:{name:'Arial',size:10,color:'#435B72'},wrapText:true,rowHeight:38};
  s.getRange('A4').format.rowHeight=10;
  s.getRange(`A5:${last}5`).values=[spec.headers];
  s.getRange(`A6:${last}${end}`).values=spec.rows;
  const table=s.tables.add(`A5:${last}${end}`,true,'BenchmarkTable'+added.length);
  table.style='TableStyleMedium2';table.showFilterButton=true;
  s.getRange(`A5:${last}5`).format={fill:'#0C7D87',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',rowHeight:48};
  s.getRange(`A6:${last}${end}`).format.rowHeight=35;
  s.getRange(`A6:${last}${end}`).format.wrapText=true;
  for(let i=0;i<spec.widths.length;i++)s.getRange(`${col(i)}1:${col(i)}${end}`).format.columnWidth=spec.widths[i];
  for(const [c,fmt] of Object.entries(spec.formats)){
    s.getRange(`${c}6:${c}${end}`).setNumberFormat(fmt);
    s.getRange(`${c}6:${c}${end}`).format.horizontalAlignment='right';
  }
  if(spec.extra_table){
    const extra=spec.extra_table,top=end+4,extraLast=col(extra.headers.length-1),bottom=top+extra.rows.length;
    s.getRange(`A${top-1}`).values=[[extra.title]];
    s.getRange(`A${top-1}`).format.font={name:'Arial',size:13,bold:true,color:'#193C55'};
    s.getRange(`A${top}:${extraLast}${bottom}`).values=[extra.headers,...extra.rows];
    s.tables.add(`A${top}:${extraLast}${bottom}`,true,'BenchmarkAvailability').style='TableStyleMedium2';
    s.getRange(`A${top}:${extraLast}${bottom}`).format={font:{name:'Arial',size:11,color:'#17364A'},rowHeight:32,wrapText:true,verticalAlignment:'center'};
    s.getRange(`A${top}:${extraLast}${top}`).format={fill:'#0C7D87',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center'};
    s.getRange(`B${top+1}:E${bottom}`).setNumberFormat('#,##0');
  }
  s.freezePanes.freezeRows(5);
  console.log(`Appended ${spec.name}: ${spec.rows.length} rows`);
}
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:2500});
await fs.writeFile(path.join(previewDir,'formula_error_scan.json'),JSON.stringify(errors,null,2));
for(const spec of input.sheets){
  const inspection=await wb.inspect({kind:'table',range:`'${spec.name}'!A5:H9`,include:'values,formulas',tableMaxRows:5,tableMaxCols:8,maxChars:3000});
  await fs.writeFile(path.join(previewDir,spec.name.replaceAll(' ','_')+'.inspect.ndjson'),inspection.ndjson);
  const preview=await wb.render({sheetName:spec.name,range:spec.preview,scale:1,format:'png'});
  await fs.writeFile(path.join(previewDir,spec.name.replaceAll(' ','_')+'.png'),new Uint8Array(await preview.arrayBuffer()));
  if(spec.extra_table){
    const start=spec.rows.length+8,end=start+spec.extra_table.rows.length+1;
    const extraPreview=await wb.render({sheetName:spec.name,range:`A${start}:H${end}`,scale:1,format:'png'});
    await fs.writeFile(path.join(previewDir,'Model_call_availability.png'),new Uint8Array(await extraPreview.arrayBuffer()));
  }
}
const output=path.join(root,'data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
console.log(`Exported ${output}`);
