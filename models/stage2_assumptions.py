"""Stage 2: dated assumption build for the WD-40 FY2025 retrospective case.

Reads only files saved under models/data (no network). Writes
  models/scenarios.json                 scenario definitions as Ginzu cell overrides, with rationale and sources
  models/out/stage2_assumptions.json    every intermediate number
Run:  python -I models/stage2_assumptions.py
"""
import csv
import datetime as dt
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "models" / "data"
OUT = ROOT / "models" / "out"
OUT.mkdir(parents=True, exist_ok=True)

PRICE_DATE = dt.date(2025, 8, 29)
PRICE = 216.04
COMMON_SHARES = 13.527614          # million, balance sheet 2025-08-31 (case proposal Input sheet!B21 rationale)
DEBT = 86.995                      # USD m, gross borrowings, case proposal Input sheet!B15
CASH = 58.13                       # USD m, case proposal Input sheet!B18
MARGINAL_TAX = 0.25                # case proposal Input sheet!B24 (analyst assumption)

# ---------------------------------------------------------------- sources
SOURCES = {
    "ust-par-2025-08-29": {"title": "US Treasury daily par yield curve, 29 Aug 2025", "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2025", "file": "models/data/rates/ustreasury_par_yield_curve_2025.csv", "asOf": "2025-08-29"},
    "damodaran-erp-2025-09": {"title": "Damodaran, implied ERP by month (start of September 2025)", "url": "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx", "file": "models/data/damodaran/ERPbymonth.xlsx", "asOf": "2025-09-01"},
    "damodaran-betas-2025-01": {"title": "Damodaran, US industry betas, January 2025", "url": "https://pages.stern.nyu.edu/~adamodar/pc/archives/betas24.xls", "file": "models/data/damodaran/betas_us_2025-01.xls", "asOf": "2025-01-06"},
    "damodaran-wacc-2025-01": {"title": "Damodaran, US industry cost of capital, January 2025", "url": "https://pages.stern.nyu.edu/~adamodar/pc/archives/wacc24.xls", "file": "models/data/damodaran/wacc_us_2025-01.xls", "asOf": "2025-01-08"},
    "yahoo-prices": {"title": "WDFC and S&P 500 weekly and monthly adjusted closes, Aug 2020 to Aug 2025 (Yahoo Finance chart API)", "file": "models/data/market/", "asOf": "2025-08-29"},
    "sec-xbrl": {"title": "WD-40 Company XBRL company facts (SEC EDGAR)", "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000105132.json", "file": "models/data/sec/wdfc_companyfacts.json"},
    "wdfc-8k-2025-10-22": {"title": "WD-40 Company FY2025 results and FY2026 guidance (8-K exhibit 99.1, 22 Oct 2025)", "url": "https://www.sec.gov/Archives/edgar/data/105132/000010513225000061/wdfc-20251022xexx991.htm", "publishedAt": "2025-10-22"},
}

# ---------------------------------------------------------------- 1. risk-free rate
rf = None
with open(DATA / "rates" / "ustreasury_par_yield_curve_2025.csv", newline="") as f:
    for row in csv.DictReader(f):
        if row["Date"] == "08/29/2025":
            rf = float(row["10 Yr"]) / 100
assert rf is not None, "10-year yield for 2025-08-29 not found"

# ---------------------------------------------------------------- 2. equity risk premium
import openpyxl  # noqa: E402

wb = openpyxl.load_workbook(DATA / "damodaran" / "ERPbymonth.xlsx", data_only=True)
ws = wb["Historical ERP"]
header = [c.value for c in ws[1]]
erp_row = None
for r in ws.iter_rows(min_row=2, values_only=True):
    if isinstance(r[0], dt.datetime) and r[0].date() == dt.date(2025, 9, 1):
        erp_row = dict(zip(header, r))
assert erp_row
erp = {"t12m": erp_row["ERP (T12m)"], "sustainablePayout": erp_row["ERP (T12 m with sustainable payout)"],
       "adjustedRiskfree": erp_row["ERP (T12m) with adj riskfree rate"], "smoothed": erp_row["ERP (Smoothed)"]}

# ---------------------------------------------------------------- 3. betas
import xlrd  # noqa: E402


def industry_rows(path):
    book = xlrd.open_workbook(path)
    sh = book.sheet_by_name("Industry Averages")
    hdr, rows = None, {}
    for i in range(sh.nrows):
        r = sh.row_values(i)
        if str(r[0]).strip().lower().startswith("industry name"):
            hdr = [str(h).strip() for h in r]
            continue
        if hdr and r[0]:
            rows[str(r[0]).strip()] = dict(zip(hdr, r))
    return rows


