// Review behaviour of the page itself: the page script runs in a VM with a stub DOM and an in-memory localStorage.
// Covers applying a saved scenario, one-step undo, the stale-value guard, reload from storage and the live reverse
// solve. A real browser reload is checked separately in the browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import vm from 'node:vm';
import {ROOT} from '../lib/page.mjs';

const HTML = readFileSync(join(ROOT, 'index.html'), 'utf8');
const start = HTML.indexOf('<script type="module">') + '<script type="module">'.length;
const SRC = HTML.slice(start, HTML.lastIndexOf('\ninit();'));

function element() {
  const store = {classList: {add() {}, remove() {}, toggle() {}, contains: () => false}, style: {}, dataset: {}};
  const self = new Proxy(function () {}, {
    get(_, k) {
      if (k in store) return store[k];
      if (k === 'querySelectorAll' || k === 'getElementsByTagName') return () => [];
      if (k === 'querySelector' || k === 'closest') return () => null;
      if (k === 'getBoundingClientRect') return () => ({width: 1000, height: 400, left: 0, top: 0, right: 1000, bottom: 400});
      if (['clientWidth', 'offsetWidth', 'scrollWidth'].includes(k)) return 1000;
      if (['value', 'textContent', 'innerHTML', 'innerText'].includes(k)) return '';
      if (k === Symbol.toPrimitive) return () => '';
      if (k === 'then' || typeof k === 'symbol') return undefined;
      return () => self;
    },
    set(_, k, v) { store[k] = v; return true; },
  });
  return self;
}

function page(storage = new Map(), patch = '') {
  const nodes = new Map();
  const document = {getElementById: id => nodes.get(id) ?? nodes.set(id, element()).get(id), querySelectorAll: () => [], querySelector: () => null,
    addEventListener() {}, createElement: () => element(), body: element(), documentElement: element()};
  const localStorage = {getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, String(v)), removeItem: k => storage.delete(k)};
  const ctx = {document, localStorage, console, setTimeout, clearTimeout, performance: {now: () => 0}, requestAnimationFrame: f => f(),
    matchMedia: () => ({matches: false, addEventListener() {}}), getComputedStyle: () => ({}), navigator: {clipboard: {}}, location: {hash: ''}, history: {}, addEventListener() {}, removeEventListener() {}};
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(`${SRC}\n${patch}\ninit();
    globalThis.api={
      acceptAll:()=>{acceptRemaining();$('confirm-accept').onclick?.();},
      openApply:k=>applyScenarioDialog(k),
      confirm:()=>$('confirm-scenario').onclick(),
      undo:()=>$('undo').onclick(),
      edit:(cell,v)=>{const p=proposalFor(cell);commitProposal(p.id,'edited',v);},
      state:()=>JSON.stringify({statuses:state.statuses,edits:state.edits}),
      overrides:()=>JSON.stringify(engine.overrides),
      value:()=>engine.value('Valuation output!B33'),
      count:()=>proposals().length,
      saved:k=>VAL.methods.find(m=>m.id==='dcf').scenarios[k].value,
      validate:(cell,v)=>validate(proposalFor(cell),v),
      solve:()=>solveLive(),
      failed:()=>$('company-name').textContent==='Unable to load the model',
    };`, ctx, {timeout: 60000});
  return {api: ctx.api, nodes, storage};
}

const html = (nodes, id) => String(nodes.get(id)?.innerHTML ?? '');
const near = (a, b, tol = 1e-8) => assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${a} != ${b}`);

test('the original case gives $88.15029580134913 once every proposal is accepted', () => {
  const {api} = page();
  assert.equal(api.failed(), false);
  api.acceptAll();
  near(api.value(), 88.15029580134913, 1e-12);
  assert.equal(api.count(), 71);
});

test('applying Base from the original review reproduces the saved Base value, and one undo restores the review', () => {
  const {api, nodes} = page();
  api.acceptAll();
  api.edit('Input sheet!B27', 0.19);
  const before = api.state(), beforeValue = api.value();
  api.openApply('base');
  assert.match(html(nodes, 'dialog-content'), /Apply \d+ change/);
  api.confirm();
  assert.notEqual(api.state(), before);
  api.undo();
  assert.equal(api.state(), before);
  assert.equal(api.value(), beforeValue);
  api.undo();
  api.acceptAll();
  api.openApply('base');
  api.confirm();
  near(api.value(), api.saved('base'));
});

test('a saved value that no longer matches its inputs is not applied', () => {
  const {api, nodes} = page(new Map(), "VAL.methods.find(m=>m.id==='dcf').scenarios.base.value+=1;");
  api.acceptAll();
  const before = api.state();
  api.openApply('base');
  assert.match(html(nodes, 'dialog-content'), /does not match a fresh recalculation/);
  assert.match(html(nodes, 'dialog-content'), /disabled/);
  assert.equal(api.state(), before);
});

test('editing the review moves the current value but not the saved scenarios', () => {
  const {api} = page();
  api.acceptAll();
  const saved = ['bear', 'base', 'bull'].map(api.saved), v0 = api.value();
  api.edit('Cost of capital worksheet!B12', 0.08);
  assert.notEqual(api.value(), v0);
  assert.deepEqual(['bear', 'base', 'bull'].map(api.saved), saved);
});

test('a saved review survives a reload from storage', () => {
  const first = page();
  first.api.acceptAll();
  first.api.openApply('bull');
  first.api.confirm();
  const second = page(first.storage);
  assert.equal(second.api.state(), first.api.state());
  assert.equal(second.api.value(), first.api.value());
  assert.equal(second.api.count(), 71);
});

test('the live reverse solve meets the price within $0.01 and leaves the review untouched', () => {
  const {api} = page();
  api.acceptAll();
  api.openApply('base');
  api.confirm();
  const state = api.state(), overrides = api.overrides();
  const r = api.solve();
  assert.equal(r.status, 'solved');
  assert.ok(Math.abs(r.residual) <= 0.01);
  assert.match(r.basis, /your review/);
  assert.equal(api.state(), state);
  assert.equal(api.overrides(), overrides);
});

test('a terminal return below terminal growth is allowed while the override is off and rejected once it is on', () => {
  const {api} = page();
  api.acceptAll();
  assert.equal(api.validate('Input sheet!B49', 0.02), null);
  api.openApply('base');
  api.confirm();
  assert.match(api.validate('Input sheet!B49', 0.02), /greater than terminal growth/);
});
