// Assembles BUNDLED_VALUATION from saved model outputs. No network, no clock.
// Usage: node models/build_payload.mjs  ->  models/out/valuation.json
import {readFileSync, writeFileSync, existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {join} from 'node:path';
import {ROOT} from './lib/page.mjs';

const read = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));
const S = read('models/scenarios.json');
const E = read('models/out/scenarios_eval.json');
const M = read('models/out/measure/stage1.json');
const MC = read('models/out/methods_comps.json'), MO = read('models/out/valuation_book/../methods_core.json');
const extra = {methods: [...MC.methods.filter(m => m.id === 'comps'), ...MO.methods, ...MC.methods.filter(m => m.id !== 'comps')], sources: {...MC.sources, ...MO.sources}};
const Q = read('models/questions/questions.json');
const questions = {asOf: Q.asOf, note: Q.note, topics: Q.topics, coverage: Q.coverage};
// model sheets for the Workbook tab: page cell schema, without Python-only fields except the value used for the in-browser check
const cellsAll = read('models/out/valuation_book/valuation_cells.json');
const books = {};
for (const [id, c] of Object.entries(cellsAll)) {
  const slim = {id, sheet: c.sheet, address: c.address, value: c.value, formula: c.formula, classification: c.classification, dependencies: c.dependencies, input: c.input};
  if (c.label) slim.label = c.label;
  if (c.formula && typeof c.pythonValue === 'number') slim.pythonValue = c.pythonValue;
  (books[c.sheet] ??= {})[id] = slim;
}

// 52-week range to the price date, from the saved daily file
const daily = readFileSync(join(ROOT, 'models/data/market/wdfc_daily_2024-08-01_2025-09-09.csv'), 'utf8').trim().split('\n').slice(1)
  .map(l => l.split(',')).map(([date, open, high, low, close]) => ({date, high: +high, low: +low, close: +close}))
  .filter(r => r.date > '2024-08-29' && r.date <= '2025-08-29');
const hi = daily.reduce((a, b) => b.high > a.high ? b : a), lo = daily.reduce((a, b) => b.low < a.low ? b : a);
const r2 = x => Math.round(x * 100) / 100;

const sources = {
  'price-close': {title: 'WDFC daily prices, Nasdaq (Yahoo Finance chart API)', file: 'models/data/market/wdfc_daily_2024-08-01_2025-09-09.csv', asOf: '2025-08-29'},
  'proxy-price': {title: 'WD-40 2025 proxy statement, outstanding equity awards footnote 2', url: 'https://www.sec.gov/Archives/edgar/data/105132/000010513225000107/wdfc-20251031.htm', publishedAt: '2025-10-31'},
  'target-dadavidson': {title: 'DA Davidson lowers WD-40 target to $300 from $322, Buy (Investing.com)', url: 'https://www.investing.com/news/analyst-ratings/wd40-stock-price-target-lowered-to-300-at-da-davidson-on-currency-trends-93CH-4131713', publishedAt: '2025-07-11'},
  'target-jefferies': {title: 'Jefferies raises WD-40 target to $280 from $250, Hold (The Fly via TipRanks)', url: 'https://www.tipranks.com/news/the-fly/wd-40-price-target-raised-to-280-from-250-at-jefferies', publishedAt: '2024-10-18'},
  ...Object.fromEntries(Object.entries(S.sources).map(([k, v]) => [k, v])),
  ...extra.sources,
  ...Q.sources,
};

const sc = k => {
  const r = E.results[k];
  return {label: r.label, value: r.result.value, terminalShare: r.result.terminalShare, operatingAssets: r.result.operatingAssets,
    inputSetHash: r.inputSetHash, overrides: r.overrides, rationale: r.rationale ?? [],
    year10ROIC: r.result.roic?.[9] ?? null, terminalROIC: r.result.terminalROIC, terminalWACC: r.result.terminalWACC, terminalGrowth: r.result.terminalGrowth};
};
const methods = [
  {id: 'dcf', group: 'standalone', label: 'DCF, Bear to Bull', sublabel: 'FCFF Ginzu, saved scenarios', kind: 'range',
    low: E.results.bear.result.value, base: E.results.base.result.value, high: E.results.bull.result.value,
    scenarios: {bear: sc('bear'), base: sc('base'), bull: sc('bull')},
    note: 'Each scenario is a complete set of Ginzu inputs, made of the original case plus the listed changes. Scenarios keep their values when you edit your review.',
    sourceIds: ['ust-par-2025-08-29', 'damodaran-erp-2025-09', 'damodaran-betas-2025-01', 'wdfc-8k-2025-10-22', 'sec-xbrl'], status: 'engine'},
  {id: 'dcf-original', group: 'standalone', label: 'DCF, original case', sublabel: '70 proposals as researched', kind: 'point',
    base: E.results.original.result.value, scenarios: {original: sc('original')},
    note: 'In the case as researched, WACC fades from 9% to 8%, the margin stays flat and terminal ROIC equals WACC. The case labels these inputs as illustrative placeholders.', sourceIds: [], status: 'engine'},
  ...extra.methods,
];