betas = industry_rows(DATA / "damodaran" / "betas_us_2025-01.xls")
waccs = industry_rows(DATA / "damodaran" / "wacc_us_2025-01.xls")
ind = {k: betas[k]["Unlevered beta corrected for cash"] for k in ("Chemical (Specialty)", "Household Products")}
sector_cost_of_debt = waccs["Chemical (Specialty)"]["Cost of Debt"]


def load_adjclose(name):
    d = json.load(open(DATA / "market" / name))["chart"]["result"][0]
    return {dt.datetime.utcfromtimestamp(t).date(): a for t, a in zip(d["timestamp"], d["indicators"]["adjclose"][0]["adjclose"]) if a}


def regression_beta(freq, years):
    a = load_adjclose(f"yahoo_WDFC_{freq}_2020-08_2025-08.json")
    m = load_adjclose(f"yahoo_GSPC_{freq}_2020-08_2025-08.json")
    start = PRICE_DATE - dt.timedelta(days=365 * years + 3)
    ks = [k for k in sorted(set(a) & set(m)) if start <= k <= PRICE_DATE]
    ra = [math.log(a[ks[i + 1]] / a[ks[i]]) for i in range(len(ks) - 1)]
    rm = [math.log(m[ks[i + 1]] / m[ks[i]]) for i in range(len(ks) - 1)]
    n = len(ra)
    ma, mm = sum(ra) / n, sum(rm) / n
    cov = sum((x - ma) * (y - mm) for x, y in zip(ra, rm)) / (n - 1)
    var_m = sum((y - mm) ** 2 for y in rm) / (n - 1)
    var_a = sum((x - ma) ** 2 for x in ra) / (n - 1)
    b = cov / var_m
    r2 = cov ** 2 / (var_m * var_a)
    se = math.sqrt((1 - r2) / (n - 2)) * math.sqrt(var_a / var_m)
    return {"frequency": freq, "years": years, "observations": n, "beta": b, "standardError": se, "r2": r2, "blumeAdjusted": 0.67 * b + 0.33}


regressions = [regression_beta("weekly", 2), regression_beta("weekly", 5), regression_beta("monthly", 3), regression_beta("monthly", 5)]

market_cap = PRICE * COMMON_SHARES
d_e = DEBT / market_cap
w_d = DEBT / (DEBT + market_cap)


def relever(bu):
    return bu * (1 + (1 - MARGINAL_TAX) * d_e)


def wacc(beta_l, erp_value, kd_pre):
    ke = rf + beta_l * erp_value
    return {"leveredBeta": beta_l, "erp": erp_value, "costOfEquity": ke, "preTaxCostOfDebt": kd_pre,
            "afterTaxCostOfDebt": kd_pre * (1 - MARGINAL_TAX), "debtWeight": w_d,
            "wacc": ke * (1 - w_d) + kd_pre * (1 - MARGINAL_TAX) * w_d}


bottom_up_unlevered = (ind["Chemical (Specialty)"] + ind["Household Products"]) / 2
wacc_cases = {
    "bear": wacc(relever(ind["Household Products"]), erp["adjustedRiskfree"], sector_cost_of_debt),
    "base": wacc(relever(bottom_up_unlevered), erp["t12m"], sector_cost_of_debt),
    "bull": wacc(regressions[1]["blumeAdjusted"], erp["sustainablePayout"], sector_cost_of_debt),
}
# Bear terminal: cost of capital drifts to the market's (beta 1) as WD-40 matures; Damodaran's default for stable growth.
market_terminal_bear = wacc(1.0, erp["adjustedRiskfree"], sector_cost_of_debt)["wacc"]

# ---------------------------------------------------------------- 4. history from XBRL
facts = json.load(open(DATA / "sec" / "wdfc_companyfacts.json"))["facts"]["us-gaap"]


def fy_series(*tags):
    out = {}
    for tag in tags:
        for fct in facts.get(tag, {}).get("units", {}).get("USD", []):
            if fct.get("form") != "10-K" or "start" not in fct:
                continue
            s, e = dt.date.fromisoformat(fct["start"]), dt.date.fromisoformat(fct["end"])
            if 360 < (e - s).days < 372 and e.month == 8:
                out.setdefault(e.year, fct["val"] / 1e6)
    return dict(sorted(out.items()))


