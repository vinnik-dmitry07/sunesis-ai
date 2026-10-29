# Stage 4a: portable-spreadsheet spike

`python -I models/spike_portable_spreadsheet.py` builds a two-sheet toy book with arithmetic, a power, `IF`, cross-sheet references and row and column labels. `models/verify_cells.mjs` evaluates every exported formula with the engine copied from `index.html`. `models/verify_excel.py` opens the `.xlsx` in Microsoft Excel, runs a full rebuild recalculation, saves a copy, reopens it and reads every formula cell again.

Versions: portable-spreadsheet 2.2.1, XlsxWriter 3.3.1, numpy-financial 1.0.0, Python 3.9.18, Node 24.18.0, Excel 16.

## What the library emits

| Fact | Observed |
|---|---|
| Address offset | Row labels go in column A and column labels in row 1, so `iloc[r, c]` is Excel column `c + 1`, row `r + 2`. The Excel words already use these addresses. |
| Cross-sheet references | `fn.cross_reference(cell, sheet)` writes `'Inputs'!B2`. The page engine parses quoted sheet names. |
| Conditionals | `fn.conditional(a > b, x, y)` writes `IF(B3>20,1,0)`. |
| Power | `**` writes `^`. |
| Cached results | The `.xlsx` stores the Python value as each formula's cached result. A viewer that does not recalculate shows the Python number even when the formula text is wrong. |
| Parentheses | **Not carried over.** `rev * (1 + g)` is written as `B2*1+B3`. Grouping needs `fn.brackets(...)`. |

## The parentheses problem

Without `fn.brackets`, Python reports 105.00 for `100 × (1 + 5%)` while the Excel formula `='Inputs'!B2*1+'Inputs'!B3` gives 100.05. Because the cached value is Python's, the file looks right until Excel recalculates it.

The engine check catches this. With the brackets removed from one cell, `verify_cells.mjs` reports 6 of 8 formulas wrong, including every cell downstream of it, and exits with an error.

## Result with brackets

| Check | Formulas | Mismatches | Worst relative difference |
|---|---:|---:|---:|
| Page engine vs Python | 8 | 0 | 0 |
| Excel full recalculation vs Python | 8 | 0 | 0 |
| Excel after save and reopen | 8 | 0 changed | |

## Rules for the models

1. Wrap every grouped term in `fn.brackets()`.
2. Use only functions the page engine supports: `IF`, `SUM`, `AVERAGE`, `ROUND`, `EXP`, `LN`, `NORMSDIST`, `VLOOKUP`. `models/lib/pss.py` refuses anything else at export.
3. Every exported book goes through both checks before it is used. A model is not called Excel-verified until `verify_excel.py` passes.
