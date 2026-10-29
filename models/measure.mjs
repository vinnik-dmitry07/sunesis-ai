// Stage 1 measurements with the page's own engine.
// Usage: node models/measure.mjs
// Writes models/snapshots/*.json, models/out/measure/stage1.json, reports/01-baseline-and-sensitivities.md
import {writeFileSync, mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {execSync} from 'node:child_process';
import {loadPage, originalOverrides, stableHash, ROOT} from './lib/page.mjs';

const P = await loadPage();
const ORIGINAL = originalOverrides(P.data);
const retained = P.data.proposals.filter(p => p.operation === 'retain_formula').map(p => p.cell);
const engine = new P.WorkbookEngine(P.book, ORIGINAL);
const V = 'Valuation output!';
const PRICE = 216.04, PRICE_DATE = '2025-08-29';
const COMMON_SHARES = 13.527614; // point-in-time common shares, from the rationale of proposal Input sheet!B21
let commit = 'unknown';
try { commit = execSync('git rev-parse HEAD', {cwd: ROOT}).toString().trim(); } catch {}

// ---------- snapshots ----------
mkdirSync(join(ROOT, 'models', 'snapshots'), {recursive: true});
const sortObj = o => Object.fromEntries(Object.keys(o).sort().map(k => [k, o[k]]));
const snapshot = {
  name: 'original',
  description: 'The 70 proposed inputs of the WD-40 FY2025 case, all accepted. retain_formula proposals keep their workbook formula, as the page does.',
  inputSetHash: stableHash(ORIGINAL),
  overrides: sortObj(ORIGINAL),
  retainedFormulas: [...retained].sort(),
  provenance: {indexHtmlSha256: P.hashes.indexHtml, engineSha256: P.hashes.engine, workbookSha256: P.hashes.workbook,
    caseCreatedAt: P.data.createdAt},
};
writeFileSync(join(ROOT, 'models/snapshots/original.json'), JSON.stringify(snapshot, null, 1) + '\n');
writeFileSync(join(ROOT, 'models/snapshots/current.json'), JSON.stringify({...snapshot, name: 'current',
  description: 'Review state measured by this harness. It has no access to a browser review, so it equals the original set. A review exported with "Export review" can replace this file.'}, null, 1) + '\n');

// ---------- helpers ----------
function evaluate(changes = {}) {
  engine.reset({...ORIGINAL, ...changes});
  const blocked = P.caseError(engine);
  const out = engine.safe(V + 'B33');
  if (blocked || out.error) return {status: 'blocked', reason: blocked ?? `${out.error} ${out.message}`, value: null};
  const pvTV = engine.value(V + 'B19'), sumPV = engine.value(V + 'B21');
  return {status: 'valid', value: out.value, operatingAssets: engine.value(V + 'B24'), pvTV, pvFCFF: engine.value(V + 'B20'),
    terminalShare: pvTV / sumPV, terminalWACC: engine.value(V + 'M12'), terminalGrowth: engine.value(V + 'M2'),
    terminalROIC: engine.value(V + 'M40'), terminalReinvestmentRate: engine.value(V + 'M8') / engine.value(V + 'M7')};
}
function before(changes) { engine.reset(ORIGINAL); return Object.fromEntries(Object.keys(changes).map(k => [k, engine.safe(k).value])); }
const base = evaluate();

// ---------- 1. baseline rows ----------
const cols = 'BCDEFGHIJKLM'.split('');
const rowIds = {growth: 2, revenue: 3, ebitMargin: 4, ebit: 5, taxRate: 6, nopat: 7, reinvestment: 8, fcff: 9, wacc: 12,
  discountFactor: 13, pvFCFF: 14, salesToCapital: 38, investedCapital: 39, roic: 40};
engine.reset(ORIGINAL);
const rows = Object.fromEntries(Object.entries(rowIds).map(([k, r]) => [k, cols.map(c => engine.safe(`${V}${c}${r}`).value)]));
const bridgeIds = {terminalCashFlow: 'B16', terminalWACC: 'B17', terminalValue: 'B18', pvTerminalValue: 'B19', pvFCFF: 'B20', sumPV: 'B21',
  probabilityOfFailure: 'B22', proceedsIfFailure: 'B23', operatingAssets: 'B24', debt: 'B25', minorityInterests: 'B26', cash: 'B27',
  nonOperatingAssets: 'B28', equity: 'B29', options: 'B30', commonEquity: 'B31', shares: 'B32', valuePerShare: 'B33'};
const bridge = Object.fromEntries(Object.entries(bridgeIds).map(([k, c]) => [k, engine.safe(V + c).value]));
const baseInputs = Object.fromEntries(['Input sheet!B11', 'Input sheet!B12', 'Valuation output!B5', 'Input sheet!B23', 'Input sheet!B24',
  'Input sheet!B26', 'Input sheet!B27', 'Input sheet!B28', 'Input sheet!B29', 'Input sheet!B30', 'Input sheet!B31', 'Input sheet!B32',
  'Cost of capital worksheet!B12', 'Input sheet!B35', 'Input sheet!B46', 'Input sheet!B48', 'Input sheet!B49', 'Input sheet!B68',
  'Input sheet!B21', 'Input sheet!B22', 'Input sheet!B15', 'Input sheet!B18', 'R& D converter!D39'].map(id => [id, engine.safe(id).value]));

// ---------- 2. market bridge ----------
const debt = bridge.debt, cash = bridge.cash;
const ebitReported = baseInputs['Input sheet!B12'], ebitAdjusted = baseInputs['Valuation output!B5'], revenue = baseInputs['Input sheet!B11'];
const market = [['Common shares outstanding', COMMON_SHARES], ['DCF denominator (Input sheet!B21)', baseInputs['Input sheet!B21']]]
  .map(([label, shares]) => {
    const cap = PRICE * shares, ev = cap + debt - cash;
    return {label, shares, marketCap: cap, enterpriseValue: ev, evToSales: ev / revenue, evToEbitReported: ev / ebitReported, evToEbitAfterRnD: ev / ebitAdjusted};
  });

// ---------- 3. one-factor probes ----------
const CoC = 'Cost of capital worksheet!B12', TW = 'Input sheet!B46', ROICy = 'Input sheet!B48', ROIC = 'Input sheet!B49',
  TM = 'Input sheet!B29', CY = 'Input sheet!B30', G1 = 'Input sheet!B26', G25 = 'Input sheet!B28', S1 = 'Input sheet!B31', TG = 'Input sheet!B68';
const groups = [
  {id: 'wacc', title: 'WACC path (the years 1-5 rate fades to the terminal rate over years 6-10)', probes: [
    {id: 'wacc-parallel-minus1', label: 'Parallel shift −1 pp: 8% fading to 7%', changes: {[CoC]: 0.08, [TW]: 0.07}},
    {id: 'wacc-parallel-plus1', label: 'Parallel shift +1 pp: 10% fading to 9%', changes: {[CoC]: 0.10, [TW]: 0.09}},
    {id: 'wacc-flat-terminal', label: 'Flat at the terminal rate: 8% in all years', changes: {[CoC]: 0.08}},
    {id: 'wacc-terminal-minus1', label: 'Terminal rate only −1 pp: 9% fading to 7%', changes: {[TW]: 0.07}},
    {id: 'wacc-flat-7', label: 'Flat 7% in all years', changes: {[CoC]: 0.07, [TW]: 0.07}},
    {id: 'wacc-flat-6', label: 'Flat 6% in all years', changes: {[CoC]: 0.06, [TW]: 0.06}},
  ]},
  {id: 'roic', title: 'Terminal return on capital (terminal reinvestment = terminal growth / ROIC × NOPAT)', probes: [
    {id: 'roic-equals-wacc', label: 'Override on, ROIC 8%, equal to terminal WACC (control)', changes: {[ROICy]: 'Yes', [ROIC]: 0.08}},
    {id: 'roic-10', label: 'ROIC 10%', changes: {[ROICy]: 'Yes', [ROIC]: 0.10}},
    {id: 'roic-15', label: 'ROIC 15%', changes: {[ROICy]: 'Yes', [ROIC]: 0.15}},
    {id: 'roic-20', label: 'ROIC 20%', changes: {[ROICy]: 'Yes', [ROIC]: 0.20}},
    {id: 'roic-25', label: 'ROIC 25%', changes: {[ROICy]: 'Yes', [ROIC]: 0.25}},
  ]},
  {id: 'margin', title: 'Operating margin path (year-1 margin stays 17.107%; the target is reached in the convergence year)', probes:
    [[0.167409, 'reported FY2025 EBIT margin 16.74%'], [0.18, '18%'], [0.20, '20%'], [0.22, '22%']].flatMap(([m, lab]) => [5, 10].map(y => (
      {id: `margin-${(m * 100).toFixed(1)}-y${y}`, label: `Target ${lab}, reached in year ${y}`, changes: {[TM]: m, [CY]: y}})))},
  {id: 'growth', title: 'Revenue growth (years 2-5 follow year 1 through the retained formula B28 = B26; years 6-10 fade to 2.5%)', probes: [
    {id: 'growth-3', label: '3% in years 1-5', changes: {[G1]: 0.03}},
    {id: 'growth-7', label: '7% in years 1-5', changes: {[G1]: 0.07}},
    {id: 'growth-9', label: '9% in years 1-5', changes: {[G1]: 0.09}},
    {id: 'growth-y1-9-then-5', label: '9% in year 1, 5% in years 2-5', changes: {[G1]: 0.09, [G25]: 0.05}},
  ]},
  {id: 'supplementary', title: 'Supplementary: capital intensity and terminal growth', probes: [
    {id: 's2c-1.5', label: 'Sales-to-capital 1.5 in all years', changes: {[S1]: 1.5}},
    {id: 's2c-3', label: 'Sales-to-capital 3.0 in all years', changes: {[S1]: 3}},
    {id: 's2c-4', label: 'Sales-to-capital 4.0 in all years', changes: {[S1]: 4}},
    {id: 'tg-2', label: 'Terminal growth 2.0%', changes: {[TG]: 0.02}},
    {id: 'tg-3', label: 'Terminal growth 3.0%', changes: {[TG]: 0.03}},
  ]},
];
for (const g of groups) for (const p of g.probes) {
  p.before = before(p.changes); p.result = evaluate(p.changes);
  p.delta = p.result.value == null ? null : p.result.value - base.value;
}

// ---------- 4. joint scenarios ----------
const step = {wacc: {[CoC]: 0.07, [TW]: 0.07}, roic: {[ROICy]: 'Yes', [ROIC]: 0.20}, growth: {[G1]: 0.07}, margin: {[TM]: 0.20, [CY]: 5}};
const joint = [
  {id: 'J1', label: 'WACC flat 7% + terminal ROIC 20%', changes: {...step.wacc, ...step.roic}},
  {id: 'J2', label: 'J1 + growth 7% in years 1-5', changes: {...step.wacc, ...step.roic, ...step.growth}},
  {id: 'J3', label: 'J2 + margin target 20% by year 5', changes: {...step.wacc, ...step.roic, ...step.growth, ...step.margin}},
  {id: 'J4', label: 'J3 + sales-to-capital 3.0', changes: {...step.wacc, ...step.roic, ...step.growth, ...step.margin, [S1]: 3}},
];
for (const j of joint) { j.result = evaluate(j.changes); j.gapToPrice = j.result.value == null ? null : PRICE - j.result.value; }
function ladder(order) {
  let acc = {}, prev = base.value;
  return order.map(k => { acc = {...acc, ...step[k]}; const r = evaluate(acc); const s = {step: k, value: r.value, contribution: r.value - prev}; prev = r.value; return s; });
}
const ladders = [['wacc', 'roic', 'growth', 'margin'], ['margin', 'growth', 'roic', 'wacc']].map(o => ({order: o.join(' → '), steps: ladder(o)}));

// ---------- 5. reverse DCF: one parameter at a time ----------
const fmtP = x => (x * 100).toFixed(2) + '%';
function solve({id, label, param, lo, hi, changes, validLo}) {
  const f = x => { const r = evaluate(changes(x)); return r.value == null ? null : r.value - PRICE; };
  const notes = [];
  let a = lo, b = hi, fa = f(a), fb = f(b);
  if (fa == null && validLo != null) {
    notes.push(`The lower bound is invalid (${evaluate(changes(lo)).reason.split('.')[0]}), so the search starts at ${(validLo * 100).toFixed(2)} pp.`);
    a = validLo; fa = f(a);
  }
  const range = [a, b];
  if (fa == null || fb == null) return {id, label, param, range, status: 'blocked at a bound', notes};
  if (Math.sign(fa) === Math.sign(fb)) return {id, label, param, range, status: 'no solution in range', valueAtBounds: [fa + PRICE, fb + PRICE], notes};
  let x = null, fx = null, it = 0;
  for (; it < 60; it++) {
    x = (a + b) / 2; fx = f(x);
    if (Math.abs(fx) <= 0.01) break;
    if (Math.sign(fx) === Math.sign(fa)) { a = x; fa = fx; } else { b = x; fb = fx; }
  }
  const r = evaluate(changes(x));
  return {id, label, param, range, status: Math.abs(fx) <= 0.01 ? 'solved' : 'not converged', solution: x, residual: fx,
    iterations: it + 1, terminalShare: r.terminalShare, changes: changes(x), notes};
}
const gT = base.terminalGrowth;
const reverse = [
  solve({id: 'R1', label: 'Uniform shift of the WACC curve (9% fading to 8%)', param: 'shift', lo: -0.06, hi: 0.02,
    validLo: 0.025 - 0.08 + 0.0001, changes: d => ({[CoC]: 0.09 + d, [TW]: 0.08 + d})}),
  solve({id: 'R2', label: 'Flat WACC in all years', param: 'rate', lo: gT + 0.0001, hi: 0.12, changes: r => ({[CoC]: r, [TW]: r})}),
  solve({id: 'R3', label: 'Terminal ROIC', param: 'rate', lo: 0.08, hi: 5, changes: r => ({[ROICy]: 'Yes', [ROIC]: r})}),
  solve({id: 'R4', label: 'Target operating margin, reached in year 5', param: 'rate', lo: 0.10, hi: 0.80, changes: m => ({[TM]: m, [CY]: 5})}),
  solve({id: 'R5', label: 'Revenue growth in years 1-5', param: 'rate', lo: 0.0, hi: 0.40, changes: g => ({[G1]: g})}),
  solve({id: 'R6', label: 'Revenue growth in years 1-5, with WACC flat 7% and terminal ROIC 20%', param: 'rate', lo: 0.0, hi: 0.40,
    changes: g => ({...step.wacc, ...step.roic, [G1]: g})}),
];

// ---------- write JSON ----------
const columns = ['base year', ...Array.from({length: 10}, (_, i) => `year ${i + 1}`), 'terminal'];
const result = {asOf: {price: PRICE, priceDate: PRICE_DATE, priceType: 'Nasdaq unadjusted close', fiscalYearEnd: '2025-08-31'},
  inputSetHash: snapshot.inputSetHash, provenance: snapshot.provenance, base, baseInputs, columns, rows, bridge, market, groups, joint, ladders, reverse};
mkdirSync(join(ROOT, 'models/out/measure'), {recursive: true});
writeFileSync(join(ROOT, 'models/out/measure/stage1.json'), JSON.stringify(result, null, 1));

// ---------- markdown ----------
const n = (x, d = 2) => x == null ? '' : Number(x).toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d});
const pc = (x, d = 1) => x == null ? '' : (x * 100).toFixed(d) + '%';
const usd = x => x == null ? '' : '$' + n(x);
const sd = x => x == null ? '' : (x >= 0 ? '+' : '−') + '$' + n(Math.abs(x));
const fv = v => typeof v === 'number' ? (Math.abs(v) < 1 ? pc(v, 2) : n(v, 3)) : String(v);
const changeText = (c, b) => Object.entries(c).map(([k, v]) => `${k}: ${b && k in b ? fv(b[k]) : ''} → ${fv(v)}`).join('; ');
const L = [];
L.push('# Stage 1: baseline, sensitivities and reverse DCF', '',
  `Generated by \`node models/measure.mjs\` with the calculation engine copied from \`index.html\` (engine sha256 \`${P.hashes.engine.slice(0, 12)}\`, workbook sha256 \`${P.hashes.workbook.slice(0, 12)}\`, input set \`${snapshot.inputSetHash}\`). Unrounded values are in \`models/out/measure/stage1.json\`.`, '',
  `Reference price: $${PRICE} per share, the Nasdaq unadjusted close on ${PRICE_DATE}, the last trading day of fiscal 2025. The proxy statement quotes the same figure as the fiscal-year-end price. The dividend-adjusted close for that day is $210.93.`, '',
  '## 1. Original case', '',
  `Accepting the 70 proposals the way the page does gives **${usd(base.value)}** per share (unrounded ${base.value}).`, '',
  '| Row | ' + columns.join(' | ') + ' |', '|---|' + columns.map(() => '---:').join('|') + '|');