revenue = fy_series("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")
ebit = fy_series("OperatingIncomeLoss")
gross = fy_series("GrossProfit")
history = [{"fiscalYear": y, "revenue": revenue[y], "operatingIncome": ebit.get(y), "operatingMargin": ebit[y] / revenue[y] if y in ebit else None,
            "grossMargin": gross[y] / revenue[y] if y in gross else None} for y in revenue if y >= 2017]
cagr = lambda a, b: (revenue[b] / revenue[a]) ** (1 / (b - a)) - 1
growth_history = {"FY2017-FY2025": cagr(2017, 2025), "FY2019-FY2025": cagr(2019, 2025), "FY2021-FY2025": cagr(2021, 2025)}
margin_pre = [h["operatingMargin"] for h in history if 2017 <= h["fiscalYear"] <= 2020]
margin_post = [h["operatingMargin"] for h in history if 2022 <= h["fiscalYear"] <= 2025]

# ---------------------------------------------------------------- 5. FY2026 guidance -> year-1 inputs
# Guidance (8-K 2025-10-22): pro forma net sales $630-655m (5-9% growth from FY2025 pro forma, FY2025 average FX),
# operating income $103-110m (5-12% growth from FY2025 pro forma), tax rate 22.5-23.5%.
# Pro forma excludes the Americas homecare and cleaning brands held for sale (about $12.5m sales, $3.6m operating income).
REPORTED_REVENUE = 619.985
RND_ADJUSTMENT = 106.05966666666667 - 103.793   # R&D capitalization adds this to EBIT in the workbook (Valuation output!B5)
guid_sales = {"bear": 630.0, "base": 642.5, "bull": 655.0}
guid_oi = {"bear": 103.0, "base": 106.5, "bull": 110.0}
year1_growth = {k: v / REPORTED_REVENUE - 1 for k, v in guid_sales.items()}
year1_margin = {k: (guid_oi[k] + RND_ADJUSTMENT) / guid_sales["base"] for k in guid_oi}

# ---------------------------------------------------------------- 6. scenarios as Ginzu cell overrides
C = {"growth1": "Input sheet!B26", "margin1": "Input sheet!B27", "growth25": "Input sheet!B28", "marginTarget": "Input sheet!B29",
     "convergence": "Input sheet!B30", "tax0": "Input sheet!B23", "wacc0": "Cost of capital worksheet!B12", "waccT": "Input sheet!B46",
     "roicOn": "Input sheet!B48", "roicT": "Input sheet!B49", "gT": "Input sheet!B68", "nonOp": "Input sheet!B19"}
r4 = lambda x: round(x, 6)
scen = {}
spec = {
    "bear": {"growth25": 0.04, "marginTarget": year1_margin["bear"], "tax0": 0.235, "gT": 0.020, "roic": None, "waccT": market_terminal_bear, "nonOp": 0.0},
    "base": {"growth25": 0.06, "marginTarget": 0.18, "tax0": 0.230, "gT": 0.025, "roic": 0.15, "waccT": None, "nonOp": 0.0},
    "bull": {"growth25": 0.07, "marginTarget": 0.20, "tax0": 0.225, "gT": 0.030, "roic": 0.20, "waccT": None, "nonOp": 0.0},
}
for k, s in spec.items():
    w0 = wacc_cases[k]["wacc"]
    o = {C["growth1"]: r4(year1_growth[k]), C["growth25"]: s["growth25"], C["margin1"]: r4(year1_margin[k]),
         C["marginTarget"]: r4(s["marginTarget"]), C["convergence"]: 5, C["tax0"]: s["tax0"],
         C["wacc0"]: r4(w0), C["waccT"]: r4(s["waccT"] if s["waccT"] else w0), C["gT"]: s["gT"], C["nonOp"]: s["nonOp"]}
    if s["roic"] is None:
        o[C["roicOn"]] = "No"
    else:
        o[C["roicOn"]] = "Yes"
        o[C["roicT"]] = s["roic"]
    scen[k] = o

