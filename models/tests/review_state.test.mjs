import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {root} from '../engine.mjs';

function review(){
  const html=readFileSync(`${root}index.html`,'utf8');
  const nodes=new Map();
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,{open:false,value:'',classList:{toggle(){}},close(){this.open=false;},showModal(){this.open=true;}});return nodes.get(id);},querySelectorAll(){return [];},addEventListener(){}};
  const context=vm.createContext({document,window:{},console,setTimeout,clearTimeout,performance:{now:()=>0}});
  const code=html.slice(html.indexOf('const BUNDLED_BOOK='),html.lastIndexOf('\ninit();'));
  vm.runInContext(code+`
    book=BUNDLED_BOOK;data=BUNDLED_CASE;initValuationBook();
    baseline=new WorkbookEngine(book);engine=new WorkbookEngine(book);
    renderAll=()=>{};save=()=>{};announce=()=>{};bind();
    globalThis.api={
      apply:applyValuationScenario,
      target:id=>scenarioTransaction(savedValuationScenarios().find(s=>s.id===id)),
      edit:(cell,value)=>commitProposal(proposalFor(cell).id,'edited',value),
      undo:()=>$('undo').onclick(),
      state:()=>JSON.stringify(state),
      restore:s=>{state=JSON.parse(s);rebuild();},
      value:()=>engine.value('Valuation output!B33'),
      count:()=>proposals().length,
      originalCount:()=>data.proposals.length,
      raw:()=>JSON.stringify(engine.overrides),
      field:footballField,
      roic:v=>validate(terminalRoicProposal(),v)
    };`,context,{timeout:10000});
  return context.api;
}

test('scenario application keeps original facts and explicitly persists active ROIC',()=>{
  const app=review();app.apply('base');
  assert.equal(app.originalCount(),70);assert.equal(app.count(),71);
  const state=JSON.parse(app.state()),raw=JSON.parse(app.raw());
  assert.equal(raw['Input sheet!B49'],.2);
  assert.equal(state.statuses['wdfc-Input_sheet-B22'],'accepted');
  assert.equal(state.edits['wdfc-Input_sheet-B22'],undefined);
  assert.ok(Math.abs(app.value()-159.17020951337236)<1e-8);
});

test('preview includes restored formulas and one undo restores the complete prior case',()=>{
  const app=review();app.apply('original');app.edit('Input sheet!B27',.19);
  const previous=app.state(),previousValue=app.value(),target=app.target('base');
  assert.ok(target.changes.some(row=>row.p.cell==='Input sheet!B27'&&row.restore));
  app.apply('base');app.undo();
  assert.deepEqual(JSON.parse(app.state()),JSON.parse(previous));
  assert.equal(app.value(),previousValue);
});

test('current WACC edits move current DCF while saved scenario snapshots stay fixed',()=>{
  const app=review();app.apply('base');const before=app.field();
  app.edit('Cost of capital worksheet!B12',.08);const after=app.field();
  assert.notEqual(after.current.value,before.current.value);
  assert.equal(JSON.stringify(after.scenarios),JSON.stringify(before.scenarios));
});

test('inactive ROIC is ignored; active unsustainable reinvestment is rejected',()=>{
  const app=review();app.apply('original');assert.equal(app.roic(-.1),null);
  app.apply('base');assert.match(app.roic(.01),/reinvestment/);
});

test('saved review reload preserves the supplemental ROIC and output',()=>{
  const first=review();first.apply('bull');const state=first.state();
  const second=review();second.restore(state);
  assert.equal(second.count(),71);assert.equal(second.value(),first.value());
  assert.equal(JSON.parse(second.raw())['Input sheet!B49'],.25);
});
