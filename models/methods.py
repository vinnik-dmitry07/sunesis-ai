"""EVA, dividend discount, LBO ability-to-pay and strategic-buyer synergies, linked to the DCF sheets.

All four sit in one workbook with the DCF so every cross-sheet formula survives the Excel export.
- EVA restates each DCF case as invested capital plus the present value of economic profit. The difference
  to the DCF operating value is computed, not forced; it is a consistency check, not a second opinion.
- DDM values dividends only (FY2025 buybacks were small next to dividends), with the same cost of equity
  as the Stage 2 CAPM build and a terminal payout tied to terminal return on equity.
- LBO: sources and uses, Base operating case from the DCF, 5-year hold, single entry and single exit cash
  flow, so IRR = MOIC^(1/5) - 1 holds. Exit multiples are fixed per scenario (peer quartiles), so IRR
  falls as the entry price rises. Ability to pay is found on a $5 grid and refined by bisection.
- Synergies: Base standalone value plus the present value of after-tax cost synergies net of one-time costs.
Run:  python -I models/methods.py  ->  models/out/valuation_book/*, models/out/methods_core.json
"""
import json
import pathlib
import sys

import portable_spreadsheet as ps

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dcf  # noqa: E402
import comps  # noqa: E402  (builds the comps sheets on import)
import precedents  # noqa: E402
from lib.pss import export_cells, write_xlsx  # noqa: E402

OUT = HERE / "out" / "valuation_book"
OUT.mkdir(parents=True, exist_ok=True)
A = json.loads((HERE / "out" / "stage2_assumptions.json").read_text())
COMPS = json.loads((HERE / "out" / "methods_comps.json").read_text())["methods"][0]
R = dcf.R
SH, CASE_SHEETS = dcf.build_all()
BASE = CASE_SHEETS["base"]


def link(sheet, src, row, col):
    return sheet.fn.cross_reference(src.iloc[R[row], col], src)


# ---------------------------------------------------------------- EVA
EVA_ROWS = ["NOPAT", "Opening invested capital", "WACC", "Capital charge", "Economic profit", "Cumulative discount factor", "PV of economic profit",
            "Invested capital, base year", "Sum of PV of economic profit, years 1-10", "Terminal NOPAT", "Terminal WACC", "Terminal growth", "Terminal ROIC",
            "Invested capital, year 10", "Economic profit on existing capital, terminal year", "Value of economic profit on new capital",
            "Continuing value of economic profit", "PV of continuing value", "Operating value from economic profit", "Operating value from DCF",
            "Difference (EVA minus DCF)"]
E = {k: i for i, k in enumerate(EVA_ROWS)}


def eva_sheet(case, src):
    sh = ps.Sheet.create_new_sheet(len(EVA_ROWS), 11, name=f"EVA {src.name[4:]}", rows_labels=EVA_ROWS,
                                   columns_labels=["Valuation"] + [f"Year {t}" for t in range(1, 11)])
    f, B = sh.fn, sh.fn.brackets
    c = lambda row, col: sh.iloc[E[row], col]  # noqa: E731
    for t in range(1, 11):
        sh.iloc[E["NOPAT"], t] = link(sh, src, "NOPAT", t)
        sh.iloc[E["Opening invested capital"], t] = link(sh, src, "Invested capital", t - 1)
        sh.iloc[E["WACC"], t] = link(sh, src, "WACC", t)
        sh.iloc[E["Capital charge"], t] = c("WACC", t) * c("Opening invested capital", t)
        sh.iloc[E["Economic profit"], t] = c("NOPAT", t) - c("Capital charge", t)
        sh.iloc[E["Cumulative discount factor"], t] = link(sh, src, "Cumulative discount factor", t)
        sh.iloc[E["PV of economic profit"], t] = c("Economic profit", t) * c("Cumulative discount factor", t)
    v = lambda row: sh.iloc[E[row], 0]  # noqa: E731
    sh.iloc[E["Invested capital, base year"], 0] = link(sh, src, "Invested capital", 0)
    sh.iloc[E["Sum of PV of economic profit, years 1-10"], 0] = sh.iloc[E["PV of economic profit"], 1:11].sum()
    sh.iloc[E["Terminal NOPAT"], 0] = link(sh, src, "NOPAT", 11)
    sh.iloc[E["Terminal WACC"], 0] = link(sh, src, "WACC", 11)
    sh.iloc[E["Terminal growth"], 0] = link(sh, src, "Revenue growth", 11)
    sh.iloc[E["Terminal ROIC"], 0] = link(sh, src, "Terminal ROIC", 0)
    sh.iloc[E["Invested capital, year 10"], 0] = link(sh, src, "Invested capital", 10)
    W, g, Rr, N = v("Terminal WACC"), v("Terminal growth"), v("Terminal ROIC"), v("Terminal NOPAT")
    sh.iloc[E["Economic profit on existing capital, terminal year"], 0] = N - W * v("Invested capital, year 10")
    sh.iloc[E["Value of economic profit on new capital"], 0] = N * B(g / Rr) * B(Rr - W) / B(W * B(W - g))
    sh.iloc[E["Continuing value of economic profit"], 0] = v("Economic profit on existing capital, terminal year") / W + v("Value of economic profit on new capital")
    sh.iloc[E["PV of continuing value"], 0] = v("Continuing value of economic profit") * c("Cumulative discount factor", 10)
    sh.iloc[E["Operating value from economic profit"], 0] = v("Invested capital, base year") + v("Sum of PV of economic profit, years 1-10") + v("PV of continuing value")
    sh.iloc[E["Operating value from DCF"], 0] = link(sh, src, "Operating assets", 0)
    sh.iloc[E["Difference (EVA minus DCF)"], 0] = v("Operating value from economic profit") - v("Operating value from DCF")
    return sh


