# WD-40 valuation models

Everything behind the valuation range in `index.html`. The case is a retrospective FY2025 review: the reference price is the $216.04 Nasdaq close on 29 Aug 2025, and filings up to the FY2025 10-K (27 Oct 2025) are used. Later filings are excluded from every calculation and shown apart.

## Rebuild

```bash
bash models/data/fetch.sh
```

```bash
python -I models/build.py
```

`fetch.sh` restores the raw files that are not committed: peer SEC facts, then the five benchmark datasets through `questions/collect.py`, which downloads each file from its pinned revision and fails if the bytes differ from `data/benchmarks/manifest.json`. `build.py` reruns every step in order, checks every formula in the page's own engine and, on Windows with Excel, recalculates the workbook in Excel, then runs the tests. It writes `out/checks.json` (each check with the sha256 of the file it certifies), `reports/05-checks.md`, and embeds the results in `index.html` between `/*BUNDLED_VALUATION:start*/` and `/*BUNDLED_VALUATION:end*/`.

Release mode is the default: a missing input or a failed check stops the build and marks it failed. `--partial` or `--no-excel` allows skipped steps and labels the build partial; a partial build is never release-ready.

Requirements: Python 3.9+ with the packages in `requirements.txt` (`pywin32` only for the Excel check), and Node 18+.

## Steps

| File | What it does |
|---|---|
| `lib/page.mjs` | Loads the calculation engine and bundled workbook straight from `index.html`, so headless results match the page. |
| `measure.mjs` | Stage 1: reproduces the original $88.15, then sensitivities, joint scenarios and one-parameter reverse DCF solves. |
| `stage2_assumptions.py` | Dated CAPM build (each equity risk premium paired with its own risk-free rate), FY2026 guidance for year 1, filed history; writes `scenarios.json`. |
| `segments.py` | Regional revenue build: year-1 guidance allocated to the three segments by reported revenue times (1 + regional rate), regional rates in years 2-5, compressed to one Ginzu growth rate that keeps year-1 and year-5 revenue. |
| `scenarios.mjs` | Evaluates Bear, Base and Bull in the page engine, solves what Base needs to reach the price, and computes the two grids around Base. |
| `export_ginzu_cases.mjs`, `lib/scope.mjs` | Resolved Ginzu inputs and rows per case for the Python port; refuses a case that uses a branch the port does not model. |
| `dcf.py`, `compare_dcf.py` | The Ginzu FCFF DCF on portable-spreadsheet, compared row by row with the engine for every saved case. |
| `comps_extract.py`, `comps.py` | Peer LTM financials as filed by 29 Aug 2025, one-off charges traced to XBRL facts, EV/EBITDA quartiles with and without the peer that has an estimated quarter. |
| `precedents.py` | Control transactions with disclosed EV and trailing EBITDA (`data/precedents/deals.json`); deals without an EV bridge are context only. |
| `methods.py` | EVA restatement, dividend discount, buyout ability to pay and strategic-buyer synergies, with Summary and Sources sheets, in one workbook with the above. |
| `questions/` | `collect.py` and `extract.py` read the pinned benchmark files; `build_questions.py` builds the WD-40 questions with computed answers and a disposition for every question of the two earlier sets (`merge_inputs.json`). |
| `verify_cells.mjs`, `verify_excel.py` | Evaluate every exported formula in the page engine and in Excel against the Python value; `verify_excel.py` also checks input changes made inside Excel. |
| `build_payload.mjs`, `inject.py` | Assemble the page payload, stop on any question link that does not resolve, and embed it. |
| `compare_branches.mjs`, `ledger.py` | The M0 comparison of the two earlier implementations, and one ledger row per measured step of the merge. |

## Excel

`excel/wd40_valuation.xlsx` holds every model with live formulas, recalculated and saved by Excel; the build checks that the published file is the one it recalculated. portable-spreadsheet does not carry Python parentheses into Excel formulas, so every grouped term is wrapped in `fn.brackets()`; `reports/03-spreadsheet-spike.md` shows the failure this prevents.

## Tests

| File | What it checks |
|---|---|
| `tests/test_models.py` | Contracts on this build's artifacts: the original value, each scenario's year-1 guidance, the regional build, terminal validity, EVA, the buyout repayment rules, question provenance, and check reports tied to the files they certify. |
| `tests/review.test.mjs` | The page script in a VM: apply a saved scenario, one-step undo, the stale-value guard, reload from storage, the live reverse solve. |
| `tests/methods.test.mjs` | The exported buyout formulas with a cash shortfall, and the original workbook with terminal WACC equal to terminal growth. |
| `tests/scope.test.mjs` | Every unsupported Ginzu branch is refused at export. |

`build.py` runs them all. To run them alone after a build, from the repository root:

```bash
python -I -m unittest discover -s models/tests -v
```

```bash
node --test models/tests/review.test.mjs models/tests/methods.test.mjs models/tests/scope.test.mjs
```

## Reports

`reports/01` to `06` record each stage: the baseline and sensitivities, the dated assumptions, the spreadsheet spike, the DCF port, the checks and the questions. `07` compares the two earlier implementations, `08` is the change ledger of the merge and `09` the readout.
