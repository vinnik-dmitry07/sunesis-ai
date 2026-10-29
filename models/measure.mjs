import {mkdirSync,writeFileSync} from 'node:fs';
import {loadOriginal,evaluate,solveWaccShift,root} from './engine.mjs';

const {book,data,WorkbookEngine,overrides,inputHash,sourceModelHash}=loadOriginal();
const engine=new WorkbookEngine(book);
const original=evaluate(engine,overrides);
const probes=[
  ['wacc-down-100bp','WACC path −100 bp',{'Cost of capital worksheet!B12':overrides['Cost of capital worksheet!B12']-.01,'Input sheet!B46':overrides['Input sheet!B46']-.01}],
  ['wacc-up-100bp','WACC path +100 bp',{'Cost of capital worksheet!B12':overrides['Cost of capital worksheet!B12']+.01,'Input sheet!B46':overrides['Input sheet!B46']+.01}],
  ['roic-20','Terminal ROIC 20%',{'Input sheet!B48':'Yes','Input sheet!B49':.2}],
  ['margin-20','Target adjusted EBIT margin 20%',{'Input sheet!B29':.2}],
  ['growth-7','Years 2–5 growth 7%',{'Input sheet!B28':.07}],
  ['combined','Combined diagnostic: 7% flat WACC, ROIC 20%, growth 7%, margin 20%',{'Cost of capital worksheet!B12':.07,'Input sheet!B46':.07,'Input sheet!B48':'Yes','Input sheet!B49':.2,'Input sheet!B28':.07,'Input sheet!B29':.2}],
];
const sensitivities=probes.map(([id,label,changes])=>({id,label,changes,...evaluate(engine,{...overrides,...changes})})).map(({rows,...probe})=>({...probe,delta:probe.value-original.value}));
const reference={price:overrides['Input sheet!B22'],priceAsOf:'2025-08-29',financialPeriod:'FY2025',basis:'Retrospective FY2025; filings published after the reference price.',valuationShareCount:overrides['Input sheet!B21'],shareCountDefinition:data.proposals.find(p=>p.cell==='Input sheet!B21')?.label};
const report={schemaVersion:'1.0',inputHash,sourceModelHash,reference,original,sensitivities,reverse:solveWaccShift(engine,overrides,reference.price),proposals:data.proposals.map(p=>({id:p.id,cell:p.cell,value:p.value,operation:p.operation??'override',sourceIds:p.sourceIds??[]})),knownLimits:['Original published-result claim is verified against the repository engine only at this stage.','No fresh Excel recalculation has been performed.','Sensitivities are conditional and are not an additive attribution of the price gap.']};
mkdirSync(`${root}models/out`,{recursive:true});
writeFileSync(`${root}models/out/measurement.json`,`${JSON.stringify(report,null,2)}\n`);
writeFileSync(`${root}models/out/original-inputs.json`,`${JSON.stringify({inputHash,overrides},null,2)}\n`);
console.log(JSON.stringify({original:original.value,inputHash,reference,sensitivities:sensitivities.map(({id,value,delta})=>({id,value,delta})),reverse:report.reverse},null,2));