eva = {c: eva_sheet(c, s) for c, s in CASE_SHEETS.items()}

# ---------------------------------------------------------------- DDM
DDM_SCEN = {  # stage-1 EPS growth, terminal ROE (None = cost of equity, no excess return), terminal growth
    "bear": {"g": 0.04, "roe": None, "gT": 0.020},
    "base": {"g": 0.06, "roe": 0.15, "gT": 0.025},
    "bull": {"g": 0.08, "roe": 0.20, "gT": 0.030},
}
EPS0, DPS0 = 5.82, 3.76  # FY2025 non-GAAP diluted EPS (8-K 22 Oct 2025); quarterly dividend $0.94 x 4
DDM_ROWS = ["Year", "EPS", "Payout ratio", "Dividend per share", "Discount factor", "PV of dividend",
            "Cost of equity", "EPS growth, years 1-10", "Terminal growth", "Terminal return on equity", "Terminal payout ratio",
            "Dividend, year 11", "Terminal value, end of year 10", "PV of terminal value", "Sum of PV of dividends, years 1-10", "Value per share"]
D = {k: i for i, k in enumerate(DDM_ROWS)}


def ddm_sheet(k):
    s = DDM_SCEN[k]
    ke = A["waccCases"][k]["costOfEquity"]
    sh = ps.Sheet.create_new_sheet(len(DDM_ROWS), 11, name=f"DDM {k.title()}", rows_labels=DDM_ROWS,
                                   columns_labels=["FY2025 / inputs"] + [f"Year {t}" for t in range(1, 11)])
    f, B = sh.fn, sh.fn.brackets
    one = f.const(1)
    c = lambda row, col: sh.iloc[D[row], col]  # noqa: E731
    sh.iloc[D["Cost of equity"], 0] = ke
    sh.iloc[D["EPS growth, years 1-10"], 0] = s["g"]
    sh.iloc[D["Terminal growth"], 0] = s["gT"]
    sh.iloc[D["Terminal return on equity"], 0] = s["roe"] if s["roe"] else ke
    sh.iloc[D["EPS"], 0] = EPS0
    sh.iloc[D["Dividend per share"], 0] = DPS0
    sh.iloc[D["Payout ratio"], 0] = c("Dividend per share", 0) / c("EPS", 0)
    for t in range(0, 11):
        sh.iloc[D["Year"], t] = float(t)
    for t in range(1, 11):
        sh.iloc[D["EPS"], t] = c("EPS", t - 1) * B(one + c("EPS growth, years 1-10", 0))
        sh.iloc[D["Payout ratio"], t] = B(c("Payout ratio", t - 1))
        sh.iloc[D["Dividend per share"], t] = c("EPS", t) * c("Payout ratio", t)
        sh.iloc[D["Discount factor"], t] = one / B(one + c("Cost of equity", 0)) ** c("Year", t)
        sh.iloc[D["PV of dividend"], t] = c("Dividend per share", t) * c("Discount factor", t)
    v = lambda row: sh.iloc[D[row], 0]  # noqa: E731
    sh.iloc[D["Terminal payout ratio"], 0] = one - v("Terminal growth") / v("Terminal return on equity")
    sh.iloc[D["Dividend, year 11"], 0] = c("EPS", 10) * B(one + v("Terminal growth")) * v("Terminal payout ratio")
    sh.iloc[D["Terminal value, end of year 10"], 0] = v("Dividend, year 11") / B(v("Cost of equity") - v("Terminal growth"))
    sh.iloc[D["PV of terminal value"], 0] = v("Terminal value, end of year 10") * c("Discount factor", 10)
    sh.iloc[D["Sum of PV of dividends, years 1-10"], 0] = sh.iloc[D["PV of dividend"], 1:11].sum()
    sh.iloc[D["Value per share"], 0] = v("Sum of PV of dividends, years 1-10") + v("PV of terminal value")
    return sh


