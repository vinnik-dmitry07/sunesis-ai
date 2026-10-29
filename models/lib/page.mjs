// Loads the calculation engine and bundled data from index.html without a browser.
// The engine source is copied verbatim from the page, so results match what the page shows.
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {dirname, join} from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
export const ROOT = join(here, '..', '..');
export const INDEX = join(ROOT, 'index.html');

function between(text, start, end) {
  const a = text.indexOf(start);
  if (a < 0) throw new Error(`Anchor not found: ${start}`);
  if (text.indexOf(start, a + 1) >= 0) throw new Error(`Anchor not unique: ${start}`);
  const b = text.indexOf(end, a + start.length);
  if (b < 0) throw new Error(`End anchor not found: ${end}`);
  return text.slice(a + start.length, b);
}

export async function loadPage(path = INDEX) {
  const html = readFileSync(path, 'utf8');
  const book = JSON.parse(between(html, 'const BUNDLED_BOOK=', ';const BUNDLED_CASE='));
  const data = JSON.parse(between(html, ';const BUNDLED_CASE=', ';/* A deliberately bounded Excel evaluator'));
  const engineSrc = 'class FormulaError' + between(html, '\nclass FormulaError', '\nconst $=id=>');
  const caseErrorSrc = 'function caseError(e){' + between(html, '\nfunction caseError(e){', '\nconst inputLabel=');
  const outDir = join(ROOT, 'models', 'out');
  mkdirSync(outDir, {recursive: true});
  const enginePath = join(outDir, 'engine.mjs');
  writeFileSync(enginePath, `${engineSrc}\n${caseErrorSrc}\nexport {WorkbookEngine, FormulaError, parseFormula, tokenize, caseError};\n`);
  const mod = await import(pathToFileURL(enginePath).href + '?v=' + Date.now());
  const sha = s => createHash('sha256').update(s).digest('hex');
  return {html, book, data, ...mod, hashes: {indexHtml: sha(html), engine: sha(engineSrc), workbook: book.metadata.sha256}};
}

// Mirrors the page's rebuild(): accepted proposals override their cell;
// retain_formula proposals are accepted as status "formula" and keep the workbook formula.
export function originalOverrides(data) {
  const o = {};
  for (const p of data.proposals) if (p.operation !== 'retain_formula') o[p.cell] = p.value;
  return o;
}

export function stableHash(obj) {
  const keys = Object.keys(obj).sort();
  return createHash('sha256').update(JSON.stringify(keys.map(k => [k, obj[k]]))).digest('hex').slice(0, 16);
}