// Statuses come from the checks of the exact files in this build, matched by sha256.
const sha = path => createHash('sha256').update(readFileSync(join(ROOT, path))).digest('hex');
const CK = existsSync(join(ROOT, 'models/out/checks.json')) ? read('models/out/checks.json') : {};
const engineOk = !!CK.engine && CK.engine.failed === 0 && CK.engine.cellsSha256 === sha('models/out/valuation_book/valuation_cells.json');
const excelOk = engineOk && !!CK.excel && CK.excel.failed === 0 && existsSync(join(ROOT, 'models/excel/wd40_valuation.xlsx'))
  && CK.excel.publishedSha256 === sha('models/excel/wd40_valuation.xlsx') && CK.excel.cellsSha256 === CK.engine.cellsSha256;
const STATUS = {
  engine: 'Calculated by the page engine',
  python: 'Calculated in Python from filings and closing prices',
  workbook: excelOk ? 'Workbook formulas checked against Python in the page engine and in Excel' : engineOk ? 'Workbook formulas checked against Python in the page engine; Excel check not run for this build' : 'Workbook formulas not checked in this build',
};
for (const m of methods) m.statusText = STATUS[m.status] ?? m.status;
const checksOut = {
  readinessAtPayload: CK.mode === 'release' ? 'release build' : 'partial build',
  engine: CK.engine ? {checked: CK.engine.checked, failed: CK.engine.failed, matchesThisBuild: engineOk} : null,
  excel: CK.excel ? {checked: CK.excel.checked, failed: CK.excel.failed, matchesThisBuild: excelOk, workbook: CK.excel.publishedPath, sha256: CK.excel.publishedSha256} : null,
};

const payload = {
  schemaVersion: 1,
  timeBasis: {...S.timeBasis, assumptionSetVersion: S.assumptionSetVersion, priceType: 'Nasdaq unadjusted close'},
  markers: [
    {id: 'price', kind: 'point', label: 'Close 29 Aug 2025', value: S.timeBasis.price, asOf: S.timeBasis.priceDate, sourceIds: ['price-close', 'proxy-price']},
    {id: 'range52w', kind: 'range', label: '52-week range', low: r2(lo.low), high: r2(hi.high), lowDate: lo.date, highDate: hi.date, basis: 'intraday', asOf: S.timeBasis.priceDate, sourceIds: ['price-close']},
    {id: 'targets', kind: 'points', label: 'Analyst targets', asOf: S.timeBasis.priceDate, points: [
      {value: 280, label: 'Jefferies, Hold', date: '2024-10-18', sourceIds: ['target-jefferies']},
      {value: 300, label: 'DA Davidson, Buy', date: '2025-07-11', sourceIds: ['target-dadavidson']}],
      note: 'Latest published targets found for each firm on or before 29 Aug 2025. Other firms may have had targets that were not found.'},
  ],
  methods,
  reverse: {from: 'base', price: S.timeBasis.price, baseValue: E.results.base.result.value, grids: E.grids, items: E.reverseFromBase.map(r => ({id: r.id, label: r.label, baseValue: r.baseValue, status: r.status, solution: r.solution ?? null, valueAtBounds: r.valueAtBounds ?? null, range: r.range}))},
  originalCheck: {value: M.base.value, inputSetHash: M.inputSetHash},
  sensitivities: {base: 'original case', value: M.base.value, groups: M.groups.map(g => ({title: g.title, probes: g.probes.map(p => ({label: p.label, changes: p.changes, value: p.result.value ?? null, delta: p.delta, terminalShare: p.result.terminalShare ?? null, status: p.result.status, reason: p.result.reason ?? null}))})),
    joint: M.joint.map(j => ({id: j.id, label: j.label, value: j.result.value, terminalShare: j.result.terminalShare})), ladders: M.ladders},
  notChanged: S.notChanged,
  newProposals: [
    {id: 'v2-Input_sheet-B49', cell: 'Input sheet!B49', label: 'Terminal return on new capital (used only when the override is Yes)', value: 0.15,
      unit: 'percentage_decimal', type: 'percentage_decimal', kind: 'assumption', status: 'proposed', defaultStatus: 'accepted', sourceIds: [],
      rationale: 'Workbook default. It has no effect while "Terminal excess-return override" is No. The Base scenario turns the override on and uses 15%.',
      period: 'Forward scenario assumption', agent: 'stage2', caveats: ['Added with the valuation range. Kept at the workbook value until you change it.']},
  ],
  books,
  checks: {eva: MO.eva, ...checksOut},
  questions,
  sources,
};
writeFileSync(join(ROOT, 'models/out/valuation.json'), JSON.stringify(payload));
console.log('methods', methods.map(m => `${m.id} ${m.low ?? ''} ${m.base} ${m.high ?? ''}`).join(' | '), '\n52w', lo.low, lo.date, hi.high, hi.date);