ddm = {k: ddm_sheet(k) for k in DDM_SCEN}

# ---------------------------------------------------------------- LBO
SOFR = json.loads((HERE / "data" / "rates" / "nyfed_sofr_2025-08-25_2025-09-02.json").read_text())
SOFR_0829 = [r["percentRate"] for r in SOFR["refRates"] if r["effectiveDate"] == "2025-08-29"][0] / 100
EBITDA25 = 103.793 + 8.191
RND_ADJ_PCT = (106.05966666666667 - 103.793) / 619.985
DA_PCT = 8.191 / 619.985
q = COMPS["quartiles"]["evToEbitda"]
LBO_SCEN = {  # exit EV/EBITDA from the peer quartiles, sponsor hurdle IRR, leverage
    "bear": {"exit": q[0], "hurdle": 0.25, "lev": 4.5},
    "base": {"exit": q[1], "hurdle": 0.20, "lev": 5.0},
    "bull": {"exit": q[2], "hurdle": 0.175, "lev": 5.5},
}
LBO_ROWS = ["Entry price per share", "Diluted shares (m)", "Equity purchase price", "Existing debt refinanced", "Cash at entry", "Minimum cash",
            "Entry enterprise value", "EBITDA FY2025", "Entry EV / EBITDA", "Leverage (x FY2025 EBITDA)", "New debt", "SOFR, 29 Aug 2025",
            "Credit spread", "Interest rate", "Transaction fees (% of entry EV)", "Financing fees (% of new debt)",
            "Mandatory amortization (% of original debt a year)", "Exit fee (% of exit EV)", "Transaction fees", "Financing fees", "Total uses",
            "Excess cash used", "Sponsor equity", "Total sources", "Sources minus uses",
            "Revenue", "EBITDA (reported basis)", "FCFF before financing (DCF Base)", "Interest", "Tax rate", "After-tax interest",
            "Cash flow after interest", "Cash available above minimum", "Mandatory repayment", "Funding shortfall (1 = yes)", "Cash sweep",
            "Debt repaid", "Debt, end of year", "Cash, end of year", "Feasible (1 = no funding shortfall)",
            "Exit EV / EBITDA", "Exit enterprise value", "Exit fee", "Exit equity value", "MOIC", "IRR", "Hurdle IRR", "Meets hurdle (1 = yes)",
            "R&D capitalization adjustment (% of revenue)", "D&A (% of revenue)"]
L_ = {k: i for i, k in enumerate(LBO_ROWS)}
LBO_TERMS = {"minimumCash": 30.0, "creditSpread": 0.035, "transactionFee": 0.02, "financingFee": 0.025, "mandatoryAmortization": 0.01, "exitFee": 0.02}


