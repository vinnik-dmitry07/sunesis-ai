"""FCFF DCF ported from Damodaran's Simple Ginzu, built on portable-spreadsheet so it exports to Excel with formulas.

Inputs are a labelled snapshot of the resolved Ginzu driver values for each case (models/out/ginzu_cases.json,
produced by node models/export_ginzu_cases.mjs). The structure follows the Ginzu "Valuation output" sheet:
reinvestment in year t funds the revenue change from t to t+1; growth, tax and WACC fade over years 6-10;
terminal reinvestment is terminal growth / terminal ROIC x terminal NOPAT. Not ported, because every case
here keeps them off: net operating losses, the distress adjustment, option dilution, trapped cash.

Run:  python -I models/dcf.py   ->  models/out/dcf/wd40_dcf.xlsx, models/out/dcf/dcf_cells.json, models/out/dcf/dcf_rows.json
"""
import json
import pathlib
import sys

import portable_spreadsheet as ps

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib.pss import export_cells, write_xlsx  # noqa: E402

OUT = HERE / "out" / "dcf"
CASES = ["original", "bear", "base", "bull"]
SRC = json.loads((HERE / "out" / "ginzu_cases.json").read_text())
# --variant driver:case=value  rebuilds with one input changed, into out/dcf/variant (used by the Excel input-change check)
if "--variant" in sys.argv:
    spec = sys.argv[sys.argv.index("--variant") + 1]
    key, rest = spec.split(":")
    case_name, val = rest.split("=")
    SRC["cases"][case_name]["drivers"][key]["value"] = float(val)
    OUT = OUT / "variant"
OUT.mkdir(parents=True, exist_ok=True)

INPUT_ROWS = ["revenue0", "ebit0", "investedCapital0", "debt", "cash", "minorities", "nonOperating", "options", "shares",
              "growth1", "growth25", "growthT", "margin1", "marginTarget", "convergence", "tax0", "taxT", "s2c1", "s2c2",
              "wacc0", "waccT", "roicOverride", "roicT"]
first = SRC["cases"]["original"]["drivers"]
inputs = ps.Sheet.create_new_sheet(len(INPUT_ROWS), len(CASES), name="Scenario inputs",
                                   rows_labels=[f"{first[k]['label']} ({first[k]['unit']})" for k in INPUT_ROWS],
                                   columns_labels=[SRC["cases"][c]["label"] for c in CASES])
for j, c in enumerate(CASES):
    for i, k in enumerate(INPUT_ROWS):
        v = SRC["cases"][c]["drivers"][k]["value"]
        inputs.iloc[i, j] = float(v)
IDX = {k: i for i, k in enumerate(INPUT_ROWS)}

ROWS = ["Year", "Revenue growth", "Revenue", "Operating margin", "EBIT", "Tax rate", "NOPAT", "Sales to capital", "Reinvestment",
        "FCFF", "WACC", "Cumulative discount factor", "PV of FCFF", "Invested capital", "ROIC",
        "Terminal ROIC", "Terminal value", "PV of terminal value", "Sum of PV of FCFF, years 1-10", "Operating assets",
        "Debt", "Cash", "Minority interests", "Non-operating assets", "Equity value", "Value of employee options",
        "Common equity", "Shares", "Value per share", "PV of terminal value / operating assets"]
R = {k: i for i, k in enumerate(ROWS)}
COLS = ["Base year"] + [f"Year {t}" for t in range(1, 11)] + ["Terminal year"]


