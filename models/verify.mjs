import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {loadOriginal,evaluate,root} from './engine.mjs';

const payload=JSON.parse(readFileSync(`${root}models/out/valuation.json`,'utf8'));
const exported=JSON.parse(readFileSync(`${root}models/out/export-report.json`,'utf8'));
assert.equal(exported.buildFingerprint,payload.buildFingerprint,'Workbook and page must have the same build fingerprint.');
assert.equal(payload.checks.workbookCurrent,true,'Only a matching workbook may be offered for download.');
assert.equal(createHash('sha256').update(Buffer.from(payload.workbookBase64,'base64')).digest('hex'),exported.workbookSha256,'The standalone download must match the formula workbook.');
const {book,WorkbookEngine,data,overrides}=loadOriginal();
assert.equal(data.proposals.length,70,'The original proposal set must remain intact.');
const original=evaluate(new WorkbookEngine(book),overrides);
assert.ok(Math.abs(original.value-payload.original.value)<1e-8);
for(const pageBook of payload.books)Object.assign(book.cells,pageBook.cells);
const engine=new WorkbookEngine(book),failures=[];
let checked=0;
const expected=exported.expectedValues;
for(const [id,value] of Object.entries(expected)){
  const cell=book.cells[id];if(!cell?.formula)continue;
  const actual=engine.safe(id);checked++;
  if(actual.error||typeof value==='number'&&Math.abs(actual.value-value)>1e-8+1e-9*Math.max(Math.abs(value),Math.abs(actual.value))||typeof value!=='number'&&actual.value!==value)failures.push({id,expected:value,...actual});
}
for(const scenario of payload.scenarios){
  const actual=evaluate(engine,scenario.overrides).value;
  if(Math.abs(actual-scenario.value)>1e-8)failures.push({scenario:scenario.id,expected:scenario.value,actual});
}
assert.ok(checked>0,'There must be live exported formulas to verify.');
const result={buildFingerprint:payload.buildFingerprint,status:failures.length?'failed':'passed',formulaCells:checked,scenarioCount:payload.scenarios.length,originalValue:original.value,failures,nativeExcelRecalculated:false};
writeFileSync(`${root}models/out/verification.json`,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
assert.equal(failures.length,0,'Emitted formulas must match their Python results.');
