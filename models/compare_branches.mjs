// M0: reproducible comparison of two branches of the WD-40 valuation page.
// Reads committed bytes with `git show` (never the working tree, whose line endings depend on core.autocrlf),
// evaluates every saved case with each branch's own engine, and applies identical control changes to both.
// Usage: node compare_branches.mjs <repo> <refA> <refB> <outDir>
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdirSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';

const [repo, refA, refB, outDir] = process.argv.slice(2);
mkdirSync(outDir, {recursive: true});
const git = (...a) => execFileSync('git', ['-C', repo, ...a], {maxBuffer: 1 << 30});
const sha = b => createHash('sha256').update(b).digest('hex');
const between = (t, s, e) => { const a = t.indexOf(s); if (a < 0 || t.indexOf(s, a + 1) >= 0) throw new Error(`anchor ${s}`); const b = t.indexOf(e, a + s.length); if (b < 0) throw new Error(`end ${e}`); return t.slice(a + s.length, b); };
const tryShow = (ref, path) => { try { return git('show', `${ref}:${path}`).toString('utf8'); } catch { return null; } };

async function load(ref) {
  const full = git('rev-parse', ref).toString().trim();
  const bytes = git('show', `${ref}:index.html`);
  const html = bytes.toString('utf8');
  const bookText = between(html, 'const BUNDLED_BOOK=', ';const BUNDLED_CASE=');
  const caseText = between(html, ';const BUNDLED_CASE=', ';/* A deliberately bounded Excel evaluator');
  const engineSrc = 'class FormulaError' + between(html, '\nclass FormulaError', '\nconst $=id=>');
  const caseErrorSrc = 'function caseError(e){' + between(html, '\nfunction caseError(e){', '\nconst inputLabel=');
  const dir = join(tmpdir(), 'sunesis-m0-' + full.slice(0, 12));
  mkdirSync(dir, {recursive: true});
  const mod = join(dir, 'engine.mjs');
  writeFileSync(mod, `${engineSrc}\n${caseErrorSrc}\nexport {WorkbookEngine, caseError};\n`);
  const E = await import(pathToFileURL(mod).href);
  let payload = null;
  for (const [s, e] of [['/*VALUATION-START*/const BUNDLED_VALUATION=', ';/*VALUATION-END*/'], ['/*BUNDLED_VALUATION:start*/const BUNDLED_VALUATION=', ';/*BUNDLED_VALUATION:end*/']]) {
    if (html.includes(s)) payload = JSON.parse(between(html, s, e));
  }
  return {ref, full, html, book: JSON.parse(bookText), data: JSON.parse(caseText), ...E, payload,
    hashes: {indexHtml: sha(bytes), book: sha(bookText), case: sha(caseText), engine: sha(engineSrc), caseError: sha(caseErrorSrc)}};
}
const originalOverrides = data => Object.fromEntries(data.proposals.filter(p => p.operation !== 'retain_formula').map(p => [p.cell, p.value]));
const stable = o => sha(JSON.stringify(Object.keys(o).sort().map(k => [k, o[k]]))).slice(0, 16);

const V = 'Valuation output!';
const COLS = 'CDEFGHIJKL'.split('');
function evaluate(P, e, overrides) {
  e.reset(overrides);
  const err = P.caseError(e), out = e.safe(V + 'B33');
  if (err || out.error) return {status: 'blocked', reason: err ?? out.message};
  const g = id => e.value(id);
  const row = r => COLS.map(c => g(`${V}${c}${r}`));
  return {status: 'valid', value: out.value, operatingValue: g(V + 'B24'), equityValue: g(V + 'B31'), terminalShare: g(V + 'B19') / g(V + 'B21'),
    pvTerminal: g(V + 'B19'), pvForecast: g(V + 'B20'), terminalWACC: g(V + 'M12'), terminalGrowth: g(V + 'M2'), terminalROIC: g(V + 'M40'),
    rows: {revenue: row(3), ebit: row(5), nopat: row(7), reinvestment: row(8), fcff: row(9), discount: row(13)}};
}
function solveShift(P, e, base) {
  const w0 = (e.reset(base), e.value('Cost of capital worksheet!B12')), wT = e.value('Input sheet!B46'), g = e.value(V + 'M2');
  const price = e.value('Input sheet!B22');
  const f = d => { const r = evaluate(P, e, {...base, 'Cost of capital worksheet!B12': w0 + d, 'Input sheet!B46': wT + d}); return r.status === 'valid' ? r.value - price : null; };
  let lo = Math.max(-w0, g - wT) + 0.0001, hi = 0.2, flo = f(lo), fhi = f(hi);
  if (flo == null || fhi == null) return {status: 'blocked at a bound', bounds: [lo, hi]};
  if (Math.sign(flo) === Math.sign(fhi)) return {status: 'no bracket', bounds: [lo, hi], values: [flo + price, fhi + price]};
  let x, fx, i = 0;
  for (; i < 100; i++) { x = (lo + hi) / 2; fx = f(x); if (Math.abs(fx) <= 0.01) break; if (Math.sign(fx) === Math.sign(flo)) { lo = x; flo = fx; } else { hi = x; } }
  return {status: Math.abs(fx) <= 0.01 ? 'solved' : 'not converged', shift: x, residual: fx, iterations: i + 1, wacc0: w0 + x, waccT: wT + x, price};
}