def lbo_sheet(k, price):
    """One entry price. Mandatory amortization is paid first, then a sweep of cash above the minimum, never more than the
    debt outstanding. A year whose cash cannot meet the mandatory payment is a funding shortfall: no revolver or extra
    equity is modelled, so the case is infeasible rather than silently borrowing more."""
    s = LBO_SCEN[k]
    sh = ps.Sheet.create_new_sheet(len(LBO_ROWS), 6, name=f"LBO {k.title()}", rows_labels=LBO_ROWS,
                                   columns_labels=["Entry / FY2025"] + [f"Year {t}" for t in range(1, 6)])
    f, B = sh.fn, sh.fn.brackets
    one, zero = f.const(1), f.const(0)
    c = lambda row, col: sh.iloc[L_[row], col]  # noqa: E731
    v = lambda row: sh.iloc[L_[row], 0]  # noqa: E731
    T = LBO_TERMS
    for row, val in [("Entry price per share", price), ("Diluted shares (m)", 13.633263), ("Existing debt refinanced", 86.995), ("Cash at entry", 58.13),
                     ("Minimum cash", T["minimumCash"]), ("EBITDA FY2025", EBITDA25), ("Leverage (x FY2025 EBITDA)", s["lev"]), ("SOFR, 29 Aug 2025", SOFR_0829),
                     ("Credit spread", T["creditSpread"]), ("Transaction fees (% of entry EV)", T["transactionFee"]), ("Financing fees (% of new debt)", T["financingFee"]),
                     ("Mandatory amortization (% of original debt a year)", T["mandatoryAmortization"]), ("Exit fee (% of exit EV)", T["exitFee"]),
                     ("Exit EV / EBITDA", s["exit"]), ("Hurdle IRR", s["hurdle"]), ("R&D capitalization adjustment (% of revenue)", RND_ADJ_PCT), ("D&A (% of revenue)", DA_PCT)]:
        sh.iloc[L_[row], 0] = float(val)
    sh.iloc[L_["Equity purchase price"], 0] = v("Entry price per share") * v("Diluted shares (m)")
    sh.iloc[L_["Entry enterprise value"], 0] = v("Equity purchase price") + v("Existing debt refinanced") - v("Cash at entry")
    sh.iloc[L_["Entry EV / EBITDA"], 0] = v("Entry enterprise value") / v("EBITDA FY2025")
    sh.iloc[L_["New debt"], 0] = v("Leverage (x FY2025 EBITDA)") * v("EBITDA FY2025")
    sh.iloc[L_["Interest rate"], 0] = v("SOFR, 29 Aug 2025") + v("Credit spread")
    sh.iloc[L_["Transaction fees"], 0] = v("Entry enterprise value") * v("Transaction fees (% of entry EV)")
    sh.iloc[L_["Financing fees"], 0] = v("New debt") * v("Financing fees (% of new debt)")
    sh.iloc[L_["Total uses"], 0] = v("Equity purchase price") + v("Existing debt refinanced") + v("Transaction fees") + v("Financing fees")
    sh.iloc[L_["Excess cash used"], 0] = v("Cash at entry") - v("Minimum cash")
    sh.iloc[L_["Sponsor equity"], 0] = v("Total uses") - v("New debt") - v("Excess cash used")
    sh.iloc[L_["Total sources"], 0] = v("New debt") + v("Excess cash used") + v("Sponsor equity")
    sh.iloc[L_["Sources minus uses"], 0] = v("Total sources") - v("Total uses")
    sh.iloc[L_["Debt, end of year"], 0] = v("New debt")
    sh.iloc[L_["Cash, end of year"], 0] = v("Minimum cash")
    for t in range(1, 6):
        sh.iloc[L_["Revenue"], t] = link(sh, BASE, "Revenue", t)
        ebit = link(sh, BASE, "EBIT", t)
        sh.iloc[L_["EBITDA (reported basis)"], t] = ebit + c("Revenue", t) * B(v("D&A (% of revenue)") - v("R&D capitalization adjustment (% of revenue)"))
        sh.iloc[L_["FCFF before financing (DCF Base)"], t] = link(sh, BASE, "FCFF", t)
        sh.iloc[L_["Tax rate"], t] = link(sh, BASE, "Tax rate", t)
        sh.iloc[L_["Interest"], t] = v("Interest rate") * c("Debt, end of year", t - 1)
        sh.iloc[L_["After-tax interest"], t] = c("Interest", t) * B(one - c("Tax rate", t))
        sh.iloc[L_["Cash flow after interest"], t] = c("FCFF before financing (DCF Base)", t) - c("After-tax interest", t)
        sh.iloc[L_["Cash available above minimum"], t] = c("Cash, end of year", t - 1) + c("Cash flow after interest", t) - v("Minimum cash")
        scheduled = v("Mandatory amortization (% of original debt a year)") * v("New debt")
        sh.iloc[L_["Mandatory repayment"], t] = f.conditional(scheduled < c("Debt, end of year", t - 1), scheduled, c("Debt, end of year", t - 1))
        sh.iloc[L_["Funding shortfall (1 = yes)"], t] = f.conditional(c("Cash available above minimum", t) < c("Mandatory repayment", t), one, zero)
        room = c("Cash available above minimum", t) - c("Mandatory repayment", t)
        cap = c("Debt, end of year", t - 1) - c("Mandatory repayment", t)
        sh.iloc[L_["Cash sweep"], t] = f.conditional(room > zero, f.conditional(room < cap, room, cap), zero)
        sh.iloc[L_["Debt repaid"], t] = c("Mandatory repayment", t) + c("Cash sweep", t)
        sh.iloc[L_["Debt, end of year"], t] = c("Debt, end of year", t - 1) - c("Debt repaid", t)
        sh.iloc[L_["Cash, end of year"], t] = c("Cash, end of year", t - 1) + c("Cash flow after interest", t) - c("Debt repaid", t)
    sh.iloc[L_["Feasible (1 = no funding shortfall)"], 0] = f.conditional(sh.iloc[L_["Funding shortfall (1 = yes)"], 1:6].sum() > zero, zero, one)
    sh.iloc[L_["Exit enterprise value"], 0] = v("Exit EV / EBITDA") * c("EBITDA (reported basis)", 5)
    sh.iloc[L_["Exit fee"], 0] = v("Exit enterprise value") * v("Exit fee (% of exit EV)")
    sh.iloc[L_["Exit equity value"], 0] = v("Exit enterprise value") - v("Exit fee") - c("Debt, end of year", 5) + c("Cash, end of year", 5)
    sh.iloc[L_["MOIC"], 0] = v("Exit equity value") / v("Sponsor equity")
    sh.iloc[L_["IRR"], 0] = f.conditional(v("MOIC") > zero, v("MOIC") ** B(one / f.const(5)) - one, f.const(-1))
    sh.iloc[L_["Meets hurdle (1 = yes)"], 0] = f.conditional(v("Feasible (1 = no funding shortfall)") == one, f.conditional(v("IRR") >= v("Hurdle IRR"), one, zero), zero)
    # Python-side checks of the same sheet: sources equal uses, balances never negative, cash at least the minimum when feasible.
    assert abs(v("Sources minus uses").value) < 1e-9
    for t in range(1, 6):
        assert c("Debt, end of year", t).value >= -1e-9
        if v("Feasible (1 = no funding shortfall)").value == 1:
            assert c("Cash, end of year", t).value >= T["minimumCash"] - 1e-9
    return sh


