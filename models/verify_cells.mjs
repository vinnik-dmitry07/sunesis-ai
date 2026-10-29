// Evaluates exported model cells with the page's own engine and compares them to the Python values.
// Usage: node models/verify_cells.mjs path/to/cells.json [--with-ginzu]
// cells.json: {cellId: {sheet, address, value|formula, pythonValue, dependencies}}
// Every formula cell must carry a finite numeric or boolean Python value; a missing or non-finite value on
// either side is a failure, never a match. The report records the sha256 of the file it checked.
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {loadPage, originalOverrides} from './lib/page.mjs';

const file = process.argv[2];
const bytes = readFileSync(file);
const cells = JSON.parse(bytes.toString('utf8'));
const P = await loadPage();
const withGinzu = process.argv.includes('--with-ginzu');
const book = {cells: {...(withGinzu ? P.book.cells : {}), ...cells}};
const e = new P.WorkbookEngine(book, withGinzu ? originalOverrides(P.data) : {});
const ABS = 1e-9, REL = 1e-9;
const finite = x => typeof x === 'number' && Number.isFinite(x);
const rows = [];
let worst = 0;
for (const [id, c] of Object.entries(cells)) {
  if (!c.formula) continue;
  const r = e.safe(id);
  const py = c.pythonValue;
  let ok = false, diff = null, reason = null;
  if (r.error) reason = `engine error ${r.error} ${r.message}`;
  else if (!(finite(py) || typeof py === 'boolean')) reason = `missing or non-finite Python value (${py})`;
  else if (typeof py === 'boolean') ok = r.value === py || r.value === (py ? 1 : 0);
  else if (!finite(r.value) && typeof r.value !== 'boolean') reason = `non-numeric engine value (${r.value})`;
  else {
    const v = typeof r.value === 'boolean' ? +r.value : r.value;
    diff = Math.abs(v - py);
    ok = diff <= ABS || diff <= REL * Math.abs(py);
    worst = Math.max(worst, diff / Math.max(1, Math.abs(py)));
  }
  rows.push({id, formula: c.formula, python: py, engine: r.error ? null : r.value, diff, ok, reason});
}
const bad = rows.filter(r => !r.ok);
const report = {file, cellsSha256: createHash('sha256').update(bytes).digest('hex'), engineSha256: P.hashes.engine,
  checked: rows.length, failed: bad.length, worstRelative: worst, tolerance: {absolute: ABS, relative: REL}, failures: bad.slice(0, 200)};
writeFileSync(file.replace(/\.json$/, '.engine-check.json'), JSON.stringify(report, null, 1));
console.log(`engine check ${file}: ${rows.length} formulas, ${bad.length} mismatches, worst relative difference ${worst.toExponential(2)}`);
for (const b of bad.slice(0, 20)) console.log('  MISMATCH', b.id, b.formula, 'python', b.python, 'engine', b.engine, b.reason ?? '');
process.exit(bad.length || rows.length === 0 ? 1 : 0);
