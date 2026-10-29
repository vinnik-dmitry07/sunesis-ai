// The exported method formulas and the original workbook, evaluated by the page engine with inputs the saved cases
// never reach: a buyout whose cash cannot meet the mandatory payment, and a terminal WACC equal to terminal growth.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {ROOT, loadPage, originalOverrides} from '../lib/page.mjs';

const P = await loadPage();
const cells = JSON.parse(readFileSync(join(ROOT, 'models/out/valuation_book/valuation_cells.json'), 'utf8'));
const byLabel = (sheet, label) => {
  const c = Object.values(cells).find(c => c.sheet === sheet && c.label === label);
  assert.ok(c, `${sheet}: no cell labelled ${label}`);
  return c.id;
};

for (const k of ['Bear', 'Base', 'Bull']) {
  const sheet = `LBO ${k}`;
  const id = label => byLabel(sheet, label);
  test(`${sheet}: a year-1 cash shortfall makes the case infeasible instead of adding debt`, () => {
    const base = new P.WorkbookEngine({cells});
    assert.equal(base.value(id('Feasible (1 = no funding shortfall) · Entry / FY2025')), 1);
    const e = new P.WorkbookEngine({cells}, {[id('FCFF before financing (DCF Base) · Year 1')]: -500});
    assert.equal(e.value(id('Funding shortfall (1 = yes) · Year 1')), 1);
    assert.equal(e.value(id('Feasible (1 = no funding shortfall) · Entry / FY2025')), 0);
    assert.equal(e.value(id('Meets hurdle (1 = yes) · Entry / FY2025')), 0);
    assert.equal(e.value(id('Cash sweep · Year 1')), 0);
    assert.ok(e.value(id('Debt, end of year · Year 1')) <= e.value(id('Debt, end of year · Entry / FY2025')));
  });
}

test('the original workbook refuses a terminal WACC equal to terminal growth', () => {
  const over = originalOverrides(P.data);
  const ok = new P.WorkbookEngine(P.book, over);
  assert.equal(P.caseError(ok), null);
  const bad = new P.WorkbookEngine(P.book, {...over, 'Input sheet!B46': ok.value('Input sheet!B68')});
  assert.ok(P.caseError(bad));
});
