import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const previewOnly=process.argv.includes('--preview-only');
const amendLabels=process.argv.includes('--amend-labels');
if(previewOnly && amendLabels) throw new Error('Choose preview-only or amend-labels, not both.');
const spec=previewOnly ? {source:path.join(root,'data/workbooks/MiD2023_Comprehensive_Data_and_LLM_EN.xlsx')} : JSON.parse(await fs.readFile(path.join(root,'data/processed/sequential_workbook_inputs.json'),'utf8'));
if(!previewOnly && createHash('sha256').update(await fs.readFile(spec.source)).digest('hex')!==spec.source_sha256) throw new Error('Source workbook fingerprint changed');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(amendLabels ? spec.output : spec.source));
const previews=path.join(root,'outputs/sequential_workbook_previews');
await fs.mkdir(previews,{recursive:true});
const inventory=await wb.inspect({kind:'sheet',include:'id,name',maxChars:7000});
await fs.writeFile(path.join(previews,'source_inventory.ndjson'),inventory.ndjson);
const before=await wb.render({sheetName:'LLM predictions',range:'A1:H10',scale:1,format:'png'});
await fs.writeFile(path.join(previews,'source_style.png'),new Uint8Array(await before.arrayBuffer()));
if(previewOnly) process.exit(0);
if(amendLabels){
  const resultsSpec=spec.sheets.find(x=>x.name==='32_Sequential_results');
  const airportSpec=spec.sheets.find(x=>x.name==='34_MUC_new_predictions');
  const resultsSheet=wb.worksheets.getItem(resultsSpec.name);
  const targetTable=resultsSheet.tables.items.find(t=>t.name==='SequentialTable1');
  if(!targetTable) throw new Error('The existing results table is missing.');
  // Header-range edits alone leave imported table-column metadata stale.
  // Recreate only this table object over the same cells using the public API.
  const tableSettings={name:targetTable.name,style:targetTable.style,
    showHeaders:targetTable.showHeaders,showTotals:targetTable.showTotals,
    showBandedColumns:targetTable.showBandedColumns,showFilterButton:targetTable.showFilterButton};
  targetTable.getHeaderRowRange().values=[resultsSpec.headers];
  targetTable.delete();
  const updatedTable=resultsSheet.tables.add(`A5:O${resultsSpec.rows.length+5}`,true,tableSettings.name);
  updatedTable.style=tableSettings.style;
  updatedTable.showHeaders=tableSettings.showHeaders;
  updatedTable.showTotals=tableSettings.showTotals;
  updatedTable.showBandedColumns=tableSettings.showBandedColumns;
  updatedTable.showFilterButton=tableSettings.showFilterButton;
  wb.worksheets.getItem(airportSpec.name).getRange('A2').values=[[airportSpec.note]];
  wb.recalculate();
  for(const entry of spec.sheets){
    const rendered=await wb.render({sheetName:entry.name,range:entry.preview,scale:1,format:'png'});
    await fs.writeFile(path.join(previews,entry.name+'.png'),new Uint8Array(await rendered.arrayBuffer()));
  }
  const headerPreview=await wb.render({sheetName:resultsSpec.name,range:'L5:O10',scale:1,format:'png'});
  await fs.writeFile(path.join(previews,'32_Sequential_results_header.png'),new Uint8Array(await headerPreview.arrayBuffer()));
  const inspected=await wb.inspect({kind:'table',range:"'32_Sequential_results'!L5:O7",include:'values,formulas',tableMaxRows:3,tableMaxCols:4,maxChars:1500});
  await fs.writeFile(path.join(previews,'amended_header.inspect.ndjson'),inspected.ndjson);
  await(await SpreadsheetFile.exportXlsx(wb)).save(spec.output);
  console.log(`Amended only the results header and Munich population note: ${spec.output}`);
  process.exit(0);
}
const col=i=>{let s='';for(let n=i+1;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
for(const [index,entry] of spec.sheets.entries()){
  const sheet=wb.worksheets.add(entry.name),last=col(entry.headers.length-1),end=entry.rows.length+5;
  sheet.showGridLines=false;
  sheet.getRange(`A1:${last}${end}`).format={font:{name:'Arial',size:11,color:'#17364A'},verticalAlignment:'center'};
  sheet.mergeCells('A1:H1');sheet.getRange('A1').values=[[entry.name.replace(/^\d+_/,'').replaceAll('_',' ')]];
  sheet.getRange('A1:H1').format={fill:'#193C55',font:{name:'Arial',size:17,bold:true,color:'#FFFFFF'},rowHeight:34};
  for(const [row,value,fill,height] of [[2,entry.note,'#E7F1F5',46],[3,entry.source,'#F3F6FA',36]]){
    sheet.mergeCells(`A${row}:H${row}`);sheet.getRange(`A${row}`).values=[[value]];
    sheet.getRange(`A${row}:H${row}`).format={fill,font:{name:'Arial',size:10,color:'#435B72'},wrapText:true,rowHeight:height};
  }
  sheet.getRange('A4').format.rowHeight=10;
  sheet.getRange(`A5:${last}5`).values=[entry.headers];
  sheet.getRange(`A6:${last}${end}`).values=entry.rows;
  for(const [column,formula] of Object.entries(entry.formulas))
    sheet.getRange(`${column}6:${column}${end}`).formulas=entry.rows.map((_,i)=>[formula.replaceAll('{r}',String(i+6))]);
  const table=sheet.tables.add(`A5:${last}${end}`,true,'SequentialTable'+(index+1));
  table.style='TableStyleMedium2';table.showFilterButton=true;
  sheet.getRange(`A5:${last}5`).format={fill:'#0C7D87',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',rowHeight:48};
  sheet.getRange(`A6:${last}${end}`).format={rowHeight:36,wrapText:true};
  entry.widths.forEach((width,i)=>{sheet.getRange(`${col(i)}1:${col(i)}${end}`).format.columnWidth=width;});
  for(const [column,format] of Object.entries(entry.formats)){
    sheet.getRange(`${column}6:${column}${end}`).setNumberFormat(format);
    sheet.getRange(`${column}6:${column}${end}`).format.horizontalAlignment='right';
  }
  sheet.freezePanes.freezeRows(5);
  console.log(`${entry.name}: ${entry.rows.length} rows`);
}
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:3000});
await fs.writeFile(path.join(previews,'formula_error_scan.json'),JSON.stringify(errors,null,2));
for(const entry of spec.sheets){
  const rendered=await wb.render({sheetName:entry.name,range:entry.preview,scale:1,format:'png'});
  await fs.writeFile(path.join(previews,entry.name+'.png'),new Uint8Array(await rendered.arrayBuffer()));
  const inspected=await wb.inspect({kind:'table',range:`'${entry.name}'!A5:H9`,include:'values,formulas',tableMaxRows:5,tableMaxCols:8,maxChars:4000});
  await fs.writeFile(path.join(previews,entry.name+'.inspect.ndjson'),inspected.ndjson);
}
await(await SpreadsheetFile.exportXlsx(wb)).save(spec.output);
console.log(`Exported ${spec.output}`);
