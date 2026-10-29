"""Peer financials as known on 29 Aug 2025, from SEC XBRL company facts (only facts filed on or before that date).

LTM for duration items = last fiscal year + current year-to-date - prior year-to-date of the same length,
taken from the latest 10-Q or 10-K filed by the cutoff. Balance items come from that filing's balance sheet.
EBIT is reported operating income; where a company does not report it, pre-tax income + interest expense
(documented per peer). Writes models/data/comps/peer_facts_2025-08-29.json (committed), with the accession
number, form, filing date and period of every number.
Run:  python -I models/comps_extract.py   (needs models/data/sec/<ticker>_companyfacts.json; see README in models/data)
"""
import datetime as dt
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
CUT = "2025-08-29"
PEERS = {
    "CHD": "Branded household and personal-care products, asset-light, outsourced manufacturing in part.",
    "CLX": "Branded household cleaning and maintenance chemicals sold through the same retail channels.",
    "ENR": "Owns the Armor All and STP auto-care chemical brands alongside its battery business.",
    "RPM": "Rust-Oleum and DAP consumer maintenance and repair brands within a specialty-coatings group.",
    "KWR": "Industrial process fluids and lubricants, the specialty-chemical side of WD-40's industrial users.",
}
REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
EBIT = ["OperatingIncomeLoss"]
PRETAX = ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
          "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]
INTEREST = ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]
DA = ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization"]
NET = ["NetIncomeLoss", "NetIncomeLossAttributableToParent"]
EPS = ["EarningsPerShareDiluted"]
ONE_OFF = ["GoodwillImpairmentLoss", "ImpairmentOfIntangibleAssetsExcludingGoodwill", "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill",
           "AssetImpairmentCharges", "GoodwillAndIntangibleAssetImpairment", "RestructuringCharges"]
CASH = ["CashAndCashEquivalentsAtCarryingValue"]


def facts(t):
    d = json.loads((DATA / "sec" / f"{t.lower()}_companyfacts.json").read_text())
    return d["entityName"], d["facts"].get("us-gaap", {}), d["facts"].get("dei", {})


def usd(g, tag):
    u = g.get(tag, {}).get("units", {})
    return [f for f in u.get("USD", u.get("USD/shares", [])) if f["filed"] <= CUT and f["form"] in ("10-K", "10-Q", "10-K/A", "10-Q/A")]


def months(f):
    s, e = dt.date.fromisoformat(f["start"]), dt.date.fromisoformat(f["end"])
    return round((e - s).days / 30.44)


def latest_filing(g):
    fs = [f for tag in REVENUE + EBIT + PRETAX for f in usd(g, tag)]
    last = max(fs, key=lambda f: (f["filed"], f["end"]))
    return last["accn"], last["form"], last["filed"]


def ltm(g, tags, accn):
    """Return (value, detail) for the trailing twelve months ending at the latest period of filing accn."""
    for tag in tags:
        fs = usd(g, tag)
        cur = [f for f in fs if f["accn"] == accn and "start" in f]
        if not cur:
            continue
        end = max(f["end"] for f in cur)
        ytd = max((f for f in cur if f["end"] == end), key=months)
        m = months(ytd)
        if m == 12:
            return ytd["val"], {"tag": tag, "method": "fiscal year", "period": [ytd["start"], ytd["end"]], "accn": accn}
        fy_end = (dt.date.fromisoformat(ytd["start"]) - dt.timedelta(days=1)).isoformat()
        fy = [f for f in fs if "start" in f and f["end"] == fy_end and months(f) == 12]
        prior_end = (dt.date.fromisoformat(ytd["end"]) - dt.timedelta(days=365)).isoformat()
        prior = [f for f in fs if "start" in f and months(f) == m and abs((dt.date.fromisoformat(f["end"]) - dt.date.fromisoformat(prior_end)).days) <= 7]
        if fy and prior:
            fyv = max(fy, key=lambda f: f["filed"])
            pv = max(prior, key=lambda f: f["filed"])
            return fyv["val"] + ytd["val"] - pv["val"], {"tag": tag, "method": f"FY {fyv['end']} + {m}m to {ytd['end']} - {m}m to {pv['end']}",
                                                         "accn": accn, "fyAccn": fyv["accn"], "priorAccn": pv["accn"]}
    return None, {"tag": None, "method": "not found", "accn": accn}


def instant(g, tags, accn):
    for tag in tags:
        fs = [f for f in usd(g, tag) if f["accn"] == accn and "start" not in f]
        if fs:
            f = max(fs, key=lambda f: f["end"])
            return f["val"], {"tag": tag, "date": f["end"], "accn": accn}
    return None, {"tag": None, "accn": accn}


