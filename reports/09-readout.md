# Readout: merging the two WD-40 implementations

Two implementations existed: `main` at `70b6ba8` (PR #1, then live) and `valuation-range` at `aa9dce5`. Both kept Damodaran's workbook, the 70 proposals and the page engine unchanged, and both gave $88.15029580134913 for the original case. This report summarizes how they were merged into one page, one workbook and one question set, and what each step changed. Details are in `07-m0-comparison.md` (first comparison) and `08-change-ledger.md` (one measured build per step).

## States

Values per share. Each delta in the ledger is against the step before and depends on the order of the steps; the deltas are not independent effects.

| State | Original | Bear | Base | Bull | Comps median | Precedents median | DDM Base | LBO Base | Strategic Base | Why it changed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `main` 70b6ba8 | $88.15 | $80.58 | $159.17 | $258.66 | none | not comparable | not comparable | not comparable | not comparable | Starting point. Comps had no observations; precedents used announced consideration; DDM and LBO rested on rates that were not CAPM estimates. |
| `valuation-range` aa9dce5, merge checkpoint | $88.15 | $80.91 | $126.30 | $205.26 | $89.58 | $95.08 | $121.42 | $76.15 | $165.41 | Merge with no assumption change; reproduces `valuation-range` exactly. |
| Year-1 margin fix | $88.15 | $82.67 | $126.30 | $205.01 | $89.58 | $95.08 | $121.42 | $76.15 | $165.41 | Bear and Bull year-1 margins had divided their guided operating income by Base sales. |
| Regional growth | $88.15 | $80.60 | $125.34 | $214.28 | $89.58 | $95.08 | $121.42 | $75.86 | $164.06 | Years 2-5 growth from a regional build (Bear 3.25%, Base 5.81%, Bull 7.98%) instead of flat 4%, 6%, 7%. |
| Method bases | $88.15 | $70.37 | $125.34 | $214.28 | $89.58 | $90.36 | $121.42 | $75.86 | $164.06 | Bear's equity risk premium paired with its own risk-free rate; Waterpik moved to context for lack of an EV bridge. |
| Buyout rules | $88.15 | $70.37 | $125.34 | $214.28 | $89.58 | $90.36 | $121.42 | $74.87 | $164.06 | Mandatory 1% amortization first, sweep capped by debt and by cash above a $30m minimum, a shortfall makes the case infeasible, 2% exit fee. |
| Questions and provenance (final) | $88.15 | $70.37 | $125.34 | $214.28 | $89.58 | $90.36 | $121.42 | $74.87 | $164.06 | No value changed. |

The reverse DCF, the review behaviour and the workbook layout changed no saved value.

## Errors found and fixed

In `main`:

- Discount rates were analyst assumptions with no CAPM behind them. The merged cases use the dated CAPM build.
- Comps had no observations and precedents used announced consideration rather than enterprise value. Both are replaced by `valuation-range`'s filed data.
- The workbook was never recalculated in Excel. The merged build recalculates it, saves a copy, reopens it and compares every formula.
- The measurement hash depended on working-tree line endings. The comparison reads committed bytes.
- Several question links pointed at the wrong cells (R&D history at `R& D converter!B6`-`B9`, the debt bridge at `Valuation output!B26`, which is minority interests). The merged questions link the right cells, and the build stops on a link that does not resolve.

In `valuation-range`:

- The year-1 margin bug above.
- Bear used Damodaran's premium computed against an adjusted 3.96% risk-free rate together with the 4.23% Treasury yield. It now uses the smoothed premium, which is computed against the same 4.23%.
- `compare_dcf.py` and `inject.py --check` reported mismatches but exited 0; the Excel check was optional; method statuses were set before any check ran. All three now fail the build, and statuses come from check reports matched by sha256.
- FY2026 XBRL facts leaked into the Stage 2 history table. Facts are now filtered by filing date.
- A negative cash flow in the buyout could become a negative repayment that raised debt.
- Benchmark downloads were unpinned, two FinLFQA origins were chosen by position, 16 questions had no evidence, the July 2026 guidance cut was attributed to the FY2026 10-K, and the EVA link opened nothing.

## Checks of the final build

- 1,761 workbook formulas evaluated by the page engine and recalculated by Excel against their Python values; the largest relative difference is 5e-13. The 1,661 and 2,038 counts of the earlier branches describe their own artifacts.
- Three input changes made inside Excel, each matching a fresh Python build of the same change on 684 formulas.
- The Python DCF matches the engine row by row for all four cases.
- 15 Python contract tests and 17 Node tests pass in the build.
- Readiness: release-ready (`05-checks.md`).

## Excluded or qualified observations

- Precedents: deals whose EBITDA is a forecast or whose price has no disclosed bridge to enterprise value (Waterpik among them) are shown but left out of the range.
- Comps: one quarter of Quaker Houghton's amortization is estimated from the adjacent quarters; without that peer the range is $82.45 / $111.35 / $136.30. Company-defined adjustments other than tagged impairments, restructuring and a divestiture loss are not added back; an RPM gain whose placement could not be confirmed is left in.
- Questions: of `valuation-range`'s 47, all are kept. Of `main`'s 30, 10 became questions of their own and 20 were merged into matching ones. None was excluded. The disposition of each is in `06-questions.md`.

## Limits

- The Python port covers the Ginzu branches the cases use; other branches are refused at export.
- Regional rates, margin targets, terminal returns and the long-run tax rate are analyst assumptions.
- About $17.0m of FY2025 revenue sits outside the guidance base, and the release does not split it by segment. Taking all of it from the Americas would change Base growth in years 2-5 by 0.05 points.
- Reuse rights of the benchmark datasets are not established.
- The reported FY2026 net sales of $688.0m do not resolve the guidance-basis question.