const fmtRow = (k, f) => `| ${k} | ` + rows[k].map(x => x == null ? '' : f(x)).join(' | ') + ' |';
L.push(fmtRow('growth', x => pc(x, 2)), fmtRow('revenue', x => n(x, 1)), fmtRow('ebitMargin', x => pc(x, 2)), fmtRow('ebit', x => n(x, 1)),
  fmtRow('taxRate', x => pc(x, 1)), fmtRow('nopat', x => n(x, 1)), fmtRow('reinvestment', x => n(x, 1)), fmtRow('fcff', x => n(x, 1)),
  fmtRow('wacc', x => pc(x, 2)), fmtRow('discountFactor', x => n(x, 4)), fmtRow('pvFCFF', x => n(x, 1)),
  fmtRow('investedCapital', x => n(x, 1)), fmtRow('roic', x => pc(x, 1)), '');
L.push('USD millions except rates. Reinvestment in year t is (revenue in year t+1 − revenue in year t) / sales-to-capital, so it leads revenue by one year. Terminal reinvestment is terminal growth / terminal ROIC × terminal NOPAT. With the override off, terminal ROIC equals the year-10 WACC.', '',
  '| Bridge item | USD m |', '|---|---:|',
  ...Object.entries(bridge).map(([k, v]) => `| ${k} | ${['terminalWACC', 'probabilityOfFailure'].includes(k) ? pc(v, 2) : n(v, k === 'shares' ? 6 : 2)} |`), '',
  `PV of terminal value is ${pc(base.terminalShare)} of operating assets. Terminal reinvestment takes ${pc(base.terminalReinvestmentRate)} of terminal NOPAT.`, '',
  '## 2. Price to market value', '',
  '| Share count | Shares (m) | Market cap | EV | EV / sales | EV / reported EBIT | EV / EBIT after R&D capitalization |', '|---|---:|---:|---:|---:|---:|---:|',
  ...market.map(m => `| ${m.label} | ${n(m.shares, 6)} | ${n(m.marketCap, 1)} | ${n(m.enterpriseValue, 1)} | ${n(m.evToSales, 2)}× | ${n(m.evToEbitReported, 2)}× | ${n(m.evToEbitAfterRnD, 2)}× |`), '',
  `EV adds gross borrowings of ${n(debt, 3)} and subtracts cash of ${n(cash, 3)}, USD millions. Operating leases (10.705) stay out of debt because rent stays in EBIT, as in the case. Market capitalization uses common shares outstanding. The 13.633263 m figure is the DCF denominator: common shares plus RSUs, target MSUs and vested DPUs.`, '');