why = {
    "bear": [
        "Year-1 revenue at the low end of FY2026 guidance ($630m pro forma), then 4% a year, below the 6.2% FY2017-FY2025 compound rate.",
        "Margin stays at the level implied by the low end of operating-income guidance; no recovery toward the FY2017-FY2020 range.",
        "Cost of capital from the Household Products unlevered beta and the higher Damodaran ERP variant; it drifts to the market's cost of capital by year 10.",
        "No excess returns on new capital after year 10 (terminal ROIC equals terminal WACC). Terminal growth 2.0%.",
    ],
    "base": [
        "Year-1 revenue at the midpoint of FY2026 guidance ($642.5m pro forma, about 3.6% above reported FY2025 because divested homecare sales leave the base), then 6% a year, in line with the 6.2% FY2017-FY2025 compound rate.",
        "Year-1 margin at the guidance midpoint ($106.5m operating income) plus the workbook's R&D adjustment; target 18% by year 5, about a third of the way from the FY2022-FY2025 average back to the FY2017-FY2020 average (both after the R&D adjustment).",
        "Cost of capital from a bottom-up beta (average of Damodaran's Chemical (Specialty) and Household Products unlevered betas, January 2025) relevered at WD-40's market debt-to-equity, the 29 Aug 2025 10-year Treasury yield and Damodaran's September 2025 implied ERP. Held flat because WD-40 is already a mature company.",
        "New capital after year 10 earns 15%: above the cost of capital because the brand and distribution persist, well below the 26% the model earns through year 10. Terminal growth 2.5%.",
    ],
    "bull": [
        "Year-1 revenue at the top of FY2026 guidance ($655m pro forma), then 7% a year, above the 6.6% FY2019-FY2025 compound rate.",
        "Year-1 margin at the top of operating-income guidance; target 20% by year 5, the FY2017-FY2020 average operating margin plus the R&D adjustment.",
        "Cost of capital from the Blume-adjusted 5-year weekly regression beta and the lower Damodaran ERP variant.",
        "New capital after year 10 earns 20%. Terminal growth 3.0%, below the 4.23% risk-free rate.",
    ],
}
scenarios = {"schemaVersion": 1, "assumptionSetVersion": "2025-10-27-retrospective-v1",
             "timeBasis": {"priceDate": PRICE_DATE.isoformat(), "price": PRICE, "fiscalYearEnd": "2025-08-31",
                           "latestSourcePublication": "2025-10-27",
                           "note": "Retrospective FY2025 review: uses the FY2025 10-K (27 Oct 2025) and the FY2026 guidance (22 Oct 2025), which were published after the price date."},
             "notChanged": ["Sales-to-capital stays at 2.0 in all scenarios (Input sheet!B31, B32).",
                            "Terminal tax rate stays at 25% (Input sheet!B24).",
                            "Expected proceeds from the Americas homecare sale are not added: no price was disclosed and the sale had not closed."],
             "scenarios": {k: {"label": k.title(), "overrides": scen[k], "rationale": why[k]} for k in ("bear", "base", "bull")},
             "sources": SOURCES}
(ROOT / "models" / "scenarios.json").write_text(json.dumps(scenarios, indent=1) + "\n")

detail = {"riskFree": rf, "erp": erp, "industryUnleveredBetas": ind, "bottomUpUnlevered": bottom_up_unlevered,
          "regressionBetas": regressions, "marketCap": market_cap, "debtToEquity": d_e, "debtWeight": w_d,
          "sectorCostOfDebt": sector_cost_of_debt, "waccCases": wacc_cases, "marketTerminalBear": market_terminal_bear,
          "history": history, "growthHistory": growth_history,
          "marginFY2017_2020": sum(margin_pre) / len(margin_pre), "marginFY2022_2025": sum(margin_post) / len(margin_post),
          "guidance": {"sales": guid_sales, "operatingIncome": guid_oi}, "year1Growth": year1_growth, "year1Margin": year1_margin,
          "rndAdjustment": RND_ADJUSTMENT}
(OUT / "stage2_assumptions.json").write_text(json.dumps(detail, indent=1, default=str))
for k in ("bear", "base", "bull"):
    w = wacc_cases[k]
    print(k, "beta %.3f ke %.4f wacc %.4f" % (w["leveredBeta"], w["costOfEquity"], w["wacc"]), "g1 %.4f m1 %.4f" % (year1_growth[k], year1_margin[k]))
print("rf", rf, "erp", erp, "terminal bear", round(market_terminal_bear, 4))
print("growth", {k: round(v, 4) for k, v in growth_history.items()}, "margins", round(detail["marginFY2017_2020"], 4), round(detail["marginFY2022_2025"], 4))
print("regressions", [(r["frequency"], r["years"], round(r["beta"], 3), round(r["r2"], 3)) for r in regressions])