def debt(g, accn):
    """Gross borrowings at the filing's balance sheet date, excluding operating leases."""
    parts = {}
    for tag in ["LongTermDebtNoncurrent", "LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings", "CommercialPaper", "LongTermDebt",
                "LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent", "NotesPayableCurrent"]:
        v, d = instant(g, [tag], accn)
        if v is not None:
            parts[tag] = (v, d["date"])
    if "LongTermDebt" in parts:
        total = parts["LongTermDebt"][0]
        used = ["LongTermDebt"]
    elif "LongTermDebtAndCapitalLeaseObligations" in parts:
        total = parts["LongTermDebtAndCapitalLeaseObligations"][0] + parts.get("LongTermDebtAndCapitalLeaseObligationsCurrent", (0,))[0]
        used = ["LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent"]
    else:
        total = parts.get("LongTermDebtNoncurrent", (0,))[0] + parts.get("LongTermDebtCurrent", (0,))[0]
        used = ["LongTermDebtNoncurrent", "LongTermDebtCurrent"]
    if "DebtCurrent" in parts and "LongTermDebtCurrent" not in used and "LongTermDebt" not in used:
        total += parts["DebtCurrent"][0]
        used.append("DebtCurrent")
    for t in ["ShortTermBorrowings", "CommercialPaper", "NotesPayableCurrent"]:
        if t in parts and parts[t][1] == max(p[1] for p in parts.values()):
            total += parts[t][0]
            used.append(t)
    return total, {"components": {k: parts[k] for k in used if k in parts}, "allTags": parts, "accn": accn}


def shares(dei, accn_filed):
    so = [f for f in dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", []) if f["filed"] <= CUT]
    f = max(so, key=lambda f: (f["filed"], f["end"]))
    same = [x["val"] for x in so if x["accn"] == f["accn"]]
    return sum(same), {"date": f["end"], "accn": f["accn"], "filed": f["filed"], "classes": len(same)}


def close_price(t):
    d = json.loads((DATA / "market" / f"yahoo_{t}_daily_2025-08-20_2025-09-02.json").read_text())["chart"]["result"][0]
    for ts, c in zip(d["timestamp"], d["indicators"]["quote"][0]["close"]):
        day = (dt.datetime.utcfromtimestamp(ts) - dt.timedelta(hours=4)).date().isoformat()
        if day == CUT:
            return c
    raise SystemExit(f"no close for {t} on {CUT}")


out = {}
for t, why in PEERS.items():
    name, g, dei = facts(t)
    accn, form, filed = latest_filing(g)
    rev, rev_d = ltm(g, REVENUE, accn)
    ebit, ebit_d = ltm(g, EBIT, accn)
    if ebit is None:
        pt, pt_d = ltm(g, PRETAX, accn)
        it, it_d = ltm(g, INTEREST, accn)
        ebit = pt + it
        ebit_d = {"method": "pre-tax income + interest expense", "pretax": pt_d, "interest": it_d, "accn": accn}
    da, da_d = ltm(g, DA, accn)
    ni, ni_d = ltm(g, NET, accn)
    eps, eps_d = ltm(g, EPS, accn)
    one_off, one_off_d = 0.0, {}
    for tag in ONE_OFF:
        v, d = ltm(g, [tag], accn)
        if v:
            one_off += v
            one_off_d[tag] = {"value": v, **d}
    cash, cash_d = instant(g, CASH, accn)
    dbt, dbt_d = debt(g, accn)
    sh, sh_d = shares(dei, filed)
    price = close_price(t)
    out[t] = {"name": name, "why": why, "filing": {"accn": accn, "form": form, "filed": filed}, "price": price, "priceDate": CUT,
              "shares": sh, "sharesDetail": sh_d, "debt": dbt, "debtDetail": dbt_d, "cash": cash, "cashDetail": cash_d,
              "revenue": rev, "revenueDetail": rev_d, "ebit": ebit, "ebitDetail": ebit_d, "da": da, "daDetail": da_d,
              "oneOffCharges": one_off, "oneOffDetail": one_off_d, "netIncome": ni, "netIncomeDetail": ni_d, "epsDiluted": eps, "epsDetail": eps_d}
(DATA / "comps").mkdir(exist_ok=True)
(DATA / "comps" / "peer_facts_2025-08-29.json").write_bytes(json.dumps({"cutoff": CUT, "peers": out}, indent=1).encode("utf-8"))
for t, p in out.items():
    m = lambda x: None if x is None else round(x / 1e6, 1)  # noqa: E731
    print(t, p["filing"]["form"], p["filing"]["filed"], "px", round(p["price"], 2), "sh(m)", round(p["shares"] / 1e6, 2), "debt", m(p["debt"]), "cash", m(p["cash"]),
          "rev", m(p["revenue"]), "ebit", m(p["ebit"]), "da", m(p["da"]), "oneoff", m(p["oneOffCharges"]), "ni", m(p["netIncome"]), "eps", p["epsDiluted"])
    print("    ebit:", p["ebitDetail"].get("method"), "| da:", p["daDetail"].get("tag"), p["daDetail"].get("method"), "| debt:", {k: (round(v[0] / 1e6, 1), v[1]) for k, v in p["debtDetail"]["components"].items()}, "| oneoff:", {k: round(v["value"] / 1e6, 1) for k, v in p["oneOffDetail"].items()})