const A = await load(refA), B = await load(refB);
const result = {generatedFrom: {[refA]: A.full, [refB]: B.full}, hashes: {[refA]: A.hashes, [refB]: B.hashes}, cases: {}, probes: {}, reverse: {}, notes: []};
for (const k of ['book', 'case', 'engine', 'caseError']) if (A.hashes[k] !== B.hashes[k]) result.notes.push(`${k} differs between branches`);

// saved cases per branch
function casesOf(P) {
  const orig = originalOverrides(P.data);
  const out = {original: {overrides: orig, source: 'BUNDLED_CASE proposals (retain_formula proposals keep their formula)'}};
  if (P.payload?.scenarios) {
    for (const s of P.payload.scenarios) out[s.id] = {overrides: s.overrides, source: 'payload scenarios[].overrides (full set)', saved: s.value};
  } else {
    const sc = JSON.parse(tryShow(P.ref, 'models/scenarios.json'));
    const saved = P.payload?.methods?.find(m => m.id === 'dcf')?.scenarios ?? {};
    for (const [k, s] of Object.entries(sc.scenarios)) out[k] = {overrides: {...orig, ...s.overrides}, source: 'original + models/scenarios.json overrides', saved: saved[k]?.value};
  }
  return out;
}
for (const P of [A, B]) {
  const e = new P.WorkbookEngine(P.book, {});
  const cs = casesOf(P);
  result.cases[P.ref] = {};
  for (const [k, c] of Object.entries(cs)) {
    const r = evaluate(P, e, c.overrides);
    result.cases[P.ref][k] = {...r, inputSetHash: stable(c.overrides), overrideCount: Object.keys(c.overrides).length, source: c.source, savedValue: c.saved ?? null,
      savedMatches: c.saved == null ? null : Math.abs(c.saved - r.value) <= 1e-9 * Math.max(1, Math.abs(r.value))};
  }
  // which cells each scenario changes relative to the branch's original set
  const orig = cs.original.overrides;
  result.cases[P.ref]._changedCells = Object.fromEntries(Object.entries(cs).filter(([k]) => k !== 'original').map(([k, c]) => [k,
    Object.fromEntries(Object.keys({...orig, ...c.overrides}).filter(id => JSON.stringify(orig[id]) !== JSON.stringify(c.overrides[id])).map(id => [id, [orig[id] ?? null, c.overrides[id] ?? null]]))]));
  // identical control probes, applied to each branch's original set
  const probes = {
    'wacc -1pp (9%->8%, 8%->7%)': {'Cost of capital worksheet!B12': 0.08, 'Input sheet!B46': 0.07},
    'growth years 1-5 = 7%': {'Input sheet!B26': 0.07},
    'target margin 20% by year 5': {'Input sheet!B29': 0.20, 'Input sheet!B30': 5},
    'terminal ROIC 20%': {'Input sheet!B48': 'Yes', 'Input sheet!B49': 0.20},
  };
  result.probes[P.ref] = Object.fromEntries(Object.entries(probes).map(([k, ch]) => [k, {cells: ch, value: evaluate(P, e, {...orig, ...ch}).value}]));
  result.reverse[P.ref] = {original: solveShift(P, e, orig), base: cs.base ? solveShift(P, e, cs.base.overrides) : null};
  // the original sets of both branches should be identical
  result.cases[P.ref]._originalSetHash = stable(orig);
}
// artifacts present in each branch
const artifacts = {};
for (const P of [A, B]) {
  const files = git('ls-tree', '-r', '--name-only', P.full).toString().split('\n').filter(f => /\.xlsx$|verification\.json|05-checks\.md|measurement\.json|stage1/.test(f));
  artifacts[P.ref] = files;
}
result.artifacts = artifacts;
writeFileSync(join(outDir, 'm0.json'), JSON.stringify(result, null, 1));