L.push('## 3. One-factor sensitivities', '', `Baseline ${usd(base.value)}. Each probe changes only the listed cells.`, '');
for (const g of groups) {
  L.push(`### ${g.title}`, '', '| Probe | Cells changed | Value / share | Change | Terminal share | Status |', '|---|---|---:|---:|---:|---|');
  for (const p of g.probes) L.push(`| ${p.label} | ${changeText(p.changes, p.before)} | ${usd(p.result.value)} | ${sd(p.delta)} | ${pc(p.result.terminalShare)} | ${p.result.status === 'valid' ? 'valid' : 'blocked: ' + p.result.reason} |`);
  L.push('');
}
L.push('## 4. Joint scenarios', '', '| Scenario | Value / share | Terminal share | Gap to $216.04 |', '|---|---:|---:|---:|',
  ...joint.map(j => `| ${j.id}: ${j.label} | ${usd(j.result.value)} | ${pc(j.result.terminalShare)} | ${usd(j.gapToPrice)} |`), '',
  'The same four steps of J3 applied in two orders. The contribution of each step depends on the order, so these are not independent effects.', '');
for (const l of ladders) L.push(`- ${l.order}: ` + l.steps.map(s => `${s.step} ${sd(s.contribution)} (to ${usd(s.value)})`).join(', '));
L.push('', '## 5. Reverse DCF', '',
  `Each line solves one parameter so that value per share equals $${PRICE}, with all other inputs as in the original case unless stated. Bisection, at most 60 iterations, stop at |value − price| ≤ $0.01. A solution means the price is reached under these fixed conditions. It does not say how the market reasons.`, '',
  '| Solve | Search range | Result | Residual ($) | Terminal share | Notes |', '|---|---|---|---:|---:|---|',
  ...reverse.map(r => {
    const res = r.status !== 'solved' ? r.status + (r.valueAtBounds ? ` (value ${usd(r.valueAtBounds[0])} to ${usd(r.valueAtBounds[1])})` : '')
      : r.id === 'R1' ? `shift ${(r.solution * 100).toFixed(2)} pp: ${fmtP(0.09 + r.solution)} fading to ${fmtP(0.08 + r.solution)}` : fmtP(r.solution);
    const rng = r.id === 'R1' ? r.range.map(x => (x * 100).toFixed(2) + ' pp').join(' to ') : r.range.map(fmtP).join(' to ');
    return `| ${r.id}: ${r.label} | ${rng} | ${res} | ${r.residual == null ? '' : n(r.residual, 4)} | ${pc(r.terminalShare)} | ${r.notes.join(' ')} |`;
  }), '');
