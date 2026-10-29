"""Trading comparables for WD-40 at 29 Aug 2025, on portable-spreadsheet.

Inputs: models/data/comps/peer_facts_2025-08-29.json (from comps_extract.py) and WD-40's own XBRL facts.
EBITDA = EBIT + D&A + listed one-off charges, each one-off traced to an XBRL fact filed by the cutoff.
The engine has no MEDIAN or PERCENTILE, so quartiles are computed here and written as labelled constants.
WD-40 is not in the peer set. Its own year-end multiples are shown separately as market context.
Run:  python -I models/comps.py  ->  models/out/comps/*, models/out/methods_comps.json
"""
import csv
import datetime as dt
import json
import pathlib
import statistics
import sys

import portable_spreadsheet as ps

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib.pss import export_cells, write_xlsx  # noqa: E402

DATA = HERE / "data"
OUT = HERE / "out" / "comps"
OUT.mkdir(parents=True, exist_ok=True)
F = json.loads((DATA / "comps" / "peer_facts_2025-08-29.json").read_text())["peers"]
SEC = {t: json.loads((DATA / "sec" / f"{t.lower()}_companyfacts.json").read_text())["facts"]["us-gaap"] for t in F}
CUT = "2025-08-29"


def fact(t, tag, start, end):
    vals = [f for f in SEC[t][tag]["units"]["USD"] if f.get("start") == start and f["end"] == end and f["filed"] <= CUT]
    assert vals, (t, tag, start, end)
    tenk = [f for f in vals if f["form"] == "10-K"]
    f = max(tenk or vals, key=lambda f: f["filed"])  # the annual report's figure wins over later re-tags
    return f["val"], f"{tag} {start} to {end}, {f['form']} accession {f['accn']}"


# One-off charges inside the LTM window, added back to EBIT. Sign: positive adds to EBIT.
ADJ = {
    "CHD": [("Intangible asset impairment, Q3 2024", *fact("CHD", "OtherAssetImpairmentCharges", "2024-01-01", "2024-12-31")),
            ("Finite-lived intangible impairment, H1 2025", *fact("CHD", "ImpairmentOfIntangibleAssetsFinitelived", "2025-01-01", "2025-06-30"))],
    "CLX": [("Loss on divestiture (business sold in FY2025)", -fact("CLX", "DisposalGroupNotDiscontinuedOperationGainLossOnDisposal", "2024-07-01", "2025-06-30")[0],
             fact("CLX", "DisposalGroupNotDiscontinuedOperationGainLossOnDisposal", "2024-07-01", "2025-06-30")[1])],
    "ENR": [("Restructuring costs, LTM", F["ENR"]["oneOffDetail"].get("RestructuringCharges", {}).get("value", 0) or None, "")],
    "RPM": [("Goodwill impairment", *fact("RPM", "GoodwillImpairmentLoss", "2024-06-01", "2025-05-31")),
            ("Restructuring charges", *fact("RPM", "RestructuringCharges", "2024-06-01", "2025-05-31"))],
    "KWR": [("Asset impairment, H1 2025", *fact("KWR", "AssetImpairmentCharges", "2025-01-01", "2025-06-30")),
            ("Restructuring, LTM", F["KWR"]["oneOffDetail"]["RestructuringCharges"]["value"], "RestructuringCharges, LTM from 10-K FY2024 and 10-Q Q2 2025")],
}
# Energizer tags restructuring as RestructuringCosts; take its LTM from the same filings.
enr_fy, s1 = fact("ENR", "RestructuringCosts", "2023-10-01", "2024-09-30")
enr_9m, s2 = fact("ENR", "RestructuringCosts", "2024-10-01", "2025-06-30")
enr_9p, s3 = fact("ENR", "RestructuringCosts", "2023-10-01", "2024-06-30")
ADJ["ENR"] = [("Restructuring costs, LTM", enr_fy + enr_9m - enr_9p, f"RestructuringCosts FY2024 + 9m FY2025 - 9m FY2024 ({s2})")]
# Quaker Houghton tags depreciation alone as DepreciationDepletionAndAmortization; add intangible amortization.
# No FY2024 or Q4 2024 amortization fact is tagged; Q4 2024 is estimated as the average of Q3 2024 and Q1 2025.
k_q3, a1 = fact("KWR", "AmortizationOfIntangibleAssets", "2024-07-01", "2024-09-30")
k_h1, a2 = fact("KWR", "AmortizationOfIntangibleAssets", "2025-01-01", "2025-06-30")
k_q1, a3 = fact("KWR", "AmortizationOfIntangibleAssets", "2025-01-01", "2025-03-31")
EXTRA_DA = {"KWR": (k_q3 + (k_q3 + k_q1) / 2 + k_h1, f"AmortizationOfIntangibleAssets Q3 2024 + H1 2025 ({a2}), plus Q4 2024 estimated as the average of Q3 2024 and Q1 2025 because it is not tagged")}
NOT_ADJUSTED = {"RPM": "A gain on the sale of a business in FY2025 is tagged but its placement in the income statement was not confirmed, so it is left in.",
                "KWR": "Company-defined adjustments beyond impairment and restructuring (integration costs, customer insolvency and others) are not added back.",
                "CLX": "Restructuring costs and ERP implementation costs that Clorox excludes from its own adjusted figures are not added back; no FY2025 amount is tagged.",
                "CHD": "", "ENR": "Other company-defined adjustments are not added back."}