def lbo_eval(k, price):
    sh = lbo_sheet(k, price)
    return sh.iloc[L_["IRR"], 0].value, sh.iloc[L_["Feasible (1 = no funding shortfall)"], 0].value == 1


lbo_solution, lbo = {}, {}
GRID = [round(50 + 5 * i, 2) for i in range(int((230 - 50) / 5) + 1)]
for k in LBO_SCEN:
    h = LBO_SCEN[k]["hurdle"]
    evals = [lbo_eval(k, p) for p in GRID]
    irrs = [e[0] for e in evals]
    feasible = all(e[1] for e in evals)
    monotonic = all(a >= b for a, b in zip(irrs, irrs[1:]))
    price, status = None, None
    if not feasible:
        status = "infeasible: the operating case cannot meet the mandatory debt payments"
    else:
        ok = [p for p, r in zip(GRID, irrs) if r >= h]
        if not ok:
            status = f"no solution: no price from ${GRID[0]:.0f} up meets the target return"
        elif ok[-1] == GRID[-1]:
            status, price = f"search ceiling reached: the target return is met at ${GRID[-1]:.0f}, the top of the search range", GRID[-1]
        else:
            lo, hi = ok[-1], ok[-1] + 5
            while hi - lo >= 0.005:
                mid = (lo + hi) / 2
                if lbo_eval(k, mid)[0] >= h:
                    lo = mid
                else:
                    hi = mid
            status, price = "boundary found", lo
    lbo_solution[k] = {"price": price, "status": status, "hurdle": h, "exitMultiple": LBO_SCEN[k]["exit"], "leverage": LBO_SCEN[k]["lev"],
                       "monotonicOnGrid": monotonic, "feasible": feasible, "terms": LBO_TERMS, "grid": list(zip(GRID, irrs))}
    lbo[k] = lbo_sheet(k, price if price else GRID[0])

