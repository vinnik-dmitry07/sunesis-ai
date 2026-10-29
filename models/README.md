# WD-40 valuation models

Everything behind the valuation range in `index.html`. The case is a retrospective FY2025 review: the reference price is the $216.04 Nasdaq close on 29 Aug 2025, and filings up to the FY2025 10-K (27 Oct 2025) are used. Later filings are excluded from every calculation.

## Rebuild

```bash
bash models/data/fetch.sh
```

```bash
python -I models/build.py
```

`fetch.sh` restores the raw files that are not committed (peer SEC facts and the five benchmark datasets). `build.py` reruns every step in order, checks every formula in the page's own engine and, on Windows with Excel, recalculates the workbook in Excel. It writes `reports/05-checks.md` and embeds the results in `index.html` between `/*BUNDLED_VALUATION:start*/` and `/*BUNDLED_VALUATION:end*/`.

Requirements: Python 3.9+ with `portable-spreadsheet==2.2.1`, `openpyxl`, `xlrd` and `pywin32` (Excel check only), and Node 18+.

## Steps

| File | What it does |
|---|---|
| `lib/page.mjs` | Loads the calculation engine and bundled workbook straight from `index.html`, so headless results match the page. |
| `measure.mjs` | Stage 1: reproduces the original $88.15, then sensitivities, joint scenarios and one-parameter reverse DCF solves. |
| `stage2_assumptions.py` | Dated CAPM build, FY2026 guidance on the pro forma base, filed history; writes `scenarios.json`. |
| `scenarios.mjs` | Evaluates Bear, Base and Bull in the page engine and solves what Base needs to reach the price. |
| `export_ginzu_cases.mjs` | Resolved Ginzu inputs and rows per case, for the Python port. |
| `dcf.py`, `compare_dcf.py` | The Ginzu FCFF DCF on portable-spreadsheet, compared row by row with the engine. |
| `comps_extract.py`, `comps.py` | Peer LTM financials as filed by 29 Aug 2025, one-off charges traced to XBRL facts, EV/EBITDA quartiles. |
| `precedents.py` | Control transactions with disclosed EV and trailing EBITDA (`data/precedents/deals.json`). |
| `methods.py` | EVA restatement, dividend discount, buyout ability-to-pay and strategic-buyer synergies, in one workbook with the above. |
| `questions/` | Merges FinanceBench, FinLFQA, FinCausal, PE Bench and FinTextQA, then builds the WD-40 questions with computed answers. |
| `verify_cells.mjs`, `verify_excel.py` | Evaluate every exported formula in the page engine and in Excel against the Python value. |
| `build_payload.mjs`, `inject.py` | Assemble the page payload and embed it. |

## Excel

`excel/wd40_valuation.xlsx` holds every model with live formulas, recalculated and saved by Excel. portable-spreadsheet does not carry Python parentheses into Excel formulas, so every grouped term is wrapped in `fn.brackets()`; `reports/03-spreadsheet-spike.md` shows the failure this prevents.

## Reports

`reports/01` to `06` record each stage: the baseline and sensitivities, the dated assumptions, the spreadsheet spike, the DCF port, the checks and the questions.
