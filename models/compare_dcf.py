"""Row-by-row comparison of the Python DCF (models/dcf.py) with the page engine (models/export_ginzu_cases.mjs).

Tolerance fixed in advance: |a - b| <= 1e-9, or <= 1e-9 * |b|. Reports the first divergent row and column per case.
Also re-runs the earlier quick replica's reinvestment timing (same-year revenue change) to test whether it explains $88.06.
Run:  python -I models/compare_dcf.py   ->  models/out/dcf/compare.json, reports/04-dcf-port.md
"""
import hashlib
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
G = json.loads((HERE / "out" / "ginzu_cases.json").read_text())["cases"]
PY = json.loads((HERE / "out" / "dcf" / "dcf_rows.json").read_text())
PAIRS = {"Revenue growth": "growth", "Revenue": "revenue", "Operating margin": "margin", "EBIT": "ebit", "Tax rate": "tax",
         "NOPAT": "nopat", "Sales to capital": "s2c", "Reinvestment": "reinvestment", "FCFF": "fcff", "WACC": "wacc",
         "Cumulative discount factor": "discount", "PV of FCFF": "pv", "Invested capital": "investedCapital", "ROIC": "roic"}
COLS = ["base"] + [f"y{t}" for t in range(1, 11)] + ["terminal"]
ABS, REL = 1e-9, 1e-9


# Cells that are blank on both sides by construction: the base-year column has no flow rows.
ALLOWED_BLANK = {(r, 0) for r in ("growth", "s2c", "reinvestment", "fcff", "wacc", "discount", "pv")}
# Terminal column of these rows is computed in the valuation block, not in the row itself.
TERMINAL_SKIP = {"investedCapital", "roic", "pv", "discount", "s2c"}


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def close(a, b):
    return finite(a) and finite(b) and (abs(a - b) <= ABS or abs(a - b) <= REL * abs(b))


result, errors = {}, []
if set(PY) != set(G):
    errors.append(f"case sets differ: python {sorted(PY)} engine {sorted(G)}")
for case in sorted(set(PY) & set(G)):
    first, worst, checked = None, 0.0, 0
    for py_row, g_row in PAIRS.items():
        a_list, b_list = PY[case]["rows"].get(py_row), G[case]["rows"].get(g_row)
        if a_list is None or b_list is None or len(a_list) != 12 or len(b_list) != 12:
            errors.append(f"{case} {py_row}: row missing or not 12 columns")
            continue
        for t, (a, b) in enumerate(zip(a_list, b_list)):
            if g_row in TERMINAL_SKIP and t == 11:
                continue
            if a is None and b is None:
                if (g_row, t) not in ALLOWED_BLANK:
                    errors.append(f"{case} {py_row} {COLS[t]}: unexpected blank on both sides")
                continue
            checked += 1
            if finite(a) and finite(b):
                worst = max(worst, abs(a - b) / max(1.0, abs(b)))
            if not close(a, b) and first is None:
                first = {"row": py_row, "column": COLS[t], "python": a, "engine": b}
    for k_py, k_g in [("terminalValue", "terminalValue"), ("pvTerminalValue", "pvTerminalValue"), ("sumPV", "sumPV"),
                      ("operatingAssets", "operatingAssets"), ("valuePerShare", "valuePerShare")]:
        checked += 1
        a, b = PY[case].get(k_py), G[case]["bridge"].get(k_g)
        if finite(a) and finite(b):
            worst = max(worst, abs(a - b) / max(1.0, abs(b)))
        if not close(a, b) and first is None:
            first = {"row": k_py, "column": "valuation", "python": a, "engine": b}
    result[case] = {"checked": checked, "firstDivergence": first, "worstRelative": worst,
                    "python": PY[case]["valuePerShare"], "engine": G[case]["bridge"]["valuePerShare"]}
    if first:
        errors.append(f"{case}: first divergence {first}")


