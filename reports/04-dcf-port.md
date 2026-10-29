# Stage 4b: DCF port and comparison

`python -I models/dcf.py` rebuilds the Ginzu FCFF valuation on portable-spreadsheet, with an input sheet holding each case's resolved Ginzu driver values and one DCF sheet per case. `python -I models/compare_dcf.py` compares every row and year with the page engine. Tolerance, fixed before the run: absolute 1e-9, or relative 1e-9.

| Case | Values compared | First divergence | Worst relative difference | Python | Engine |
|---|---:|---|---:|---:|---:|
| base | 161 | none | 2.4e-16 | 126.299989 | 126.299989 |
| bear | 161 | none | 2.9e-16 | 82.674065 | 82.674065 |
| bull | 161 | none | 2.2e-16 | 205.006754 | 205.006754 |
| original | 161 | none | 1.6e-16 | 88.150296 | 88.150296 |

## Why the earlier replica gave $88.06

The quick replica written during planning funded each year's growth with that year's revenue change. The workbook funds year t with the change from t to t+1. Re-running a plain replica both ways on the original inputs:

| Case | Workbook timing (t to t+1) | Same-year timing (t-1 to t) |
|---|---:|---:|
| original | $88.1503 | $88.0636 |
| bear | $82.6741 | $83.0367 |
| base | $126.3000 | $126.5962 |
| bull | $205.0068 | $205.1387 |

With workbook timing the replica returns the engine's value. Same-year timing lowers the original case to about $88.06, the figure the earlier replica produced, so the timing explains the gap. Rounding does not.

## Not ported

Net operating losses, the distress adjustment, employee option dilution and the trapped-cash haircut. Every case keeps these switched off (Input sheet B51, B61, B37 and B70 are No), and the engine values match without them.
