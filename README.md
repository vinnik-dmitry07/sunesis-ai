# Sunesis WD-40 valuation review

A standalone browser review of Damodaran's FCFF Simple Ginzu workbook, extended
with saved valuation scenarios, reverse DCF, acquisition and financing context,
and diligence questions with benchmark provenance.

The original 70 proposed inputs remain intact. They produce **$88.1502958013**
per share in both the original JavaScript engine and the independent Python DCF.
The **$216.04** reference is the fiscal-year-end price disclosed in the proxy,
dated to the preceding trading day, August 29, 2025. Later FY2025 filings are
used retrospectively.

## Use

Open `index.html` directly or serve the repository. The page is self-contained,
including the downloadable formula workbook. Review inputs individually, or
inspect a saved scenario and preview its full replacement before applying it.
One undo restores the prior review. Current browser edits move the current DCF;
saved scenario snapshots retain their own assumptions.

The Excel download contains the saved scenarios, regional revenue builds, DCF,
EVA, LBO, DDM, synergies, acquisition observations, sources and questions. Its
inputs and calculations use live formulas. Browser edits can be exported through
the existing review JSON action.

## Reproduce

Tested with Python 3.12 and Node 24. Python 3.9 compatibility is not asserted.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r models/requirements.txt
node models/measure.mjs
.venv/bin/python -m models.build
node models/verify.mjs
.venv/bin/python -m models.build
```

The final build incorporates the matching verification status. Repeating it
with unchanged source and data leaves the HTML and workbook unchanged.
`--skip-xlsx` is useful during page development; a workbook from another build
is not offered as a current download.

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
No Excel installation is needed to run the browser or Python models.

```bash
.venv/bin/python -m unittest discover -s models/tests -v
node --test models/tests/review_state.test.mjs
.venv/bin/python -m unittest discover -s models/questions -p 'test_*.py' -v
```

The source model hash covers the original embedded workbook and calculation
engine. Changing either requires a new measurement before rebuilding.

## Sources and scenario basis

Primary financial, transaction and capital-cost sources are recorded in
`models/data/`. Reported EBIT, R&D-adjusted EBIT and issuer adjusted EBITDA are
distinct measures. Market capitalization uses reported common shares; the DCF
uses the original explicit dilution proxy.

Bear/Base/Bull regional growth assumptions feed year-one growth and the
years-two-to-five CAGR. This Ginzu compression preserves year-one and year-five
revenue and exposes intermediate revenue differences. WACC, terminal ROIC and
long-term margin targets remain analyst assumptions. The original FY2026
pro forma guidance and the July 2026 revision are recorded separately.

Trading peer ranges require verified historical market snapshots and currently
show unavailable. The acquisition observations use announced consideration /
TTM EBITDA and are labelled as adjacent-category context. They are not claimed
to be fully reconciled enterprise-value transaction multiples. LBO assumptions
describe a sponsor financing case; synergy assumptions describe a buyer case.

## Diligence question provenance

Thirty adapted questions are grouped under ten investment topics. Their source
records come from actual FinanceBench, FinLFQA, PE Bench and FinCausal records.
The public FinTextQA policy subset was inspected and excluded as inapplicable.
Forecast questions include resolution rules and a retrospective-template label.

Pinned revisions, download hashes and observed counts are in
`models/data/benchmarks/manifest.json`. Raw snapshots are intentionally ignored.
To repeat full provenance checks:

```bash
.venv/bin/python models/questions/collect.py
.venv/bin/python models/questions/extract.py
.venv/bin/python models/questions/build_questions.py
.venv/bin/python -m unittest discover -s models/questions -p 'test_*.py' -v
```

## Calculation verification

The Python DCF is checked against actual Ginzu forecast rows across the original
case, saved scenarios and boundary cases. The emitted page-book formulas are
evaluated by the same browser engine and compared with their Python results.
`models/out/verification.json` records the matching build and checked cells.

The saved Excel formula values are populated and full recalculation on opening
is enabled. A fresh Microsoft Excel recalculation has **not** been performed;
the application and workbook disclose that limit.

The original workbook attribution and its author permission statement remain
in the application. No blanket license over third-party workbooks, source
documents or datasets is asserted.