def build(case_index, label):
    sh = ps.Sheet.create_new_sheet(len(ROWS), len(COLS), name=f"DCF {label}", rows_labels=ROWS, columns_labels=COLS)
    f, B = sh.fn, sh.fn.brackets
    one = f.const(1)

    def inp(name):
        return f.cross_reference(inputs.iloc[IDX[name], case_index], inputs)

    cell = lambda row, col: sh.iloc[R[row], col]  # noqa: E731
    for t in range(0, 11):
        sh.iloc[R["Year"], t] = float(t)
    # revenue growth
    sh.iloc[R["Revenue growth"], 1] = inp("growth1")
    for t in range(2, 6):
        sh.iloc[R["Revenue growth"], t] = inp("growth25")
    sh.iloc[R["Revenue growth"], 11] = inp("growthT")
    g5, gT = cell("Revenue growth", 5), cell("Revenue growth", 11)
    for k, t in enumerate(range(6, 11), start=1):
        sh.iloc[R["Revenue growth"], t] = g5 - B(B(g5 - gT) / f.const(5)) * f.const(k)
    # revenue
    sh.iloc[R["Revenue"], 0] = inp("revenue0")
    for t in range(1, 12):
        sh.iloc[R["Revenue"], t] = cell("Revenue", t - 1) * B(one + cell("Revenue growth", t))
    # margin and EBIT
    sh.iloc[R["EBIT"], 0] = inp("ebit0")
    sh.iloc[R["Operating margin"], 0] = cell("EBIT", 0) / cell("Revenue", 0)
    sh.iloc[R["Operating margin"], 1] = inp("margin1")
    m1, target, conv = cell("Operating margin", 1), inp("marginTarget"), inp("convergence")
    for t in range(2, 11):
        yr = cell("Year", t)
        sh.iloc[R["Operating margin"], t] = f.conditional(yr > conv, target, target - B(B(target - m1) / conv) * B(conv - yr))
    sh.iloc[R["Operating margin"], 11] = cell("Operating margin", 10)
    for t in range(1, 12):
        sh.iloc[R["EBIT"], t] = cell("Operating margin", t) * cell("Revenue", t)
    # tax
    sh.iloc[R["Tax rate"], 0] = inp("tax0")
    for t in range(1, 6):
        sh.iloc[R["Tax rate"], t] = cell("Tax rate", t - 1)
    sh.iloc[R["Tax rate"], 11] = inp("taxT")
    for t in range(6, 11):
        sh.iloc[R["Tax rate"], t] = cell("Tax rate", t - 1) + B(cell("Tax rate", 11) - cell("Tax rate", 5)) / f.const(5)
    # NOPAT (no net operating losses in any case)
    for t in range(0, 11):
        ebit = cell("EBIT", t)
        sh.iloc[R["NOPAT"], t] = f.conditional(ebit > f.const(0), ebit * B(one - cell("Tax rate", t)), ebit)
    sh.iloc[R["NOPAT"], 11] = cell("EBIT", 11) * B(one - cell("Tax rate", 11))
    # sales to capital, reinvestment
    for t in range(1, 11):
        sh.iloc[R["Sales to capital"], t] = inp("s2c1") if t <= 5 else inp("s2c2")
        sh.iloc[R["Reinvestment"], t] = B(cell("Revenue", t + 1) - cell("Revenue", t)) / cell("Sales to capital", t)
    # WACC and discounting
    for t in range(1, 6):
        sh.iloc[R["WACC"], t] = inp("wacc0")
    sh.iloc[R["WACC"], 11] = inp("waccT")
    for t in range(6, 11):
        sh.iloc[R["WACC"], t] = cell("WACC", t - 1) - B(cell("WACC", 5) - cell("WACC", 11)) / f.const(5)
    sh.iloc[R["Cumulative discount factor"], 1] = one / B(one + cell("WACC", 1))
    for t in range(2, 11):
        sh.iloc[R["Cumulative discount factor"], t] = cell("Cumulative discount factor", t - 1) * B(one / B(one + cell("WACC", t)))
    # terminal ROIC, terminal reinvestment, FCFF
    sh.iloc[R["Terminal ROIC"], 0] = f.conditional(inp("roicOverride") == f.const(1), inp("roicT"), cell("WACC", 10))
    gt_cell = cell("Revenue growth", 11)
    sh.iloc[R["Reinvestment"], 11] = f.conditional(gt_cell > f.const(0), B(gt_cell / cell("Terminal ROIC", 0)) * cell("NOPAT", 11), f.const(0))
    for t in range(1, 12):
        sh.iloc[R["FCFF"], t] = cell("NOPAT", t) - cell("Reinvestment", t)
    for t in range(1, 11):
        sh.iloc[R["PV of FCFF"], t] = cell("FCFF", t) * cell("Cumulative discount factor", t)
    # invested capital and ROIC
    sh.iloc[R["Invested capital"], 0] = inp("investedCapital0")
    sh.iloc[R["ROIC"], 0] = cell("NOPAT", 0) / cell("Invested capital", 0)
    for t in range(1, 11):
        sh.iloc[R["Invested capital"], t] = cell("Invested capital", t - 1) + cell("Reinvestment", t)
        sh.iloc[R["ROIC"], t] = cell("NOPAT", t) / cell("Invested capital", t - 1)
    # valuation, in the base-year column
    c0 = lambda row: sh.iloc[R[row], 0]  # noqa: E731
    sh.iloc[R["Terminal value"], 0] = cell("FCFF", 11) / B(cell("WACC", 11) - cell("Revenue growth", 11))
    sh.iloc[R["PV of terminal value"], 0] = c0("Terminal value") * cell("Cumulative discount factor", 10)
    sh.iloc[R["Sum of PV of FCFF, years 1-10"], 0] = sh.iloc[R["PV of FCFF"], 1:11].sum()
    sh.iloc[R["Operating assets"], 0] = c0("PV of terminal value") + c0("Sum of PV of FCFF, years 1-10")
    for row, name in [("Debt", "debt"), ("Cash", "cash"), ("Minority interests", "minorities"), ("Non-operating assets", "nonOperating"),
                      ("Value of employee options", "options"), ("Shares", "shares")]:
        sh.iloc[R[row], 0] = inp(name)
    sh.iloc[R["Equity value"], 0] = c0("Operating assets") - c0("Debt") - c0("Minority interests") + c0("Cash") + c0("Non-operating assets")
    sh.iloc[R["Common equity"], 0] = c0("Equity value") - c0("Value of employee options")
    sh.iloc[R["Value per share"], 0] = c0("Common equity") / c0("Shares")
    sh.iloc[R["PV of terminal value / operating assets"], 0] = c0("PV of terminal value") / c0("Operating assets")
    return sh


sheets = [inputs] + [build(j, SRC["cases"][c]["label"]) for j, c in enumerate(CASES)]
write_xlsx(sheets, OUT / "wd40_dcf.xlsx")
cells = export_cells(sheets)
(OUT / "dcf_cells.json").write_text(json.dumps(cells, indent=1))

rows_out = {}
for j, c in enumerate(CASES):
    sh = sheets[j + 1]
    get = lambda r, t: sh.iloc[R[r], t].value  # noqa: E731
    rows_out[c] = {
        "rows": {k: [get(k, t) for t in range(12)] for k in ROWS[:15]},
        "valuePerShare": get("Value per share", 0), "terminalValue": get("Terminal value", 0),
        "pvTerminalValue": get("PV of terminal value", 0), "sumPV": get("Sum of PV of FCFF, years 1-10", 0),
        "operatingAssets": get("Operating assets", 0), "terminalROIC": get("Terminal ROIC", 0), "sheet": sh.name,
    }
(OUT / "dcf_rows.json").write_text(json.dumps(rows_out, indent=1, default=lambda x: None))
print({c: round(v["valuePerShare"], 6) for c, v in rows_out.items()})