const y10 = rows.roic[10], t10 = rows.reinvestment[10], tT = rows.reinvestment[11];
L.push('## 6. Open items', '',
  `- **ROIC step at the terminal year.** Return on invested capital is ${pc(rows.roic[1])} in year 1 and ${pc(y10)} in year 10. With the override off, the terminal year assumes new capital earns ${pc(base.terminalROIC)}, so reinvestment rises from ${n(t10, 1)} in year 10 to ${n(tT, 1)} in the terminal year. Whether that step is intended is a question for Stage 2.`,
  '- **Python replica.** An earlier Python replica returned $88.06. Its first divergent row was year-1 reinvestment: the replica used the same-year revenue change, the workbook uses the next-year change. Stage 4 confirms this with a row-by-row comparison.',
  `- **Margin probes are not like for like.** Model EBIT is after R&D capitalization (${pc(rows.ebitMargin[0], 2)} in the base year). The 16.74% probe uses the reported margin, so it also removes the R&D adjustment from the target.`,
  '- **Share counts.** Market capitalization uses 13.527614 m common shares. The DCF divides by 13.633263 m, which adds unvested and vested stock units. The two EV figures in section 2 differ by that amount.',
  '- **Not yet sourced.** Analyst price targets as of 2025-08-29 and a dated CAPM build for WACC.',
  '');
mkdirSync(join(ROOT, 'reports'), {recursive: true});
writeFileSync(join(ROOT, 'reports/01-baseline-and-sensitivities.md'), L.join('\n'));
console.log('base', base.value);
for (const r of reverse) console.log(r.id, r.status, r.solution ?? '', r.residual ?? '', r.valueAtBounds ?? '');
for (const j of joint) console.log(j.id, j.result.value);
for (const g of groups) for (const p of g.probes) console.log(p.id, p.result.value?.toFixed(4), p.result.status);
