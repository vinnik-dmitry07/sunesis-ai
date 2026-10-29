# Sunesis: WD-40 valuation review

`index.html` is a self-contained review of WD-40 Company (WDFC) built on Aswath Damodaran's FCFF Simple Ginzu workbook. Live page: https://vinnik-dmitry07.github.io/sunesis-ai/

The case is a retrospective FY2025 review. The reference price is the $216.04 Nasdaq close on 29 Aug 2025. Inputs use filings up to the FY2025 10-K of 27 Oct 2025. Anything published later is shown apart, labelled, and never enters a valuation.

## Why the original case gives $88.15

The 70 proposed inputs of the original case give $88.15029580134913 a share, in the page and in the Python port. That is correct arithmetic of inputs the case itself labels as placeholders: a WACC of 9% fading to 8% with no CAPM behind it, a flat 17.1% operating margin, 5% growth, and a return on new capital after year 10 equal to the cost of capital.

The saved scenarios replace them with dated inputs: a CAPM cost of capital from the 29 Aug 2025 Treasury yield and Damodaran's September 2025 equity risk premiums, FY2026 guidance for year 1, and a regional build for years 2-5.

| | Bear | Base | Bull |
|---|---:|---:|---:|
| DCF value per share | $70.37 | $125.34 | $214.28 |

Starting from Base, the price needs one of: a 5.40% WACC in every year, a 31.1% operating margin by year 5, or 19.0% revenue growth in years 2-5. No return on new capital reaches it on its own. The price is the reference for that comparison; how close a case lands to it is not how the case is judged.

## The football field

Each method shows a Bear, Base and Bull value from its own named inputs, drawn against the price, the 52-week range and two dated analyst targets. A scenario-based field fits this case because every spread traces to inputs the page lists. Probabilities for the cases would be invented, so there is no probability-weighted view. Buyer-specific values appear as their own rows (buyout and strategic buyer). Interactive sensitivity is on the page as measured one-input changes, two grids around Base and a live reverse solve on your own review.

| Method | Bear | Base | Bull | Basis |
|---|---:|---:|---:|---|
| DCF | $70.37 | $125.34 | $214.28 | Ginzu FCFF with the saved scenarios |
| Trading comparables | $88.98 | $89.58 | $133.12 | EV/EBITDA quartiles of five peers on 29 Aug 2025 |
| Precedent transactions | $80.87 | $90.36 | $114.89 | Control deals with disclosed EV and trailing EBITDA |
| Dividend discount | $72.68 | $121.42 | $198.76 | CAPM cost of equity of each scenario |
| Buyout, ability to pay | $65.10 | $74.87 | $106.28 | Highest price that meets the sponsor's target return |
| Strategic buyer | $151.25 | $164.06 | $181.38 | Base DCF plus synergies at the lowest, median and highest share of revenue announced in precedent deals |

WD-40's own EV/EBITDA history ($214.37 to $281.93) is shown as context. EVA restates each DCF exactly and serves as a consistency check. APV is left out: with debt at 2.9% of capital, the tax shield it would separate is too small to move the range.

## Use

Open `index.html`, or the live page. Accept or edit each input, apply a saved scenario (one undo restores your previous review), and open any method for its inputs and sources. The review is kept in your browser's storage.

The workbook link downloads `models/excel/wd40_valuation.xlsx`: the saved scenarios and every method with live formulas, plus Summary and Sources sheets. Edits you make on the page are not in it.

## Rebuild

Restore the raw files that are not committed (peer SEC facts, then the five benchmark datasets from their pinned revisions):

```bash
bash models/data/fetch.sh
```

Install the Python packages:

```bash
python -m pip install -r models/requirements.txt
```

Rebuild every model, check it, and embed the result in `index.html`:

```bash
python -I models/build.py
```

The default release mode stops on any missing input or failed check. The Excel steps need Windows with Microsoft Excel; `--no-excel` (or `--partial`) runs without them and labels the build partial. The result is in `reports/05-checks.md`. Step-by-step details are in [models/README.md](models/README.md).

## Checks in the current build

- 1,761 workbook formulas are evaluated by the page's engine and recalculated by Excel, each compared with its Python value (largest relative difference 5e-13).
- Three input changes made inside the Excel file (a Base WACC, a Bull growth rate and a Bear terminal growth rate) recalculate to the values of a fresh Python build of the same change, 684 formulas each.
- The Python DCF matches the page engine row by row for the original case and the three scenarios.
- 15 Python contract tests and 17 Node tests run in every build: the original value, each scenario's year-1 guidance, the regional build, the buyout repayment rules, question provenance, check reports tied to the files they certify, and the page's apply, undo, reload and reverse solve.

## Diligence questions

57 questions under 11 topics, adapted from FinanceBench, FinLFQA, FinCausal and PE Bench. FinTextQA's public questions cover bank regulation and none apply. Following The Mom Test, each topic splits a judgement into questions about specific past facts, then asks which model input those facts test. Answers are computed from filings, the original case and the models. Benchmark files are pinned by revision and sha256 in `models/data/benchmarks/manifest.json`; their reuse rights are not established, so the raw files are not committed.

## Limits

- The Python port covers the Ginzu branches the cases use. A case with a net operating loss, distress adjustment, option valuation, trapped cash or a reinvestment lag other than one year is refused at export.
- The regional growth rates and the margin, terminal-return and long-run tax targets are analyst assumptions, labelled as such.
- The guidance base leaves out about $17.0m of FY2025 revenue that the release does not split by segment.
- Comps and precedent quartiles enter the workbook as computed constants; changing a peer or a deal needs a rebuild. One Quaker Houghton quarter of amortization is estimated; the page also shows the range without that peer.
- Later information (the FY2026 10-K and the July 2026 guidance revision) is shown apart. The reported FY2026 net sales of $688.0m are not on the guidance basis, so they do not resolve the guidance question.

## Reports

| Report | Contents |
|---|---|
| `reports/01-baseline-and-sensitivities.md` | The original $88.15, one-input sensitivities and reverse solves |
| `reports/02-assumptions.md` | Dated inputs of each scenario and their sources |
| `reports/03-spreadsheet-spike.md` | Why every grouped term in the workbook is bracketed |
| `reports/04-dcf-port.md` | The Python DCF against the engine |
| `reports/05-checks.md` | The last build and its readiness |
| `reports/06-questions.md` | Questions, answers, origins and the merge of the two earlier sets |
| `reports/07-m0-comparison.md` | Comparison of the two earlier implementations |
| `reports/08-change-ledger.md` | Values after each measured step of the merge |
| `reports/09-readout.md` | Summary of the merge: states, errors fixed, limits |

The original workbook's attribution and its author's permission statement remain in the page. No license over third-party workbooks, source documents or datasets is asserted.