// markdown
const n = (x, d = 6) => x == null ? '' : typeof x === 'number' ? x.toFixed(d) : String(x);
const L = ['# M0: comparison of the two branches', '',
  `Generated by \`node models/compare_branches.mjs\` from committed bytes (\`git show\`), so working-tree line endings cannot change the result.`, '',
  '| | ' + [A, B].map(P => `${P.ref} \`${P.full.slice(0, 7)}\``).join(' | ') + ' |', '|---|---|---|',
  ...['indexHtml', 'book', 'case', 'engine', 'caseError'].map(k => `| ${k} sha256 | ${A.hashes[k].slice(0, 16)} | ${B.hashes[k].slice(0, 16)} |`),
  `| original input set | ${result.cases[refA]._originalSetHash} | ${result.cases[refB]._originalSetHash} |`, '',
  '## Saved cases, recomputed with each branch\'s own engine', '',
  '| Branch | Case | Value / share | Saved value | Matches | Operating value | Equity value | Terminal share | Cells changed vs original |', '|---|---|---:|---:|---|---:|---:|---:|---:|'];
for (const P of [A, B]) for (const [k, c] of Object.entries(result.cases[P.ref])) {
  if (k.startsWith('_')) continue;
  L.push(`| ${P.ref} | ${k} | ${n(c.value)} | ${n(c.savedValue)} | ${c.savedMatches == null ? '' : c.savedMatches ? 'yes' : 'NO'} | ${n(c.operatingValue, 3)} | ${n(c.equityValue, 3)} | ${n(c.terminalShare * 100, 2)}% | ${k === 'original' ? '' : Object.keys(result.cases[P.ref]._changedCells[k]).length} |`);
}
L.push('', '## Cells each scenario changes', '');
for (const P of [A, B]) for (const [k, ch] of Object.entries(result.cases[P.ref]._changedCells)) {
  L.push(`- **${P.ref} ${k}**: ` + Object.entries(ch).map(([id, [a, b]]) => `${id} ${typeof a === 'number' ? +a.toFixed(6) : a} → ${typeof b === 'number' ? +b.toFixed(6) : b}`).join('; '));
}
L.push('', '## Yearly rows of Base (years 1-10)', '');
for (const P of [A, B]) {
  const c = result.cases[P.ref].base; if (!c?.rows) continue;
  L.push(`**${P.ref}**`, '', '| Row | ' + COLS.map((_, i) => `Y${i + 1}`).join(' | ') + ' |', '|---|' + COLS.map(() => '---:').join('|') + '|',
    ...Object.entries(c.rows).map(([r, xs]) => `| ${r} | ` + xs.map(x => r === 'discount' ? x.toFixed(4) : x.toFixed(2)).join(' | ') + ' |'), '');
}
L.push('## Identical control changes on each branch\'s original set', '', '| Probe | Cells | ' + [A, B].map(P => P.ref).join(' | ') + ' |', '|---|---|---:|---:|');
for (const k of Object.keys(result.probes[refA])) L.push(`| ${k} | ${Object.entries(result.probes[refA][k].cells).map(([a, b]) => `${a}=${b}`).join(', ')} | ${n(result.probes[refA][k].value)} | ${n(result.probes[refB][k].value)} |`);
L.push('', '## Reverse DCF: parallel shift of the WACC curve to reach the reference price', '', '| Branch | Starting set | Status | Shift (pp) | WACC path | Residual ($) |', '|---|---|---|---:|---|---:|');
for (const P of [A, B]) for (const [k, r] of Object.entries(result.reverse[P.ref])) if (r) L.push(`| ${P.ref} | ${k} | ${r.status} | ${r.shift == null ? '' : (r.shift * 100).toFixed(4)} | ${r.wacc0 == null ? '' : `${(r.wacc0 * 100).toFixed(3)}% → ${(r.waccT * 100).toFixed(3)}%`} | ${r.residual == null ? '' : r.residual.toExponential(2)} |`);
L.push('', '## Workbooks and check results in each branch', '');
for (const P of [A, B]) L.push(`- ${P.ref}: ` + (artifacts[P.ref].join(', ') || 'none'));
L.push('', '## Notes', '', ...(result.notes.length ? result.notes.map(x => `- ${x}`) : ['- Workbook, case, engine and caseError are byte-identical between the branches.']));
writeFileSync(join(outDir, 'm0.md'), L.join('\n') + '\n');
console.log(L.slice(0, 40).join('\n'));