TICKERS = list(F)
m = lambda x: x / 1e6  # noqa: E731
COLS = ["Price 29 Aug 2025", "Shares (m)", "Market cap", "Debt", "Cash", "Enterprise value", "LTM revenue", "LTM EBIT", "One-off charges added back",
        "LTM D&A", "Adjusted EBITDA", "Adjusted EBIT", "EV / adjusted EBITDA", "EV / adjusted EBIT"]
C = {k: i for i, k in enumerate(COLS)}
sh = ps.Sheet.create_new_sheet(len(TICKERS), len(COLS), name="Comps peers", rows_labels=[F[t]["name"].title() for t in TICKERS], columns_labels=COLS)
B = sh.fn.brackets
for i, t in enumerate(TICKERS):
    p = F[t]
    adj = sum(a[1] for a in ADJ[t] if a[1])
    da = m(p["da"]) + m(EXTRA_DA.get(t, (0,))[0])
    for col, val in [("Price 29 Aug 2025", p["price"]), ("Shares (m)", m(p["shares"])), ("Debt", m(p["debt"])), ("Cash", m(p["cash"])),
                     ("LTM revenue", m(p["revenue"])), ("LTM EBIT", m(p["ebit"])), ("One-off charges added back", m(adj)), ("LTM D&A", da)]:
        sh.iloc[i, C[col]] = float(val)
    r = lambda col: sh.iloc[i, C[col]]  # noqa: E731
    sh.iloc[i, C["Market cap"]] = r("Price 29 Aug 2025") * r("Shares (m)")
    sh.iloc[i, C["Enterprise value"]] = r("Market cap") + r("Debt") - r("Cash")
    sh.iloc[i, C["Adjusted EBIT"]] = r("LTM EBIT") + r("One-off charges added back")
    sh.iloc[i, C["Adjusted EBITDA"]] = r("Adjusted EBIT") + r("LTM D&A")
    sh.iloc[i, C["EV / adjusted EBITDA"]] = r("Enterprise value") / r("Adjusted EBITDA")
    sh.iloc[i, C["EV / adjusted EBIT"]] = r("Enterprise value") / r("Adjusted EBIT")

ev_ebitda = sorted(sh.iloc[i, C["EV / adjusted EBITDA"]].value for i in range(len(TICKERS)))
ev_ebit = sorted(sh.iloc[i, C["EV / adjusted EBIT"]].value for i in range(len(TICKERS)))


def quart(xs):
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return q[0], statistics.median(xs), q[2]


qa, qb = quart(ev_ebitda), quart(ev_ebit)

# WD-40 FY2025 metrics, from the case and SEC XBRL (FY ended 2025-08-31)
W = json.loads((DATA / "sec" / "wdfc_companyfacts.json").read_text())["facts"]["us-gaap"]
WD_CUT = "2025-10-27"  # FY2025 10-K filing date; later filings are outside the case
wd_da = [f["val"] for f in W["DepreciationDepletionAndAmortization"]["units"]["USD"] if f.get("start") == "2024-09-01" and f["end"] == "2025-08-31" and f["filed"] <= WD_CUT][0] / 1e6
WD = {"EBIT FY2025 (reported)": 103.793, "D&A FY2025": wd_da, "Debt": 86.995, "Cash": 58.13, "Shares, DCF denominator (m)": 13.633263}
VROWS = ["EBIT FY2025 (reported)", "D&A FY2025", "EBITDA FY2025", "Debt", "Cash", "Shares, DCF denominator (m)",
         "Peer EV / EBITDA (computed in Python from Comps peers)", "Implied enterprise value", "Implied equity value", "Value per share"]
