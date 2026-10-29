// Evaluates exported model cells with the page's own engine and compares them to the Python values.
// Usage: node models/verify_cells.mjs path/to/cells.json [--with-ginzu]
// cells.json: {cellId: {sheet, address, value|formula, pythonValue, dependencies}}
import {readFileSync, writeFileSync} from 'node:fs';
import {loadPage, originalOverrides} from './lib/page.mjs';

const file = process.argv[2];
const cells = JSON.parse(readFileSync(file, 'utf8'));
const P = await loadPage();
const book = {cells: {...(process.argv.includes('--with-ginzu') ? P.book.cells : {}), ...cells}};
const e = new P.WorkbookEngine(book, process.argv.includes('--with-ginzu') ? originalOverrides(P.data) : {});
const ABS = 1e-9, REL = 1e-9;
const rows = [];
let worst = 0;
for (const [id, c] of Object.entries(cells)) {
  if (!c.formula) continue;
  const r = e.safe(id);
  const py = c.pythonValue;
  let ok, diff = null;
  if (r.error) ok = false;
  else if (typeof py === 'number' && typeof r.value === 'number') { diff = Math.abs(r.value - py); ok = diff <= ABS || diff <= REL * Math.abs(py); worst = Math.max(worst, diff / Math.max(1, Math.abs(py))); }
  else ok = String(r.value) === String(py) || (py === true && r.value === 1) || (py === 1 && r.value === true) || (py === 0 && r.value === false);
  rows.push({id, formula: c.formula, python: py, engine: r.error ? `${r.error} ${r.message}` : r.value, diff, ok});
}
const bad = rows.filter(r => !r.ok);
writeFileSync(file.replace(/\.json$/, '.engine-check.json'), JSON.stringify({checked: rows.length, failed: bad.length, worstRelative: worst, rows}, null, 1));
console.log(`engine check ${file}: ${rows.length} formulas, ${bad.length} mismatches, worst relative difference ${worst.toExponential(2)}`);
for (const b of bad.slice(0, 20)) console.log('  MISMATCH', b.id, b.formula, 'python', b.python, 'engine', b.engine);
process.exit(bad.length ? 1 : 0);
