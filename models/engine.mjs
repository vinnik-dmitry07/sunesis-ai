import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

export const root = fileURLToPath(new URL('../', import.meta.url));

export function loadOriginal(path = `${root}index.html`) {
  const html = readFileSync(path, 'utf8');
  const start = html.indexOf('const BUNDLED_BOOK=');
  const end = html.indexOf('const $=');
  if (start < 0 || end < start) throw new Error('Original workbook/engine anchors are missing.');
  const context = vm.createContext({});
  vm.runInContext(`${html.slice(start, end)}\nglobalThis.bundle={book:BUNDLED_BOOK,data:BUNDLED_CASE,WorkbookEngine,parseFormula,tokenize};`, context, {timeout:10000});
  const result = context.bundle;
  const caseStart=html.indexOf('const BUNDLED_CASE=');
  const literal=html.slice(start+'const BUNDLED_BOOK='.length,caseStart).trim().replace(/;$/,'');
  const engineSource=html.slice(html.indexOf('class FormulaError extends Error'),end);
  result.sourceModelHash=createHash('sha256').update(literal+'\n'+engineSource).digest('hex');
  result.overrides = Object.fromEntries(result.data.proposals.filter(p => p.operation !== 'retain_formula').map(p => [p.cell,p.value]));
  result.inputHash = createHash('sha256').update(JSON.stringify(result.overrides)).digest('hex');
  return result;
}

export function evaluate(engine, overrides) {
  engine.reset(overrides);
  const get = address => engine.value(`Valuation output!${address}`);
  const value = get('B33');
  if (!Number.isFinite(value)) throw new Error('Non-finite DCF output.');
  const rows = Array.from({length:11},(_,i) => {
    const col = String.fromCharCode(67+i);
    return {year:i===10?'Terminal':i+1,cells:Object.fromEntries(Array.from({length:14},(_,j) => [`${col}${j+1}`,engine.safe(`Valuation output!${col}${j+1}`)]))};
  });
  return {value,operatingValue:get('B24'),equityValue:get('B31'),pvTerminalValue:get('B19'),pvCashFlows:get('B21'),terminalShare:get('B19')/get('B21'),rows};
}

export function validateOverrides(engine, overrides) {
  engine.reset(overrides);
  const value = id => engine.value(id);
  const growth = value('Valuation output!M2');
  const rate = value('Valuation output!M12');
  if (!(rate > growth)) return 'Terminal WACC must exceed terminal growth.';
  if (!(value('Input sheet!B21') > 0)) return 'Share count must be positive.';
  if (!(value('Input sheet!B31') > 0 && value('Input sheet!B32') > 0)) return 'Sales-to-capital ratios must be positive.';
  if (value('Input sheet!B48') === 'Yes') {
    const roic = value('Input sheet!B49');
    if (!(roic > 0)) return 'Active terminal ROIC must be positive.';
    if (growth/roic < 0 || growth/roic > 1) return 'Terminal reinvestment must be between 0% and 100% for this stable-growth case.';
  }
  return null;
}

export function solveWaccShift(engine, original, price) {
  const initial = original['Cost of capital worksheet!B12'];
  const terminal = original['Input sheet!B46'];
  const growth = original['Input sheet!B68'];
  const bounds = [Math.max(-initial+0.0001,growth-terminal+0.0001),0.2];
  const run = shift => evaluate(engine,{...original,'Cost of capital worksheet!B12':initial+shift,'Input sheet!B46':terminal+shift}).value-price;
  let [low,high] = bounds, fl = run(low), fh = run(high);
  if (fl*fh > 0) return {status:'no_solution',parameter:'parallel WACC shift',bounds,residuals:[fl,fh]};
  let mid=0,residual=0,iterations=0;
  for (;iterations<60;iterations++) {
    mid=(low+high)/2;residual=run(mid);
    if (Math.abs(residual)<=0.000001) break;
    if (fl*residual<=0) high=mid;else {low=mid;fl=residual;}
  }
  return {status:'solved',parameter:'parallel WACC shift',shift:mid,waccInitial:initial+mid,waccTerminal:terminal+mid,price,residual,iterations:iterations+1,bounds};
}
