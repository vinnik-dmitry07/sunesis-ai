// Resolves each case's Ginzu driver values and engine rows, for the Python port and its comparison.
// Usage: node models/export_ginzu_cases.mjs  ->  models/out/ginzu_cases.json
import {readFileSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {loadPage, originalOverrides, stableHash, ROOT} from './lib/page.mjs';
import {unsupportedFeatures} from './lib/scope.mjs';

const P = await loadPage();
const ORIGINAL = originalOverrides(P.data);
const S = JSON.parse(readFileSync(join(ROOT, 'models/scenarios.json'), 'utf8'));
const e = new P.WorkbookEngine(P.book, ORIGINAL);
const V = 'Valuation output!';
const DRIVERS = {
  revenue0: ['Valuation output!B3', 'Revenue FY2025', 'USD m'],
  ebit0: ['Valuation output!B5', 'EBIT FY2025 after R&D capitalization', 'USD m'],
  investedCapital0: ['Valuation output!B39', 'Invested capital FY2025', 'USD m'],
  debt: ['Valuation output!B25', 'Debt', 'USD m'],
  cash: ['Valuation output!B27', 'Cash', 'USD m'],
  minorities: ['Valuation output!B26', 'Minority interests', 'USD m'],
  nonOperating: ['Valuation output!B28', 'Non-operating assets', 'USD m'],
  options: ['Valuation output!B30', 'Value of employee options', 'USD m'],
  shares: ['Valuation output!B32', 'Shares, DCF denominator', 'million'],
  growth1: ['Input sheet!B26', 'Revenue growth, year 1', 'rate'],
  growth25: ['Input sheet!B28', 'Revenue growth, years 2-5', 'rate'],
  growthT: ['Valuation output!M2', 'Revenue growth after year 10', 'rate'],
  margin1: ['Input sheet!B27', 'Operating margin, year 1', 'rate'],
  marginTarget: ['Input sheet!B29', 'Target operating margin', 'rate'],
  convergence: ['Input sheet!B30', 'Margin convergence year', 'year'],
  tax0: ['Valuation output!B6', 'Tax rate, base year to year 5', 'rate'],
  taxT: ['Valuation output!M6', 'Tax rate after year 10', 'rate'],
  s2c1: ['Input sheet!B31', 'Sales to capital, years 1-5', 'ratio'],
  s2c2: ['Input sheet!B32', 'Sales to capital, years 6-10', 'ratio'],
  wacc0: ['Input sheet!B35', 'WACC, years 1-5', 'rate'],
  waccT: ['Valuation output!M12', 'WACC after year 10', 'rate'],
  roicOverride: ['Input sheet!B48', 'Terminal ROIC override (1 = on)', 'flag'],
  roicT: ['Input sheet!B49', 'Terminal ROIC when the override is on', 'rate'],
};
const ROWS = {growth: 2, revenue: 3, margin: 4, ebit: 5, tax: 6, nopat: 7, reinvestment: 8, fcff: 9, nol: 10, wacc: 12, discount: 13, pv: 14, s2c: 38, investedCapital: 39, roic: 40};
const BRIDGE = {terminalCashFlow: 'B16', terminalWACC: 'B17', terminalValue: 'B18', pvTerminalValue: 'B19', sumPV: 'B20', operatingAssetsBeforeDistress: 'B21',
  operatingAssets: 'B24', debt: 'B25', minorities: 'B26', cash: 'B27', nonOperating: 'B28', equity: 'B29', options: 'B30', commonEquity: 'B31', shares: 'B32', valuePerShare: 'B33'};
const cases = {original: {label: 'Original', overrides: ORIGINAL}};
for (const [k, s] of Object.entries(S.scenarios)) cases[k] = {label: s.label, overrides: {...ORIGINAL, ...s.overrides}};
const out = {};
for (const [k, c] of Object.entries(cases)) {
  e.reset(c.overrides);
  const unsupported = unsupportedFeatures(e);
  if (unsupported.length) {
    console.error(`Case ${k} uses Ginzu features the Python port does not model: ${unsupported.join('; ')}. Export refused.`);
    process.exit(1);
  }
  const g = id => e.safe(id).value;
  const drivers = Object.fromEntries(Object.entries(DRIVERS).map(([name, [id, label, unit]]) => {
    let v = g(id);
    if (name === 'roicOverride') v = v === 'Yes' ? 1 : 0;
    return [name, {value: v, cell: id, label, unit}];
  }));
  const rows = Object.fromEntries(Object.entries(ROWS).map(([n, r]) => [n, 'BCDEFGHIJKLM'.split('').map(col => g(`${V}${col}${r}`))]));
  rows.roicTerminal = g(V + 'M40');
  out[k] = {label: c.label, inputSetHash: stableHash(c.overrides), drivers, rows, bridge: Object.fromEntries(Object.entries(BRIDGE).map(([n, a]) => [n, g(V + a)]))};
}
writeFileSync(join(ROOT, 'models/out/ginzu_cases.json'), JSON.stringify({engineSha256: P.hashes.engine, workbookSha256: P.hashes.workbook, cases: out}, null, 1));
console.log(Object.entries(out).map(([k, v]) => `${k} ${v.bridge.valuePerShare}`).join(' | '));