VC = ["25th percentile", "Median", "75th percentile"]
val = ps.Sheet.create_new_sheet(len(VROWS), 3, name="Comps valuation", rows_labels=VROWS, columns_labels=VC)
V = {k: i for i, k in enumerate(VROWS)}
for j in range(3):
    for k, v in WD.items():
        val.iloc[V[k], j] = float(v)
    rc = lambda row: val.iloc[V[row], j]  # noqa: E731
    val.iloc[V["EBITDA FY2025"], j] = rc("EBIT FY2025 (reported)") + rc("D&A FY2025")
    val.iloc[V["Peer EV / EBITDA (computed in Python from Comps peers)"], j] = float(qa[j])
    val.iloc[V["Implied enterprise value"], j] = rc("EBITDA FY2025") * rc("Peer EV / EBITDA (computed in Python from Comps peers)")
    val.iloc[V["Implied equity value"], j] = rc("Implied enterprise value") - rc("Debt") + rc("Cash")
    val.iloc[V["Value per share"], j] = rc("Implied equity value") / rc("Shares, DCF denominator (m)")
per_share = [val.iloc[V["Value per share"], j].value for j in range(3)]

# WD-40's own trailing EV/EBITDA at fiscal year-ends (market context, not a valuation method)
def wd_fy(tag, year):
    fs = [f for f in W[tag]["units"]["USD"] if f.get("start", "").startswith(f"{year - 1}-09") and f["end"] == f"{year}-08-31" and f["filed"] <= WD_CUT]
    return max(fs, key=lambda f: f["filed"])["val"] / 1e6


def wd_inst(tags, year):
    for tag in tags:
        fs = [f for f in W.get(tag, {}).get("units", {}).get("USD", []) if f["end"] == f"{year}-08-31" and "start" not in f and f["filed"] <= WD_CUT]
        if fs:
            return max(fs, key=lambda f: f["filed"])["val"] / 1e6
    return 0.0


daily = json.loads((DATA / "market" / "yahoo_WDFC_daily_2020-08_2025-08.json").read_text())["chart"]["result"][0]
closes = {(dt.datetime.utcfromtimestamp(ts) - dt.timedelta(hours=4)).date(): c for ts, c in zip(daily["timestamp"], daily["indicators"]["quote"][0]["close"]) if c}
WD_SHARES = {f["end"]: f["val"] / 1e6 for f in json.loads((DATA / "sec" / "wdfc_companyfacts.json").read_text())["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"] if f["filed"] <= WD_CUT}
own = []
for y in range(2021, 2026):
    fye = dt.date(y, 8, 31)
    day = max(d for d in closes if d <= fye)
    sh_date = min((d for d in WD_SHARES if d >= f"{y}-09-01"), default=None)
    shares_y = WD_SHARES[sh_date] if sh_date else 13.527614
    debt_y = wd_inst(["LongTermDebtNoncurrent"], y) + wd_inst(["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"], y)
    cash_y = wd_inst(["CashAndCashEquivalentsAtCarryingValue"], y)
    ebitda_y = wd_fy("OperatingIncomeLoss", y) + wd_fy("DepreciationDepletionAndAmortization", y)
    ev = closes[day] * shares_y + debt_y - cash_y
    own.append({"fiscalYear": y, "priceDate": day.isoformat(), "price": closes[day], "shares": shares_y, "sharesDate": sh_date, "debt": debt_y, "cash": cash_y,
                "ebitda": ebitda_y, "ev": ev, "evToEbitda": ev / ebitda_y})

write_xlsx([sh, val], OUT / "wd40_comps.xlsx")
cells = export_cells([sh, val])
(OUT / "comps_cells.json").write_text(json.dumps(cells, indent=1))

src_ids = {t: f"sec-{t.lower()}" for t in TICKERS}
sources = {f"sec-{t.lower()}": {"title": f"{F[t]['name'].title()} {F[t]['filing']['form']} filed {F[t]['filing']['filed']} (SEC XBRL company facts)",
                                "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={t}&type=10-&dateb=20250829", "asOf": CUT} for t in TICKERS}
sources["yahoo-peers"] = {"title": "Peer closing prices on 29 Aug 2025 (Yahoo Finance chart API)", "file": "models/data/market/", "asOf": CUT}
f1 = lambda x: f"{x:,.1f}"  # noqa: E731
table = [["Company", "Why it is here", "EV ($m)", "Adj. EBITDA ($m)", "EV / EBITDA", "EV / EBIT", "One-offs added ($m)"]]
for i, t in enumerate(TICKERS):
    g = lambda col: sh.iloc[i, C[col]].value  # noqa: E731
    table.append([F[t]["name"].title(), F[t]["why"], f1(g("Enterprise value")), f1(g("Adjusted EBITDA")), f"{g('EV / adjusted EBITDA'):.1f}x", f"{g('EV / adjusted EBIT'):.1f}x", f1(g("One-off charges added back"))])