# ---------------------------------------------------------------- strategic buyer synergies
# Run-rate pre-tax cost synergies as % of target revenue: minimum, median and maximum announced in the precedent deals.
_sp = precedents.method["synergyPctOfRevenue"]
SYN = {"bear": min(_sp), "base": sorted(_sp)[len(_sp) // 2 - 1] / 2 + sorted(_sp)[len(_sp) // 2] / 2 if len(_sp) % 2 == 0 else sorted(_sp)[len(_sp) // 2], "bull": max(_sp)}
SYN_ROWS = ["Revenue (DCF Base)", "Phase-in", "Pre-tax cost synergies", "One-time costs to achieve", "Tax rate (DCF Base)", "After-tax net synergies",
            "Cumulative discount factor (DCF Base)", "PV of net synergies", "Run-rate synergies (% of revenue)", "One-time costs (x run-rate synergies)",
            "Terminal growth (DCF Base)", "Terminal WACC (DCF Base)", "Terminal value of synergies, end of year 10", "PV of terminal value",
            "Sum of PV, years 1-10", "Value of synergies", "Shares (m)", "Synergy value per share", "Standalone Base value per share",
            "Value per share to a buyer that keeps all synergies"]
S_ = {k: i for i, k in enumerate(SYN_ROWS)}


def syn_sheet(k):
    sh = ps.Sheet.create_new_sheet(len(SYN_ROWS), 11, name=f"Synergies {k.title()}", rows_labels=SYN_ROWS,
                                   columns_labels=["Valuation"] + [f"Year {t}" for t in range(1, 11)])
    f, B = sh.fn, sh.fn.brackets
    one = f.const(1)
    c = lambda row, col: sh.iloc[S_[row], col]  # noqa: E731
    v = lambda row: sh.iloc[S_[row], 0]  # noqa: E731
    sh.iloc[S_["Run-rate synergies (% of revenue)"], 0] = SYN[k]
    sh.iloc[S_["One-time costs (x run-rate synergies)"], 0] = 1.0
    sh.iloc[S_["Shares (m)"], 0] = 13.633263
    sh.iloc[S_["Terminal growth (DCF Base)"], 0] = link(sh, BASE, "Revenue growth", 11)
    sh.iloc[S_["Terminal WACC (DCF Base)"], 0] = link(sh, BASE, "WACC", 11)
    sh.iloc[S_["Standalone Base value per share"], 0] = link(sh, BASE, "Value per share", 0)
    for t in range(1, 11):
        sh.iloc[S_["Revenue (DCF Base)"], t] = link(sh, BASE, "Revenue", t)
    for t in range(1, 11):
        sh.iloc[S_["Phase-in"], t] = 0.5 if t == 1 else 1.0
        sh.iloc[S_["Pre-tax cost synergies"], t] = c("Revenue (DCF Base)", t) * v("Run-rate synergies (% of revenue)") * c("Phase-in", t)
        if t <= 2:
            sh.iloc[S_["One-time costs to achieve"], t] = f.const(0.5) * v("One-time costs (x run-rate synergies)") * c("Revenue (DCF Base)", 2) * v("Run-rate synergies (% of revenue)")
        else:
            sh.iloc[S_["One-time costs to achieve"], t] = 0.0
        sh.iloc[S_["Tax rate (DCF Base)"], t] = link(sh, BASE, "Tax rate", t)
        sh.iloc[S_["After-tax net synergies"], t] = B(c("Pre-tax cost synergies", t) - c("One-time costs to achieve", t)) * B(one - c("Tax rate (DCF Base)", t))
        sh.iloc[S_["Cumulative discount factor (DCF Base)"], t] = link(sh, BASE, "Cumulative discount factor", t)
        sh.iloc[S_["PV of net synergies"], t] = c("After-tax net synergies", t) * c("Cumulative discount factor (DCF Base)", t)
    terminal_tax = link(sh, BASE, "Tax rate", 11)
    sh.iloc[S_["Terminal value of synergies, end of year 10"], 0] = (c("Pre-tax cost synergies", 10) * B(one + v("Terminal growth (DCF Base)")) * B(one - terminal_tax)
                                                                      / B(v("Terminal WACC (DCF Base)") - v("Terminal growth (DCF Base)")))
    sh.iloc[S_["PV of terminal value"], 0] = v("Terminal value of synergies, end of year 10") * c("Cumulative discount factor (DCF Base)", 10)
    sh.iloc[S_["Sum of PV, years 1-10"], 0] = sh.iloc[S_["PV of net synergies"], 1:11].sum()
    sh.iloc[S_["Value of synergies"], 0] = v("Sum of PV, years 1-10") + v("PV of terminal value")
    sh.iloc[S_["Synergy value per share"], 0] = v("Value of synergies") / v("Shares (m)")
    sh.iloc[S_["Value per share to a buyer that keeps all synergies"], 0] = v("Standalone Base value per share") + v("Synergy value per share")
    return sh


syn = {k: syn_sheet(k) for k in SYN}

# ---------------------------------------------------------------- export
sheets = SH + list(eva.values()) + list(ddm.values()) + list(lbo.values()) + list(syn.values()) + [comps.sh, comps.val] + precedents.sheets
write_xlsx(sheets, OUT / "wd40_valuation.xlsx")
cells = export_cells(sheets)
(OUT / "valuation_cells.json").write_text(json.dumps(cells, indent=1))

val = lambda sh, rows, row: sh.iloc[rows[row], 0].value  # noqa: E731
addr = lambda sheet, rows, row, col="B": f"{sheet.name}!{col}{rows[row] + 2}"  # noqa: E731
res = {
    "eva": {c: {"evaValue": val(s, E, "Operating value from economic profit"), "dcfValue": val(s, E, "Operating value from DCF"),
                "difference": val(s, E, "Difference (EVA minus DCF)"), "cell": addr(s, E, "Difference (EVA minus DCF)")} for c, s in eva.items()},
    "ddm": {k: {"value": val(s, D, "Value per share"), "costOfEquity": A["waccCases"][k]["costOfEquity"], **DDM_SCEN[k],
                "terminalPayout": val(s, D, "Terminal payout ratio"), "pvTerminalShare": val(s, D, "PV of terminal value") / val(s, D, "Value per share"),
                "cell": addr(s, D, "Value per share")} for k, s in ddm.items()},
    "lbo": {k: {**{kk: vv for kk, vv in lbo_solution[k].items() if kk != "grid"}, "sponsorEquity": val(s, L_, "Sponsor equity"),
                "entryEvToEbitda": val(s, L_, "Entry EV / EBITDA"), "moic": val(s, L_, "MOIC"), "irr": val(s, L_, "IRR"),
                "debtYear5": s.iloc[L_["Debt, end of year"], 5].value, "interestRate": val(s, L_, "Interest rate"), "newDebt": val(s, L_, "New debt"),
                "exitFee": val(s, L_, "Exit fee"), "sourcesMinusUses": val(s, L_, "Sources minus uses"),
                "cells": [addr(s, L_, "Entry price per share"), addr(s, L_, "IRR"), addr(s, L_, "MOIC")]} for k, s in lbo.items()},
    "lboGrid": {k: lbo_solution[k]["grid"] for k in lbo_solution},
    "synergies": {k: {"pct": SYN[k], "perShare": val(s, S_, "Synergy value per share"), "buyerValue": val(s, S_, "Value per share to a buyer that keeps all synergies"),
                      "cell": addr(s, S_, "Value per share to a buyer that keeps all synergies")} for k, s in syn.items()},
    "sofr": SOFR_0829,
}
(OUT / "core_results.json").write_text(json.dumps(res, indent=1))

pc = lambda x, d=1: f"{x * 100:.{d}f}%"  # noqa: E731
L, Dd, Sy = res["lbo"], res["ddm"], res["synergies"]
LBO_STATUS = "; ".join(f"{k} {d['status']}" for k, d in L.items())
LBO_MONOTONIC = "yes" if all(d["monotonicOnGrid"] for d in L.values()) else "no"
methods = [
    {"id": "ddm", "group": "standalone", "label": "Dividend discount", "sublabel": "dividends only, Bear to Bull", "kind": "range",
     "low": Dd["bear"]["value"], "base": Dd["base"]["value"], "high": Dd["bull"]["value"], "status": "workbook",
     "note": ("Dividends per share grow with EPS for ten years from FY2025 non-GAAP EPS of $5.82 and a $3.76 annual dividend, then the payout rises to 1 - growth / return on equity. "
              "Cost of equity is the Stage 2 CAPM figure for each scenario. Buybacks are left out because FY2025 repurchases were $12.3m against $50.3m of dividends."),
     "table": [["Scenario", "EPS growth, years 1-10", "Cost of equity", "Terminal growth", "Terminal return on equity", "Terminal payout", "Value per share"]] +
              [[k.title(), pc(d["g"], 0), pc(d["costOfEquity"], 2), pc(d["gT"]), "cost of equity" if d["roe"] is None else pc(d["roe"], 0), pc(d["terminalPayout"], 0), f"${d['value']:.2f}"] for k, d in Dd.items()],
     "cells": [d["cell"] for d in Dd.values()], "sourceIds": ["wdfc-8k-2025-10-22", "sec-xbrl", "damodaran-erp-2025-09"]},
    {"id": "lbo", "group": "buyer", "label": "Buyout fund", "sublabel": "highest price that meets the target return", "kind": "range",
     "low": L["bear"]["price"], "base": L["base"]["price"], "high": L["bull"]["price"], "status": "workbook",
     "note": (f"Sources and uses at the entry price, new debt at SOFR on 29 Aug 2025 ({pc(SOFR_0829, 2)}) plus 3.5%, existing debt refinanced, cash above $30m used, 2% transaction and 2.5% financing fees. "
              "The Base DCF operating case funds interest, a mandatory 1% a year of the original debt, then a sweep of cash above the minimum, for five years; the business is then sold at the peer EV/EBITDA quartile less a 2% exit fee. "
              "A year whose cash cannot meet the mandatory payment would make the case infeasible, since no revolver or extra equity is modelled; no scenario has one. "
              "With one equity payment in and one out, IRR = MOIC^(1/5) - 1. Each price is the highest at which the IRR meets the target, bracketed on a $5 grid from $50 to $230 and refined to under a cent. "
              f"Status by scenario: {LBO_STATUS}. IRR falls as price rises on the grid in every scenario: {LBO_MONOTONIC}."),
     "table": [["Scenario", "Debt / EBITDA", "Target IRR", "Exit EV / EBITDA", "Highest price", "Entry EV / EBITDA", "Sponsor equity ($m)", "Debt after year 5 ($m)", "MOIC", "IRR"]] +
              [[k.title(), f"{d['leverage']:.1f}x", pc(d["hurdle"], 1), f"{d['exitMultiple']:.1f}x", f"${d['price']:.2f}" if d["price"] else d["status"], f"{d['entryEvToEbitda']:.1f}x", f"{d['sponsorEquity']:,.0f}", f"{d['debtYear5']:,.0f}", f"{d['moic']:.2f}x", pc(d["irr"], 2)] for k, d in L.items()],
     "cells": L["base"]["cells"], "sourceIds": ["nyfed-sofr-2025-08-29"] + comps.method["sourceIds"][:1]},
    {"id": "synergies", "group": "buyer", "label": "Strategic buyer", "sublabel": "Base value plus all cost synergies", "kind": "range",
     "low": Sy["bear"]["buyerValue"], "base": Sy["base"]["buyerValue"], "high": Sy["bull"]["buyerValue"], "status": "workbook",
     "note": ("Base standalone value plus the present value of after-tax cost synergies, phased in at half in year 1 and fully from year 2, less one-time costs equal to one year of run-rate synergies. "
              f"Run-rate synergies are {pc(SYN['bear'])}, {pc(SYN['base'])} and {pc(SYN['bull'])} of WD-40's revenue, the lowest, median and highest share announced in the precedent deals that disclosed them. "
              "The bar is the most a buyer could pay before handing all synergies to WD-40's shareholders. Base already includes WD-40's own margin improvement to 18%, which is not counted again."),
     "table": [["Scenario", "Synergies / revenue", "Synergy value per share", "Value per share to the buyer"]] +
              [[k.title(), pc(d["pct"]), f"${d['perShare']:.2f}", f"${d['buyerValue']:.2f}"] for k, d in Sy.items()],
     "cells": [d["cell"] for d in Sy.values()], "sourceIds": [k for k in precedents.sources]},
    precedents.method,
]
(HERE / "out" / "methods_core.json").write_text(json.dumps({"methods": methods, "eva": res["eva"],
    "sources": {**precedents.sources, "nyfed-sofr-2025-08-29": {"title": "SOFR, New York Fed, 29 Aug 2025", "url": "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2025-08-25&endDate=2025-09-02", "asOf": "2025-08-29"}}}, indent=1))
print(json.dumps({k: v for k, v in res.items() if k not in ("lboGrid", "eva")}, indent=1)[:1500])