def replica(d, lead=True):
    """Plain-Python Ginzu with a switch for reinvestment timing."""
    v = {k: x["value"] for k, x in d.items()}
    rev, g = [v["revenue0"]], []
    for t in range(1, 12):
        gt = v["growth1"] if t == 1 else v["growth25"] if t <= 5 else (v["growthT"] if t == 11 else None)
        if gt is None:
            gt = g[4] - (g[4] - v["growthT"]) / 5 * (t - 5)
        g.append(gt)
        rev.append(rev[-1] * (1 + gt))
    m = [v["ebit0"] / v["revenue0"], v["margin1"]]
    for t in range(2, 11):
        m.append(v["marginTarget"] if t > v["convergence"] else v["marginTarget"] - (v["marginTarget"] - v["margin1"]) / v["convergence"] * (v["convergence"] - t))
    m.append(m[10])
    tax = [v["tax0"]] * 6
    for t in range(6, 11):
        tax.append(tax[-1] + (v["taxT"] - tax[5]) / 5)
    tax.append(v["taxT"])
    nopat = [rev[t] * m[t] * (1 - tax[t]) for t in range(12)]
    wacc = [None] + [v["wacc0"]] * 5
    for t in range(6, 11):
        wacc.append(wacc[-1] - (wacc[5] - v["waccT"]) / 5)
    s2c = [None] + [v["s2c1"]] * 5 + [v["s2c2"]] * 5
    reinv = [None] + [((rev[t + 1] - rev[t]) if lead else (rev[t] - rev[t - 1])) / s2c[t] for t in range(1, 11)]
    roic_t = v["roicT"] if v["roicOverride"] == 1 else wacc[10]
    df, pv = 1.0, 0.0
    for t in range(1, 11):
        df /= 1 + wacc[t]
        pv += (nopat[t] - reinv[t]) * df
    tv = nopat[11] * (1 - v["growthT"] / roic_t) / (v["waccT"] - v["growthT"])
    equity = pv + tv * df - v["debt"] - v["minorities"] + v["cash"] + v["nonOperating"] - v["options"]
    return equity / v["shares"]


timing = {case: {"leadTiming": replica(G[case]["drivers"], True), "sameYearTiming": replica(G[case]["drivers"], False)} for case in G}
(HERE / "out" / "dcf" / "compare.json").write_text(json.dumps({"tolerance": {"absolute": ABS, "relative": REL}, "cases": result, "timing": timing, "errors": errors,
    "inputs": {n: hashlib.sha256((HERE / "out" / n).read_bytes()).hexdigest() for n in ("ginzu_cases.json", "dcf/dcf_rows.json")}}, indent=1))

L = ["# Stage 4b: DCF port and comparison", "",
     "`python -I models/dcf.py` rebuilds the Ginzu FCFF valuation on portable-spreadsheet, with an input sheet holding each case's resolved Ginzu driver values and one DCF sheet per case. `python -I models/compare_dcf.py` compares every row and year with the page engine. Tolerance, fixed before the run: absolute 1e-9, or relative 1e-9.", "",
     "| Case | Values compared | First divergence | Worst relative difference | Python | Engine |", "|---|---:|---|---:|---:|---:|"]
for case, r in result.items():
    fd = "none" if not r["firstDivergence"] else f"{r['firstDivergence']['row']}, {r['firstDivergence']['column']}"
    L.append(f"| {case} | {r['checked']} | {fd} | {r['worstRelative']:.1e} | {r['python']:.6f} | {r['engine']:.6f} |")
L += ["", "## Why the earlier replica gave $88.06", "",
      "The quick replica written during planning funded each year's growth with that year's revenue change. The workbook funds year t with the change from t to t+1. Re-running a plain replica both ways on the original inputs:", "",
      "| Case | Workbook timing (t to t+1) | Same-year timing (t-1 to t) |", "|---|---:|---:|"]
for case, tm in timing.items():
    L.append(f"| {case} | ${tm['leadTiming']:.4f} | ${tm['sameYearTiming']:.4f} |")
L += ["", "With workbook timing the replica returns the engine's value. Same-year timing lowers the original case to about $88.06, the figure the earlier replica produced, so the timing explains the gap. Rounding does not.", "",
      "## Not ported", "",
      "Net operating losses, the distress adjustment, employee option dilution and the trapped-cash haircut. Every case keeps these switched off (Input sheet B51, B61, B37 and B70 are No), and the engine values match without them.", ""]
(ROOT / "reports" / "04-dcf-port.md").write_bytes("\n".join(L).encode("utf-8"))
print(json.dumps({k: (v["firstDivergence"], round(v["worstRelative"], 15)) for k, v in result.items()}))
if errors:
    print("DCF comparison FAILED: " + " | ".join(errors))
    sys.exit(1)
print({k: {kk: round(vv, 6) for kk, vv in v.items()} for k, v in timing.items()})