table.append(["Quartiles (25th / median / 75th)", "", "", "", " / ".join(f"{x:.1f}x" for x in qa), " / ".join(f"{x:.1f}x" for x in qb), ""])
table.append(["WD-40 at $216.04", "Not in the peer set", f1(216.04 * 13.527614 + 86.995 - 58.13), f1(103.793 + wd_da), f"{(216.04 * 13.527614 + 86.995 - 58.13) / (103.793 + wd_da):.1f}x", f"{(216.04 * 13.527614 + 86.995 - 58.13) / 103.793:.1f}x", ""])
method = {
    "id": "comps", "group": "multiples", "label": "Trading comparables", "sublabel": "EV / EBITDA, 25th to 75th percentile of 5 peers",
    "kind": "range", "low": per_share[0], "base": per_share[1], "high": per_share[2], "status": "verified-js",
    "note": (f"Five listed companies that share WD-40's channels or products, priced at the 29 Aug 2025 close, with trailing-twelve-month results from the latest filing made by that date. "
             f"One-off impairments, restructuring and a divestiture loss are added back to EBITDA where tagged; other company-defined adjustments are not. "
             f"The peer quartiles ({qa[0]:.1f}x / {qa[1]:.1f}x / {qa[2]:.1f}x EV/EBITDA) are applied to WD-40's FY2025 EBITDA of ${103.793 + wd_da:.1f}m. "
             f"WD-40 itself traded at {(216.04 * 13.527614 + 86.995 - 58.13) / (103.793 + wd_da):.1f}x, above every peer."),
    "table": table,
    "adjustments": {t: [{"item": a[0], "usdMillions": (a[1] or 0) / 1e6, "source": a[2]} for a in ADJ[t]] + ([{"item": "Intangible amortization (not in D&A tag)", "usdMillions": EXTRA_DA[t][0] / 1e6, "source": EXTRA_DA[t][1]}] if t in EXTRA_DA else []) for t in TICKERS},
    "notAdjusted": {t: v for t, v in NOT_ADJUSTED.items() if v},
    "quartiles": {"evToEbitda": qa, "evToEbit": qb}, "ownHistory": own,
    "cells": ["Comps valuation!B11", "Comps valuation!C11", "Comps valuation!D11"],
    "sourceIds": list(src_ids.values()) + ["yahoo-peers"],
}
own_method = {
    "id": "own-history", "group": "market", "label": "WD-40's own EV / EBITDA", "sublabel": "fiscal year-ends 2021-2025, applied to FY2025",
    "kind": "range", "status": "verified-js",
    "low": None, "base": None, "high": None,
    "note": "WD-40's trailing EV/EBITDA at each fiscal year-end from 2021 to 2025, applied to FY2025 EBITDA. It shows the multiples the market has paid for this company, as context for the methods above.",
    "table": [["Fiscal year-end", "Close", "EV ($m)", "EBITDA ($m)", "EV / EBITDA"]] + [[o["priceDate"], f"${o['price']:.2f}", f1(o["ev"]), f1(o["ebitda"]), f"{o['evToEbitda']:.1f}x"] for o in own],
    "sourceIds": ["sec-xbrl", "price-close"],
}
ebitda25 = 103.793 + wd_da
lo_m, hi_m = min(o["evToEbitda"] for o in own), max(o["evToEbitda"] for o in own)
own_method["low"] = (ebitda25 * lo_m - 86.995 + 58.13) / 13.633263
own_method["high"] = (ebitda25 * hi_m - 86.995 + 58.13) / 13.633263
own_method["base"] = None
(HERE / "out" / "methods_comps.json").write_text(json.dumps({"methods": [method, own_method], "sources": sources,
                                                             "books": {"Comps peers": "comps_cells", "Comps valuation": "comps_cells"}}, indent=1))
print("EV/EBITDA", [round(x, 2) for x in ev_ebitda], "quartiles", [round(x, 2) for x in qa])
print("EV/EBIT", [round(x, 2) for x in ev_ebit], "quartiles", [round(x, 2) for x in qb])
print("per share", [round(x, 2) for x in per_share], "WD-40 EBITDA", round(ebitda25, 3))
print("own history", [(o["fiscalYear"], round(o["price"], 2), round(o["shares"], 3), round(o["debt"], 1), round(o["cash"], 1), round(o["ebitda"], 1), round(o["evToEbitda"], 1)) for o in own])
print("own-history per share", round(own_method["low"], 2), round(own_method["high"], 2))
