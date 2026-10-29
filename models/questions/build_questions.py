"""WD-40 diligence questions adapted from the five benchmarks, each split into narrow sub-questions.

Selection: models/out/questions_merged.jsonl (extract.py). Answers are computed here from SEC XBRL facts filed by
27 Oct 2025 (the FY2025 10-K date), the original case's proposals, the FY2025 8-K and 10-K passages recorded below,
and the model outputs. Following The Mom Test, a judgement question ("Is WD-40 capital-intensive?") is broken into
questions about specific past facts, then a question about which model input the facts test. Forecast questions
name the object, period, threshold and resolution rule; later information is computed from the FY2026 filing,
labelled as such and never used in a valuation.

The set merges the questions of both earlier implementations (models/questions/merge_inputs.json) by meaning:
each of their questions is kept, merged into another, or excluded with a reason, and the build stops if one has
no disposition. Benchmark origins are pinned by record id and checked against the record's text.
Run:  python -I models/questions/build_questions.py  ->  models/questions/questions.json, reports/06-questions.md
"""
import collections
import datetime as dt
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "models" / "out"
CUT = "2025-10-27"


def fail(msg):
    sys.exit(f"build_questions: {msg}")


MERGED = [json.loads(l) for l in (OUT / "questions_merged.jsonl").read_text(encoding="utf-8").splitlines()]
G = json.loads((ROOT / "models" / "data" / "sec" / "wdfc_companyfacts.json").read_text())["facts"]["us-gaap"]
GC = json.loads((OUT / "ginzu_cases.json").read_text())["cases"]
CORE = json.loads((OUT / "valuation_book" / "core_results.json").read_text())
COMPS = json.loads((OUT / "methods_comps.json").read_text())["methods"][0]
A2 = json.loads((OUT / "stage2_assumptions.json").read_text())
EV = json.loads((OUT / "scenarios_eval.json").read_text())
RV = {r["id"]: r for r in EV["reverseFromBase"]}
SC = json.loads((ROOT / "models" / "scenarios.json").read_text(encoding="utf-8"))
RES = json.loads((ROOT / "models" / "data" / "research.json").read_text(encoding="utf-8"))
MERGE_INPUTS = json.loads((ROOT / "models" / "questions" / "merge_inputs.json").read_text(encoding="utf-8"))
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CASE = json.JSONDecoder().raw_decode(HTML, HTML.index("const BUNDLED_CASE=") + len("const BUNDLED_CASE="))[0]
PROP = {p["cell"]: p for p in CASE["proposals"]}

# XBRL: the unit comes from the fact's metadata; among 10-K facts for the period, the latest accession filed by
# the cut is used, and every fact of that accession for the period must agree.
SCALE = {"USD": 1e6, "USD/shares": 1.0}


def pick(tag, end, duration=True, cut=CUT):
    units = G[tag]["units"]
    if len(units) != 1 or next(iter(units)) not in SCALE:
        fail(f"{tag}: unexpected units {list(units)}")
    unit, rows = next(iter(units.items()))
    cand = [f for f in rows if f["form"] == "10-K" and f["filed"] <= cut and f["end"] == end and ("start" in f) == duration
            and (not duration or 360 < (dt.date.fromisoformat(f["end"]) - dt.date.fromisoformat(f["start"])).days < 372)]
    if not cand:
        fail(f"{tag}: no 10-K fact for the period ending {end} filed by {cut}")
    accn = max(cand, key=lambda f: (f["filed"], f["accn"]))["accn"]
    vals = {f["val"] for f in cand if f["accn"] == accn}
    if len(vals) != 1:
        fail(f"{tag} {end}: accession {accn} reports {sorted(vals)}")
    return vals.pop() / SCALE[unit]


def v(tag, year):
    return pick(tag, f"{year}-08-31")


def b(tag, year):
    return pick(tag, f"{year}-08-31", duration=False)


Y5 = range(2021, 2026)
rev = {y: v("RevenueFromContractWithCustomerExcludingAssessedTax", y) for y in Y5}
gp = {y: v("GrossProfit", y) for y in Y5}
oi = {y: v("OperatingIncomeLoss", y) for y in Y5}
cogs = {y: v("CostOfGoodsAndServicesSold", y) for y in Y5}
capex = {y: v("PaymentsToAcquirePropertyPlantAndEquipment", y) for y in Y5}
da = {y: v("DepreciationDepletionAndAmortization", y) for y in Y5}
ocf = {y: v("NetCashProvidedByUsedInOperatingActivities", y) for y in Y5}
ni = {y: v("NetIncomeLoss", y) for y in Y5}
dps = {y: v("CommonStockDividendsPerShareCashPaid", y) for y in Y5}
tax = {y: v("IncomeTaxExpenseBenefit", y) for y in (2024, 2025)}
pretax = {y: v("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", y) for y in (2024, 2025)}
inv = {y: b("InventoryNet", y) for y in Y5}
ar = {y: b("AccountsReceivableNetCurrent", y) for y in (2024, 2025)}
ap = {y: b("AccountsPayableCurrent", y) for y in (2024, 2025)}
debt = {y: b("LongTermDebtNoncurrent", y) + b("ShortTermBorrowings", y) for y in (2024, 2025)}
cash25 = b("CashAndCashEquivalentsAtCarryingValue", 2025)
inv_rise22 = v("IncreaseDecreaseInInventories", 2022)
eps25 = v("EarningsPerShareDiluted", 2025)
interest25 = v("InterestExpenseNonoperating", 2025)
cf25 = {k: v(t, 2025) for k, t in [("operating", "NetCashProvidedByUsedInOperatingActivities"), ("investing", "NetCashProvidedByUsedInInvestingActivities"),
                                    ("financing", "NetCashProvidedByUsedInFinancingActivities")]}
buyback25 = v("PaymentsForRepurchaseOfCommonStock", 2025)
dividends25 = v("PaymentsOfDividends", 2025)
fcf = {y: ocf[y] - capex[y] for y in ocf}
p = lambda x, d=1: f"{x * 100:.{d}f}%"  # noqa: E731
m = lambda x, d=1: f"${x:,.{d}f}m"  # noqa: E731

# figures read from filing text rather than XBRL; each is cited where it is used
TAX_BENEFIT = 11.929       # FY2025 release of an uncertain-tax-position reserve, 10-K note 15 (wdfc25-tax)
NON_GAAP_EPS = 5.82        # FY2025 non-GAAP diluted EPS, 8-K of 22 Oct 2025

# later information: the FY2026 10-K, located by period and accession, filed after the case date
fy26 = [f for f in G["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"] if f["form"] == "10-K" and f["end"] == "2026-08-31" and "start" in f]
FY26 = None
if fy26:
    accns = {f["accn"] for f in fy26}
    if len(accns) != 1:
        fail(f"several FY2026 10-K accessions: {sorted(accns)}")
    a = accns.pop()
    filed = fy26[0]["filed"]
    later = lambda tag: next(f["val"] for f in G[tag]["units"]["USD"] if f["accn"] == a and f["end"] == "2026-08-31" and "start" in f) / 1e6  # noqa: E731
    FY26 = {"accn": a, "filed": filed, "revenue": later("RevenueFromContractWithCustomerExcludingAssessedTax"), "grossProfit": later("GrossProfit")}
JULY = next(g for g in RES["guidance"] if g["id"] == "fy26-july-revised")
GUIDE = next(g for g in RES["guidance"] if g["id"] == "fy26-original")

S10K, S8K, SX, MB, JULY_SRC, GUIDE_SRC = "wdfc25-10k", "wdfc-8k-2025-10-22", "sec-xbrl", "model-build", "wd40-fy26-guidance-july-revision", "wd40-fy25-guidance-original"
SOURCES = {
    S10K: {"title": "WD-40 Company FY2025 Form 10-K", "url": "https://www.sec.gov/Archives/edgar/data/105132/000010513225000067/wdfc-20250831.htm", "publishedAt": "2025-10-27"},
    MB: {"title": "Scenario and method workbook built from the scenario inputs (models/build.py)", "url": "models/excel/wd40_valuation.xlsx"},
}
if FY26:
    SOURCES["wdfc26-10k"] = {"title": "WD-40 Company FY2026 Form 10-K (later information, outside the case)", "publishedAt": FY26["filed"],
                             "url": f"https://www.sec.gov/Archives/edgar/data/105132/{FY26['accn'].replace('-', '')}/{FY26['accn']}-index.htm"}
POOL = {s["id"]: {k: s[k] for k in ("title", "url", "publishedAt", "asOf", "locator") if s.get(k)} for s in CASE["sources"] + RES["sources"]}

# benchmark origins, pinned by record id; the pattern must occur in the record's text
ORIGINS = {
    ("FinanceBench", "financebench_id_00956"): r"high growth",
    ("FinanceBench", "financebench_id_01198"): r"drove revenue change",
    ("FinanceBench", "financebench_id_00684"): r"gross margin",
    ("FinanceBench", "financebench_id_01226"): r"operating margin change",
    ("FinanceBench", "financebench_id_00685"): r"gross margins",
    ("FinanceBench", "financebench_id_00499"): r"capital-intensive",
    ("FinanceBench", "financebench_id_00540"): r"inventory",
    ("FinanceBench", "financebench_id_03029"): r"capital expenditure",
    ("FinanceBench", "financebench_id_01279"): r"operations, investing, and financing",
    ("FinanceBench", "financebench_id_00591"): r"cashflow conversion",
    ("FinanceBench", "financebench_id_04854"): r"free cash flow",
    ("FinanceBench", "financebench_id_01351"): r"effective tax rate",
    ("FinanceBench", "financebench_id_00517"): r"more than 20%",
    ("FinanceBench", "financebench_id_01244"): r"dividends",
    ("FinanceBench", "financebench_id_01858"): r"dividend",
    ("FinanceBench", "financebench_id_06272"): r"payout ratio",
    ("FinanceBench", "financebench_id_00552"): r"debt",
    ("FinanceBench", "financebench_id_00438"): r"operating margin",
    ("FinanceBench", "financebench_id_01319"): r"restructuring",
    ("FinLFQA", "validation-34"): r"free cash flow",
    ("FinLFQA", "validation-82"): r"effective tax rate",
    ("FinLFQA", "validation-97"): r"tax-related adjustments",
    ("FinLFQA", "validation-170"): r"Return on Equity",
    ("FinLFQA", "validation-221"): r"dividend.*repurchases",
    ("FinLFQA", "validation-41"): r"dividends",
    ("FinCausal", "0209.00019"): r"disposals",
    ("FinCausal", "0100.00018"): r"oil prices",
    ("PE Bench", "voltaic-01-historicals"): r"historicals",
    ("PE Bench", "voltaic-02-comparables"): r"comparable|comps|trading",
    ("PE Bench", "voltaic-04-ebitda-bridge"): r"EBITDA",
    ("PE Bench", "voltaic-05-nwc-peg"): r"working capital",
    ("PE Bench", "voltaic-07-operating-model"): r"operating model",
    ("PE Bench", "voltaic-08-debt-schedule"): r"debt",
    ("PE Bench", "voltaic-09-sources-uses"): r"sources",
    ("PE Bench", "voltaic-11-returns-waterfall"): r"return|waterfall",
}
REC = {(r["source"], r["sourceId"]): r for r in MERGED}


def origin(source, sid, note=""):
    rec = REC.get((source, sid))
    if rec is None or (source, sid) not in ORIGINS:
        fail(f"origin {source} {sid} is not a pinned record")
    body = " ".join(filter(None, [rec.get("question"), rec.get("text"), rec.get("cause"), rec.get("effect")]))
    if not re.search(ORIGINS[(source, sid)], body, re.I):
        fail(f"origin {source} {sid} no longer matches /{ORIGINS[(source, sid)]}/")
    o = {"key": f"{source}:{sid}", "source": source, "sourceId": sid, "dataset": rec["dataset"], "revision": rec["revision"],
         "datasetSha256": rec["datasetSha256"], "datasetUrl": rec["datasetUrl"], "licenseKnown": rec["licenseKnown"], "note": note}
    if rec.get("question"):
        o["originalText"] = re.sub(r"\s+", " ", rec["question"]).strip()[:240]
    if source == "FinCausal":
        o.update({"text": rec["text"], "cause": rec["cause"], "effect": rec["effect"]})
    return o


topics = []


def topic(tid, title, parent, origins, leaves, adaptation):
    keys = {o["key"] for o in origins}
    for l_ in leaves:
        if not set(l_["origins"]) <= keys:
            fail(f"{l_['id']}: origins {sorted(set(l_['origins']) - keys)} are not listed on topic {tid}")
    unused = keys - {k for l_ in leaves for k in l_["origins"]}
    if unused:
        fail(f"topic {tid}: origins {sorted(unused)} are not used by any question")
    topics.append({"id": tid, "title": title, "parent": parent, "origins": origins, "adaptation": adaptation, "leaves": leaves})


def leaf(lid, purpose, text, answer, covers, origins, status="answered", evidence=(), cells=(), methods=(), resolution=None, later=None):
    if not evidence:
        fail(f"{lid}: no evidence")
    return {"id": lid, "purpose": purpose, "text": text, "answer": answer, "status": status, "evidence": list(evidence),
            "cells": list(cells), "methods": list(methods), "resolution": resolution, "laterInformation": later,
            "origins": list(origins), "covers": list(covers)}


def need(cond, msg):
    if not cond:
        fail(msg)


drv = {k: {d: c["drivers"][d]["value"] for d in c["drivers"]} for k, c in GC.items()}
CASES = [("bear", "Bear"), ("base", "Base"), ("bull", "Bull")]
terminal_roic = {k: (d["roicT"] if d["roicOverride"] == 1 else d["waccT"]) for k, d in drv.items()}

# ---------------------------------------------------------------- growth
cagr = (rev[2025] / rev[2021]) ** 0.25 - 1
g25 = rev[2025] / rev[2024] - 1
reg = SC["regional"]
gap = reg["base"]["perimeterBound"]["unassignedFY2025Revenue"]
need(abs(rev[2025] - GUIDE["fy25ProFormaCurrencyAdjustedRevenueApprox"] - gap) < 1e-6, "perimeter gap does not match reported revenue minus the pro forma base")
rates = ", ".join(lab + " " + "/".join(f"{reg[k]['rates'][r] * 100:.0f}" for r in ("americas", "eimea", "asiaPacific")) + "%" for k, lab in CASES)
mid = (GUIDE["netSalesLow"] + GUIDE["netSalesHigh"]) / 2
FB, LF, PE, FC = "FinanceBench", "FinLFQA", "PE Bench", "FinCausal"
later_rev = None
if FY26:
    later_rev = {"text": f"The FY2026 10-K reports net sales of {m(FY26['revenue'])}. That is reported revenue: it includes the Americas homecare and cleaning brands, which the company moved back from held for sale to held for use in July 2026, and currency translation. It is not on the guidance basis, so it does not resolve the question; the constant-currency figure on the original perimeter was not collected.",
                 "sourceIds": ["wdfc26-10k", JULY_SRC]}
topic("growth", "Revenue growth", "Is WD-40's revenue growth in line with the growth the scenarios assume?",
      [origin(FB, "financebench_id_00956"), origin(FB, "financebench_id_01198"), origin(PE, "voltaic-01-historicals"),
       origin(PE, "voltaic-07-operating-model", "The operating-model task asks for a revenue build with stated drivers and a test against later results."),
       origin(FC, "0209.00019", "A cause-effect pair about disposals changing reported income; the WD-40 question asks how a planned sale changes the revenue base.")],
      [leaf("growth-1", "fact", "What were net sales in FY2021, FY2024 and FY2025, and the compound annual growth rate from FY2021 to FY2025?",
            f"{m(rev[2021])} in FY2021, {m(rev[2024])} in FY2024 and {m(rev[2025])} in FY2025: {p(cagr)} a year from FY2021. FY2025 and FY2024 are the model's starting revenue.",
            ["valuation-range:growth-1", "main:revenue-base"], [f"{PE}:voltaic-01-historicals", f"{FB}:financebench_id_00956"],
            evidence=[SX, "wdfc25-is"], cells=["Input sheet!B11", "Input sheet!C11"]),
       leaf("growth-2", "fact", "How much did net sales grow in FY2025, and how much of the change came from volume, price and currency?",
            f"{p(g25, 2)}, or {m(rev[2025] - rev[2024])}. Volume added about $25.2m, price about $5.6m and currency translation took off $1.4m.",
            ["valuation-range:growth-2", "main:revenue-growth"], [f"{FB}:financebench_id_01198"], evidence=[SX, S10K]),
       leaf("growth-3", "fact", "What growth did management guide for FY2026, from what base and at what exchange rates?",
            f"{p(GUIDE['growthLow'], 0)}-{p(GUIDE['growthHigh'], 0)} from FY2025 pro forma results, which exclude the Americas homecare and cleaning brands held for sale, at FY2025 average exchange rates: ${GUIDE['netSalesLow']:.0f}-{GUIDE['netSalesHigh']:.0f}m.",
            ["valuation-range:growth-3"], [f"{PE}:voltaic-07-operating-model"], evidence=[S8K]),
       leaf("growth-perimeter", "calculation", "How much FY2025 revenue does the guidance base leave out, and does the release say what the excluded brands sell?",
            f"The guidance starts from currency-adjusted pro forma FY2025 net sales of about ${GUIDE['fy25ProFormaCurrencyAdjustedRevenueApprox']:.0f}m, against {m(rev[2025])} reported, so about {m(gap)} sits outside the base. The release does not split that amount, so it only bounds the excluded brands' FY2025 sales from above. The release's ${GUIDE['divestmentFailureIncrement']['netSalesApprox']:.1f}m is a different figure: how much higher FY2026 net sales guidance would be if the sale did not happen. The scenarios grow reported revenue and assume no sale proceeds. Taking the whole {m(gap)} out of the Americas would change Base growth in years 2-5 by {reg['base']['perimeterBound']['differencePp']:.2f} points.",
            ["main:risks-disposal"], [f"{FC}:0209.00019"], evidence=[GUIDE_SRC, MB], cells=["Input sheet!B26", "Input sheet!B28"], methods=["dcf"],
            later={"text": f"In July 2026 the company moved the brands from held for sale back to held for use and put their contribution at about ${JULY['reclassifiedBrandsNetSalesApprox']:.0f}m of net sales and ${JULY['reclassifiedBrandsOperatingIncomeApprox']:.1f}m of operating income.",
                   "sourceIds": [JULY_SRC]}),
       leaf("growth-4", "assumption", "Which growth rates do the scenarios use, and how do they compare with the FY2021-FY2025 rate?",
            f"Year 1 is set at the guidance range on the reported base: " + ", ".join(f"{lab} {p(drv[k]['growth1'], 2)}" for k, lab in CASES)
            + f". Years 2-5 come from a regional build (Americas/EIMEA/Asia-Pacific: {rates}; analyst assumptions), compressed to one rate: "
            + ", ".join(f"{lab} {p(drv[k]['growth25'], 2)}" for k, lab in CASES) + f" a year, against {p(cagr)} in FY2021-FY2025.",
            ["valuation-range:growth-4"], [f"{PE}:voltaic-07-operating-model", f"{FB}:financebench_id_00956"],
            evidence=[MB, S8K], cells=["Input sheet!B26", "Input sheet!B28"], methods=["dcf"]),
       leaf("growth-5", "forecast", f"Will FY2026 net sales on the guidance basis (pro forma, FY2025 exchange rates) reach the ${mid:.1f}m midpoint?",
            "Open at the case date.", ["valuation-range:growth-5"], [f"{PE}:voltaic-07-operating-model"], status="open at case date", evidence=[S8K],
            resolution={"object": "FY2026 net sales, pro forma and constant currency", "period": "FY ending 31 Aug 2026", "threshold": f"${mid:.1f}m",
                        "rule": "Compare FY2026 net sales on the original guidance basis (without the brands then held for sale, at FY2025 exchange rates) with the midpoint.",
                        "linkedAssumption": f"Input sheet!B26 (Base {p(drv['base']['growth1'], 2)})"},
            later=later_rev),
       leaf("growth-6", "forecast", "Will FY2026 reported net sales exceed FY2025 reported net sales by at least 5%?",
            "Open at the case date. The case recorded no probability for it.", ["main:revenue-resolution"], [f"{PE}:voltaic-07-operating-model"],
            status="open at case date", evidence=[SX],
            resolution={"object": "FY2026 reported net sales", "period": "FY ending 31 Aug 2026", "threshold": f"{m(rev[2025] * 1.05)} (5% above {m(rev[2025])})",
                        "rule": "Compare reported net sales in the FY2026 10-K with FY2025 reported net sales.", "linkedAssumption": "Input sheet!B26 (the original case's 5% year-1 growth)"},
            later={"text": f"The FY2026 10-K reports net sales of {m(FY26['revenue'])}, {p(FY26['revenue'] / rev[2025] - 1)} above FY2025. Both years are reported figures that include the homecare brands and currency translation. With no probability recorded at the case date, this is an outcome, not a forecasting record.",
                   "sourceIds": ["wdfc26-10k"]} if FY26 else None)],
      "FinanceBench asks whether a company's financials are those of a high-growth company and what drove revenue change; PE Bench asks for historicals and an operating model. The WD-40 version asks the same about the years the scenarios extrapolate from, then tests the scenario inputs against them.")

# ---------------------------------------------------------------- margins
gm = {y: gp[y] / rev[y] for y in Y5}
om = {y: oi[y] / rev[y] for y in Y5}
rd_life = PROP["R& D converter!F6"]["value"]
rd = [PROP[c]["value"] for c in ("R& D converter!F7", "R& D converter!B11", "R& D converter!B12", "R& D converter!B13")]
need(rd_life == 3, f"R&D life is {rd_life}; the answer below assumes three years")
amort = sum(rd[1:4]) / rd_life
rd_adj = rd[0] - amort
need(abs(rd_adj - A2["rndAdjustment"]) < 1e-9, "R&D adjustment differs from the one the scenarios use")
need(abs(oi[2025] + rd_adj - drv["original"]["ebit0"]) < 1e-6, "reported EBIT plus the R&D adjustment does not equal the workbook's adjusted EBIT")
topic("margin", "Margins", f"Does WD-40's margin history support the Base path from {p(drv['base']['margin1'])} to {p(drv['base']['marginTarget'], 0)}?",
      [origin(FB, "financebench_id_00684"), origin(FB, "financebench_id_01226"), origin(FB, "financebench_id_00685"),
       origin(PE, "voltaic-04-ebitda-bridge", "The EBITDA-bridge task asks for each adjustment between reported and adjusted earnings; here the one adjustment is the R&D capitalization."),
       origin(PE, "voltaic-07-operating-model")],
      [leaf("margin-1", "fact", "What was the gross margin in each fiscal year from 2021 to 2025?",
            ", ".join(f"FY{y} {p(gm[y])}" for y in gm) + ".", ["valuation-range:margin-1"], [f"{FB}:financebench_id_00685", f"{FB}:financebench_id_00684"], evidence=[SX]),
       leaf("margin-2", "fact", "What explained the change in gross margin from FY2024 to FY2025?",
            f"The filing names lower specialty chemical costs (+80 bp), lower aerosol can costs (+60 bp) and higher average selling prices (+50 bp), less higher warehousing, distribution and freight costs (-50 bp). Gross margin rose {(gm[2025] - gm[2024]) * 1e4:.0f} bp; the named drivers add up to 140 bp, leaving about {(gm[2025] - gm[2024]) * 1e4 - 140:.0f} bp that the filing does not attribute.",
            ["valuation-range:margin-2"], [f"{FB}:financebench_id_00684"], evidence=[S10K]),
       leaf("margin-3", "fact", "What was the reported operating margin in each fiscal year from 2021 to 2025?",
            ", ".join(f"FY{y} {p(om[y])}" for y in om) + f". FY2025 is {m(oi[2025], 3)} over {m(rev[2025], 3)}, before the workbook's R&D adjustment.",
            ["valuation-range:margin-3", "main:margin-reported"], [f"{FB}:financebench_id_01226"], evidence=[SX, "wdfc25-is"], cells=["Input sheet!B11", "Input sheet!B12"]),
       leaf("margin-rd", "calculation", "How does the workbook's R&D capitalization change FY2025 operating income?",
            f"It adds back FY2025 R&D of ${rd[0]:.1f}m and subtracts a third of each of the three prior years' R&D (${rd[1]:.1f}m, ${rd[2]:.1f}m and ${rd[3]:.1f}m), ${amort:.2f}m in total. Operating income rises by ${rd_adj:.2f}m to {m(drv['original']['ebit0'], 2)}, a {p(drv['original']['ebit0'] / rev[2025], 2)} margin against {p(om[2025], 2)} reported. The three-year life is an analyst assumption; the company expenses R&D.",
            ["main:margin-rd-bridge", "main:capital-rd"], [f"{PE}:voltaic-04-ebitda-bridge"], evidence=["wdfc25-rd", "wdfc23-rd"],
            cells=["R& D converter!F6", "R& D converter!F7", "R& D converter!B11", "R& D converter!B12", "R& D converter!B13", "Valuation output!B5"]),
       leaf("margin-4", "fact", "How far was FY2025 cost of doing business from the company's own target?",
            "37% of net sales against a long-term target of 30%; gross margin was at its 55% target and adjusted EBITDA was 18% against 25%.",
            ["valuation-range:margin-4"], [f"{PE}:voltaic-07-operating-model"], evidence=[S10K]),
       leaf("margin-5", "assumption", "Which margin paths do the scenarios use, and on what basis?",
            "Year-1 margins come from operating-income guidance plus the workbook's R&D adjustment: " + ", ".join(f"{lab} {p(drv[k]['margin1'])}" for k, lab in CASES)
            + ". By year 5: " + ", ".join(f"{lab} {'stays at its year-1 margin' if abs(drv[k]['marginTarget'] - drv[k]['margin1']) < 1e-12 else p(drv[k]['marginTarget'], 0)}" for k, lab in CASES)
            + f". FY2017-FY2020 averaged {p(A2['marginFY2017_2020'])} reported. The company's long-term model targets adjusted EBITDA of 25%, not an operating margin, so no filing gives the {p(drv['base']['marginTarget'], 0)} or {p(drv['bull']['marginTarget'], 0)} directly: both are analyst assumptions.",
            ["valuation-range:margin-5", "main:margin-target"], [f"{PE}:voltaic-07-operating-model", f"{FB}:financebench_id_01226"],
            evidence=[MB, S8K, S10K], cells=["Input sheet!B27", "Input sheet!B29", "Input sheet!B30"], methods=["dcf"])],
      "FinanceBench asks whether margins are improving and what drove the change; PE Bench asks for the bridge from reported to adjusted earnings. Here the facts are the filed margins, the drivers named in the FY2025 10-K and the workbook's one adjustment, and the last question checks the scenario paths against them.")

# ---------------------------------------------------------------- capital
capint = {y: capex[y] / rev[y] for y in Y5}
bic = {y: b("StockholdersEquity", y) + b("LongTermDebtNoncurrent", y) + b("ShortTermBorrowings", y) - b("CashAndCashEquivalentsAtCarryingValue", y) for y in (2021, 2025)}
book_s2c = (rev[2025] - rev[2021]) / (bic[2025] - bic[2021])
topic("capital", "Capital intensity and reinvestment", "Does WD-40 need as much capital to grow as the sales-to-capital ratio of 2.0 implies?",
      [origin(FB, "financebench_id_00499"), origin(FB, "financebench_id_00540"), origin(FB, "financebench_id_03029"),
       origin(PE, "voltaic-05-nwc-peg", "Working-capital peg task, used for the working-capital questions.")],
      [leaf("capital-1", "fact", "What were capital expenditures as a share of net sales in each year from FY2021 to FY2025?",
            ", ".join(f"FY{y} {p(capint[y])}" for y in capint) + f". FY2025 capex (purchases of property, plant and equipment in the cash-flow statement) was {m(capex[2025])} against depreciation and amortization of {m(da[2025])}.",
            ["valuation-range:capital-1", "main:capital-capex"], [f"{FB}:financebench_id_03029", f"{FB}:financebench_id_00499"], evidence=[SX, "wdfc25-cf"]),
       leaf("capital-2", "calculation", "How many times did inventory turn in FY2025 (cost of products sold over average inventory)?",
            f"{cogs[2025] / ((inv[2024] + inv[2025]) / 2):.2f} times: {m(cogs[2025])} over average inventory of {m((inv[2024] + inv[2025]) / 2)}.",
            ["valuation-range:capital-2"], [f"{FB}:financebench_id_00540"], evidence=[SX]),
       leaf("capital-3", "calculation", "What were receivables plus inventory minus payables at the end of FY2025, as a share of FY2025 net sales?",
            f"{m(ar[2025] + inv[2025] - ap[2025])}, or {p((ar[2025] + inv[2025] - ap[2025]) / rev[2025])} of net sales.",
            ["valuation-range:capital-3"], [f"{PE}:voltaic-05-nwc-peg"], evidence=[SX]),
       leaf("capital-4", "calculation", "How much revenue did each dollar of added invested capital bring between FY2021 and FY2025?",
            f"Net sales rose {m(rev[2025] - rev[2021])}. Book equity plus borrowings minus cash rose from {m(bic[2021])} to {m(bic[2025])}, so each added dollar brought about ${book_s2c:.2f} of revenue. This book measure excludes the capitalized R&D the workbook adds.",
            ["valuation-range:capital-4"], [f"{FB}:financebench_id_00499"], evidence=[SX], cells=["Valuation output!B39"]),
       leaf("capital-5", "assumption", "Which sales-to-capital ratio does the model use, and is it observed or assumed?",
            f"2.0 in years 1-10 in every case, an assumption. The FY2021-FY2025 book measure above is {book_s2c:.2f}, so the scenarios keep 2.0. The one ratio covers capital spending and working capital together: the model has no separate receivables, inventory and payables schedule.",
            ["valuation-range:capital-5", "main:capital-turnover", "main:cash-working-capital"], [f"{FB}:financebench_id_00499", f"{PE}:voltaic-05-nwc-peg"],
            evidence=[MB, SX], cells=["Input sheet!B31", "Input sheet!B32"], methods=["dcf"])],
      "FinanceBench asks whether a company is capital-intensive, what it spends on capex and how fast it turns inventory; PE Bench asks for a working-capital peg. Here those facts test the single reinvestment input of the DCF.")

# ---------------------------------------------------------------- cash
base_rows = GC["base"]["rows"]
topic("cash", "Cash conversion", "How much of WD-40's profit turns into cash?",
      [origin(FB, "financebench_id_01279"), origin(FB, "financebench_id_00591"), origin(FB, "financebench_id_04854"),
       origin(LF, "validation-34", "FinLFQA compares free cash flow between companies with cited evidence and asks what it implies for shareholder returns; the same form is used here.")],
      [leaf("cash-1", "fact", "What were operating cash flow and capital expenditures in each year from FY2021 to FY2025?",
            "; ".join(f"FY{y} {m(ocf[y])} and {m(capex[y])}" for y in ocf) + f". FY2022 operating cash flow was low because inventory rose by {m(inv_rise22)}.",
            ["valuation-range:cash-1"], [f"{FB}:financebench_id_04854"], evidence=[SX]),
       leaf("cash-2", "calculation", "What was free cash flow (operating cash flow minus capex) as a share of net income in FY2023, FY2024 and FY2025?",
            ", ".join(f"FY{y} {p(fcf[y] / ni[y], 0)}" for y in (2023, 2024, 2025)) + f". FY2025 net income includes an ${TAX_BENEFIT:.1f}m one-time tax benefit; without it FY2025 is {p(fcf[2025] / (ni[2025] - TAX_BENEFIT), 0)}.",
            ["valuation-range:cash-2", "main:cash-conversion"], [f"{FB}:financebench_id_00591", f"{LF}:validation-34"], evidence=[SX, "wdfc25-tax"]),
       leaf("cash-3", "fact", "Among operating, investing and financing activities, which brought in the most cash in FY2025?",
            f"Operating activities: {m(cf25['operating'])}. Investing used {m(-cf25['investing'])} and financing used {m(-cf25['financing'])}.",
            ["valuation-range:cash-3"], [f"{FB}:financebench_id_01279"], evidence=[SX]),
       leaf("cash-4", "calculation", "What free cash flow does Base produce in year 1, and how does it compare with FY2025 operating cash flow minus capex?",
            f"{m(base_rows['fcff'][1])}: after-tax operating income of {m(base_rows['nopat'][1])} less reinvestment of {m(base_rows['reinvestment'][1])}. FY2025 operating cash flow minus capex was {m(fcf[2025])}. The model figure is a forecast before interest; the FY2025 figure is reported and after interest.",
            ["main:cash-fcff"], [f"{FB}:financebench_id_04854", f"{LF}:validation-34"], evidence=[MB, SX],
            cells=["Valuation output!C7", "Valuation output!C8", "Valuation output!C9"], methods=["dcf"])],
      "FinanceBench asks which cash-flow category brought in the most cash and whether free-cash-flow conversion improved; FinLFQA compares free cash flow with evidence. Both are answered here from the filed cash-flow statements, and the last question sets the model's first-year cash flow beside them.")

# ---------------------------------------------------------------- tax
etr = {y: tax[y] / pretax[y] for y in tax}
b23 = PROP["Input sheet!B23"]["value"]
norm = (tax[2025] + TAX_BENEFIT) / pretax[2025]
need(abs(norm - b23) < 1e-6, f"normalized tax rate {norm} differs from the case's {b23}")
nol = re.search(r"\$([\d.]+)m state NOLs and an associated \$([\d.]+)m deferred tax asset", " ".join(PROP["Input sheet!B61"]["caveats"]))
need(nol, "state NOL amounts not found in the case")
topic("tax", "Taxes", "Which tax rate should the forecast start from, and which tax effects recur?",
      [origin(FB, "financebench_id_01351"),
       origin(LF, "validation-82", "FinLFQA asks how an adjusted, non-GAAP effective tax rate differs from the reported one; here the adjustment is one reserve release."),
       origin(LF, "validation-97", "FinLFQA asks how tax-related adjustments affect effective rates; here the adjustment left out is the state NOLs.")],
      [leaf("tax-1", "calculation", "How much did the effective tax rate change between FY2024 and FY2025?",
            f"From {p(etr[2024])} to {p(etr[2025])}: {(etr[2025] - etr[2024]) * 100:.1f} points.", ["valuation-range:tax-1"], [f"{FB}:financebench_id_01351"], evidence=[SX]),
       leaf("tax-2", "fact", "What one-time item explains the FY2025 rate, and how does the workbook remove it?",
            f"An ${TAX_BENEFIT:.3f}m release of a reserve for an uncertain tax position. The workbook's starting rate adds it back: ({m(tax[2025], 3)} + ${TAX_BENEFIT:.3f}m) / {m(pretax[2025], 3)} = {p(norm, 2)}.",
            ["valuation-range:tax-2", "main:tax-normalization"], [f"{LF}:validation-82", f"{FB}:financebench_id_01351"], evidence=[S10K, "wdfc25-tax"], cells=["Input sheet!B23"]),
       leaf("tax-3", "assumption", "Which starting and long-run tax rates do the scenarios use?",
            ", ".join(f"{lab} {p(drv[k]['tax0'])}" for k, lab in CASES) + f" to start, from the FY2026 guidance range of {p(GUIDE['taxRateLow'])}-{p(GUIDE['taxRateHigh'])}; the original case uses the normalized {p(drv['original']['tax0'])}. All move to {p(drv['base']['taxT'], 0)} by year 10, an analyst assumption for the long-run marginal rate, not a company figure.",
            ["valuation-range:tax-3", "main:tax-terminal"], [f"{LF}:validation-82"], evidence=[MB, S8K], cells=["Input sheet!B23", "Input sheet!B24"], methods=["dcf"]),
       leaf("tax-4", "assumption", "Why does the model leave WD-40's state net operating losses out?",
            f"The 10-K reports ${nol.group(1)}m of state NOLs with a ${nol.group(2)}m deferred tax asset. The workbook's NOL input would shelter all consolidated operating income at one rate, which overstates a state-only loss, so it stays off. The Python port refuses any case with that input on.",
            ["main:tax-nol"], [f"{LF}:validation-97"], evidence=["wdfc25-nol"], cells=["Input sheet!B61", "Input sheet!B62"])],
      "FinanceBench asks how much the effective tax rate changed between two years; FinLFQA asks how tax adjustments change effective rates. The WD-40 version adds the cause of the change, the rate the model starts from, and the tax item it leaves out.")

# ---------------------------------------------------------------- cost of capital
wc = A2["waccCases"]
erp_list = ", ".join(f"{A2['erp'][k] * 100:.2f}% ({n})" for k, n in (("t12m", "trailing 12-month cash yield"), ("smoothed", "smoothed"), ("sustainablePayout", "sustainable payout")))
erp_name = {"t12m": "trailing 12-month cash yield", "smoothed": "smoothed", "sustainablePayout": "sustainable payout"}
grid = next(g for g in EV["grids"] if g["id"] == "wacc-roic")
row = next(r for r in grid["rows"] if r["label"] == f"{drv['base']['roicT'] * 100:.0f}%")
w0 = drv["base"]["wacc0"]
need(abs(drv["base"]["waccT"] - w0) < 1e-12, "Base WACC is no longer flat; the sensitivity answer assumes it is")
j = max(i for i, c in enumerate(grid["columns"]) if c <= w0)
need(j + 1 < len(grid["columns"]), "Base WACC is outside the grid")
(wa, va), (wb, vb) = (grid["columns"][j], row["values"][j]), (grid["columns"][j + 1], row["values"][j + 1])
topic("cost-of-capital", "Cost of capital", "What discount rate do market data support for WD-40 at 29 Aug 2025?",
      [origin(PE, "voltaic-02-comparables", "Rubric requires a declared pricing date; every market input here is dated."),
       origin(PE, "voltaic-07-operating-model"), origin(PE, "voltaic-11-returns-waterfall", "The returns task is adapted into a required-return sensitivity; its transaction terms are not carried over.")],
      [leaf("coc-1", "fact", "What was the 10-year Treasury yield on 29 Aug 2025, and Damodaran's implied equity risk premiums at the start of September 2025?",
            f"{p(A2['riskFree'], 2)}. Premiums: {erp_list}. Each scenario pairs one premium with the same {p(A2['riskFree'], 2)} rate: "
            + ", ".join(f"{lab} {erp_name[wc[k]['erpVariant']]}" for k, lab in CASES) + ".",
            ["valuation-range:coc-1"], [f"{PE}:voltaic-02-comparables"], evidence=["ust-par-2025-08-29", "damodaran-erp-2025-09"]),
       leaf("coc-2", "calculation", "What betas do regressions of WD-40 on the S&P 500 give, and how much of the variation do they explain?",
            "; ".join(f"{r['years']}-year {r['frequency']}: {r['beta']:.2f} (R² {r['r2']:.3f})" for r in A2["regressionBetas"]) + f". None explains more than {math.ceil(max(r['r2'] for r in A2['regressionBetas']) * 100)}% of WD-40's returns.",
            ["valuation-range:coc-2"], [f"{PE}:voltaic-02-comparables"], evidence=["yahoo-prices"]),
       leaf("coc-3", "fact", "What were Damodaran's January 2025 unlevered betas for Chemical (Specialty) and Household Products?",
            f"{A2['industryUnleveredBetas']['Chemical (Specialty)']:.2f} and {A2['industryUnleveredBetas']['Household Products']:.2f}, corrected for cash.",
            ["valuation-range:coc-3"], [f"{PE}:voltaic-02-comparables"], evidence=["damodaran-betas-2025-01"]),
       leaf("coc-4", "assumption", "Which WACC do the scenarios use, and what did the original case use?",
            f"Bear {p(wc['bear']['wacc'], 2)} moving to {p(A2['marketTerminalBear'], 2)}, Base {p(wc['base']['wacc'], 2)} and Bull {p(wc['bull']['wacc'], 2)} in every year. The original case used {p(drv['original']['wacc0'], 0)} moving to {p(drv['original']['waccT'], 0)}: the starting rate is an illustrative placeholder with no CAPM behind it, and the terminal rate is typed into the workbook's override instead of coming from its risk-free rate plus mature-market premium.",
            ["valuation-range:coc-4", "main:discount-start", "main:discount-terminal"], [f"{PE}:voltaic-07-operating-model"],
            evidence=[MB, "ust-par-2025-08-29", "damodaran-erp-2025-09"], cells=["Cost of capital worksheet!B12", "Input sheet!B45", "Input sheet!B46"], methods=["dcf"]),
       leaf("coc-5", "calculation", "How much does Base value per share move when the WACC changes?",
            f"With a flat WACC and every other Base input fixed, value per share is ${va:.2f} at {p(wa)} and ${vb:.2f} at {p(wb)}: about ${va - vb:.0f} per half point around Base's {p(w0, 2)}. A flat rate and a shifted path that fades are different changes; the live reverse DCF on the page shifts the whole path.",
            ["main:discount-sensitivity"], [f"{PE}:voltaic-11-returns-waterfall"], evidence=[MB],
            cells=["Cost of capital worksheet!B12", "Input sheet!B46", "Valuation output!B33"], methods=["dcf"])],
      "PE Bench requires a declared pricing date and asks what return a price implies. Each input here carries its date and source, and the last question shows how much the value depends on the rate. FinLFQA's validation questions include none on the cost of capital.")

# ---------------------------------------------------------------- returns
roic_all = [r for c in GC.values() for r in c["rows"]["roic"][1:11]]
products = {x["id"]: x["revenue"] for x in RES["operatingFacts"]["products"]}
regions = {x["label"]: x["revenue"] for x in RES["operatingFacts"]["regions"]}
need(abs(sum(products.values()) - rev[2025]) < 0.01 and abs(sum(regions.values()) - rev[2025]) < 0.01, "product or region revenue does not add up to net sales")
eva = CORE["eva"]
ALL4 = [("original", "Original")] + CASES
topic("returns", "Return on capital", "How long can WD-40 keep earning more than its cost of capital?",
      [origin(LF, "validation-170", "FinLFQA asks which company's return on equity shows more shareholder value; here the return is on invested capital, set against the cost of capital."),
       origin(FB, "financebench_id_00517"), origin(PE, "voltaic-07-operating-model")],
      [leaf("returns-1", "calculation", "What was FY2025 return on invested capital in the workbook (after-tax operating income over invested capital)?",
            f"{p(GC['original']['rows']['roic'][0])}, on invested capital of {m(GC['original']['rows']['investedCapital'][0])} including capitalized R&D.",
            ["valuation-range:returns-1"], [f"{LF}:validation-170"], evidence=["wdfc25-is", "wdfc25-bs", "wdfc25-rd"], cells=["Valuation output!B40", "Valuation output!B39"]),
       leaf("returns-2", "fact", "What share of FY2025 net sales came from WD-40 Multi-Use Product?",
            f"{m(products['multiUse'])} of {m(rev[2025])}, or {p(products['multiUse'] / rev[2025])}. WD-40 Specialist added {m(products['specialist'])}.",
            ["valuation-range:returns-2", "main:risks-product-concentration"], [f"{FB}:financebench_id_00517"], evidence=[S8K]),
       leaf("returns-3", "fact", "How were FY2025 net sales split by region, and did any customer reach 10%?",
            ", ".join(f"{k} {p(x / rev[2025], 0)}" for k, x in regions.items()) + ". About 66% came from outside the US. No customer reached 10% of consolidated net sales.",
            ["valuation-range:returns-3", "main:risks-product-concentration"], [f"{FB}:financebench_id_00517"], evidence=[S10K, "wd40-fy25-operating-research"]),
       leaf("returns-4", "calculation", "Does restating the DCF as invested capital plus economic profit give the same operating value?",
            "Yes. " + "; ".join(f"{lab} {m(eva[k]['evaValue'])} against {m(eva[k]['dcfValue'])}" for k, lab in ALL4) + ". The two are the same calculation arranged differently, so this checks consistency, not value. The reconciliation is in the DCF details.",
            ["valuation-range:returns-4"], [f"{PE}:voltaic-07-operating-model"], evidence=[MB], methods=["dcf"]),
       leaf("returns-5", "assumption", "What return on new capital after year 10 do the scenarios assume, and what supports it?",
            ", ".join(f"{lab}: {'equal to the cost of capital (no excess return)' if drv[k]['roicOverride'] != 1 else p(drv[k]['roicT'], 0)}" for k, lab in CASES)
            + f". In years 1-10 the model earns {p(min(roic_all), 0)} to {p(max(roic_all), 0)} on capital across the four cases. No filing establishes a permanent excess return; the Base and Bull figures rest on the brand and the low capital needs above, and are analyst assumptions.",
            ["valuation-range:returns-5", "main:terminal-excess-returns"], [f"{LF}:validation-170", f"{PE}:voltaic-07-operating-model"],
            evidence=[MB], cells=["Input sheet!B48", "Input sheet!B49", "Valuation output!M40"], methods=["dcf"]),
       leaf("returns-6", "calculation", "What reinvestment does each case's terminal growth and return on new capital imply?",
            "Reinvestment is growth over the return on new capital: " + "; ".join(f"{lab} {p(drv[k]['growthT'])} / {p(terminal_roic[k], 2)} = {p(drv[k]['growthT'] / terminal_roic[k])}" for k, lab in ALL4)
            + " of after-tax operating income. A higher assumed return lets the same growth come with less reinvestment, so the two have to be read together.",
            ["main:terminal-reinvestment"], [f"{PE}:voltaic-07-operating-model"], evidence=[MB],
            cells=["Input sheet!B48", "Input sheet!B49", "Valuation output!M2", "Valuation output!M8", "Valuation output!M40"], methods=["dcf"]),
       leaf("returns-7", "calculation", "What share of operating value comes from after year 10 in each case?",
            "; ".join(f"{lab} {p(EV['results'][k]['result']['terminalShare'], 0)}" for k, lab in ALL4) + ". The cases with higher growth and returns lean more on the years after the forecast.",
            ["main:terminal-value-share"], [f"{PE}:voltaic-07-operating-model"], evidence=[MB],
            cells=["Valuation output!B19", "Valuation output!B21", "Valuation output!B24"], methods=["dcf"])],
      "FinLFQA compares returns on equity; FinanceBench asks whether any product exceeds 20% of revenue. Together they ask how durable WD-40's excess return is, and how much of the value rests on it lasting.")

# ---------------------------------------------------------------- payouts
ddm = CORE["ddm"]
sh = re.search(r"([\d.]+) common shares \+([\d.]+) RSUs \+([\d.]+) target MSUs \+([\d.]+) vested DPUs", PROP["Input sheet!B21"]["rationale"])
need(sh, "share-count components not found in the case")
parts = [float(x) for x in sh.groups()]
need(abs(sum(parts) - PROP["Input sheet!B21"]["value"]) < 1e-9, "share-count components do not add up to Input sheet!B21")
topic("payouts", "Shareholder payouts", "Is the dividend sustainable at the scenarios' growth rates, and how does value reach each share?",
      [origin(FB, "financebench_id_01244"), origin(FB, "financebench_id_01858"), origin(FB, "financebench_id_06272"),
       origin(LF, "validation-221", "FinLFQA compares dividends with share repurchases in size; the same comparison is made for WD-40."),
       origin(LF, "validation-41", "FinLFQA compares dividends paid; here the dividend becomes the base of a dividend discount model."),
       origin(PE, "voltaic-09-sources-uses", "The sources-and-uses task needs a fully diluted share count; the WD-40 question asks how the model's count is built.")],
      [leaf("payouts-1", "fact", "What dividend per share did WD-40 pay in each year from FY2021 to FY2025?",
            ", ".join(f"FY{y} ${dps[y]:.2f}" for y in dps) + (". It rose every year." if all(dps[y + 1] > dps[y] for y in range(2021, 2025)) else "."),
            ["valuation-range:payouts-1"], [f"{FB}:financebench_id_01244", f"{FB}:financebench_id_01858"], evidence=[SX]),
       leaf("payouts-2", "calculation", "How well did FY2025 earnings and free cash flow cover the dividend?",
            f"${dps[2025]:.2f} a share paid against ${NON_GAAP_EPS:.2f} non-GAAP diluted EPS ({p(dps[2025] / NON_GAAP_EPS, 0)}) or ${eps25:.2f} GAAP EPS, which includes the one-time tax benefit ({p(dps[2025] / eps25, 0)}). In cash, dividends of {m(dividends25)} were {p(dividends25 / fcf[2025], 0)} of operating cash flow minus capex.",
            ["valuation-range:payouts-2", "main:payouts-dividends"], [f"{FB}:financebench_id_06272"], evidence=[SX, S8K]),
       leaf("payouts-3", "fact", "How did FY2025 share repurchases compare with dividends?",
            f"{m(buyback25)} of repurchases against {m(dividends25)} of dividends.", ["valuation-range:payouts-3"], [f"{LF}:validation-221"], evidence=[SX]),
       leaf("payouts-4", "calculation", "What does a dividend discount model give with the scenarios' cost of equity?",
            "; ".join(f"{k.title()} ${d['value']:.2f} (cost of equity {p(d['costOfEquity'], 2)}, terminal payout {p(d['terminalPayout'], 0)})" for k, d in ddm.items())
            + ". The discount rate is each scenario's CAPM cost of equity, not its WACC; earnings growth and payout are analyst assumptions.",
            ["valuation-range:payouts-4", "main:payouts-ddm"], [f"{LF}:validation-41"], evidence=[MB], methods=["ddm"]),
       leaf("payouts-5", "fact", "Which share count divides equity value, and how is it built?",
            f"{PROP['Input sheet!B21']['value']:.6f}m: {parts[0]:.6f}m common shares plus {parts[1]:.6f}m restricted stock units, {parts[2]:.6f}m market-based units at target and {parts[3]:.6f}m vested deferred units. Performance units granted in FY2025 are left out because they were later forfeited. Every case uses this count.",
            ["main:payouts-dilution"], [f"{PE}:voltaic-09-sources-uses"], evidence=["wdfc25-bs", "wdfc25-rsu", "wdfc25-msu", "wdfc25-plan-footnote", "wdfc25-psu"],
            cells=["Input sheet!B21", "Valuation output!B32", "Valuation output!B33"])],
      "FinanceBench asks whether a company pays dividends, keeps a stable trend and what its payout ratio is; FinLFQA compares dividends with buybacks; PE Bench needs a diluted share count. The WD-40 version adds coverage, a dividend-based value and the share count every value is divided by.")

# ---------------------------------------------------------------- financing
lbo = CORE["lbo"]
T = lbo["base"]["terms"]
eq = re.search(r"Reported equity ([\d.]+) \+ operating-lease liabilities ([\d.]+) - operating ROU assets ([\d.]+)", PROP["Input sheet!B14"]["rationale"])
need(eq, "lease recast not found in the case")
eq_rep, lease_liab, rou = (float(x) for x in eq.groups())
need(abs(eq_rep + lease_liab - rou - PROP["Input sheet!B14"]["value"]) < 1e-9, "lease recast does not add up to Input sheet!B14")
need(abs(cash25 - PROP["Input sheet!B18"]["value"]) < 1e-9 and abs(debt[2025] - PROP["Input sheet!B15"]["value"]) < 1e-9, "XBRL debt or cash differs from the case")
topic("financing", "Financing a buyout", "What could a financial buyer pay for WD-40?",
      [origin(PE, "voltaic-08-debt-schedule"), origin(PE, "voltaic-09-sources-uses"), origin(PE, "voltaic-11-returns-waterfall"),
       origin(PE, "voltaic-05-nwc-peg", "The peg task asks which liabilities count as debt-like; the WD-40 question asks the same of operating leases."),
       origin(FB, "financebench_id_00552")],
      [leaf("financing-1", "fact", "How did borrowings change between the end of FY2024 and FY2025, and what reaches the equity bridge?",
            f"From {m(debt[2024], 3)} to {m(debt[2025], 3)}. With cash of {m(cash25, 3)}, borrowings net of cash were {m(debt[2025] - cash25, 3)} at FY2025 year-end; the DCF subtracts the debt and adds the cash.",
            ["valuation-range:financing-1", "main:financing-net-debt"], [f"{FB}:financebench_id_00552", f"{PE}:voltaic-09-sources-uses"],
            evidence=[SX, "wdfc25-bs"], cells=["Input sheet!B15", "Input sheet!C15", "Input sheet!B18", "Valuation output!B25", "Valuation output!B27"]),
       leaf("financing-2", "calculation", "What was FY2025 operating income over interest expense?",
            f"{oi[2025] / interest25:.0f} times: {m(oi[2025])} over {m(interest25, 2)}.", ["valuation-range:financing-2"], [f"{PE}:voltaic-08-debt-schedule"], evidence=[SX]),
       leaf("financing-3", "calculation", "With the Base financing terms, what is the highest price per share a buyer can pay and still earn its target return?",
            f"${lbo['base']['price']:.2f} ({lbo['base']['status']}), an entry multiple of {lbo['base']['entryEvToEbitda']:.1f} times EBITDA. Terms: {lbo['base']['leverage']:.1f} times FY2025 EBITDA of debt at SOFR on 29 Aug 2025 plus {p(T['creditSpread'], 1)} ({p(lbo['base']['interestRate'], 2)}), a {p(lbo['base']['hurdle'], 0)} target return, and an exit after five years at {lbo['base']['exitMultiple']:.1f} times EBITDA, the peer median. Debt is repaid {p(T['mandatoryAmortization'], 0)} a year, then from cash above a ${T['minimumCash']:.0f}m minimum; fees are {p(T['transactionFee'], 0)} on the transaction, {p(T['financingFee'], 1)} on the financing and {p(T['exitFee'], 0)} on exit. "
            + f"Bear ({lbo['bear']['leverage']:.1f}x debt, {p(lbo['bear']['hurdle'], 0)} target, exit at the 25th percentile) gives ${lbo['bear']['price']:.2f}; Bull ({lbo['bull']['leverage']:.1f}x, {p(lbo['bull']['hurdle'], 1)}, 75th percentile) ${lbo['bull']['price']:.2f}.",
            ["valuation-range:financing-3", "main:financing-affordability"], [f"{PE}:voltaic-11-returns-waterfall", f"{PE}:voltaic-08-debt-schedule", f"{PE}:voltaic-09-sources-uses"],
            evidence=[MB, "nyfed-sofr-2025-08-29"], methods=["lbo"]),
       leaf("financing-4", "assumption", "Which operating case does the buyout model use?",
            "The Base DCF case: its revenue, EBIT, tax rate and free cash flow before financing in years 1-5. EBITDA is put on a reported basis by removing the R&D adjustment and adding depreciation and amortization at the FY2025 share of sales.",
            ["valuation-range:financing-4"], [f"{PE}:voltaic-08-debt-schedule"], evidence=[MB], methods=["lbo", "dcf"]),
       leaf("financing-5", "assumption", "Why are operating leases left out of debt?",
            f"The case keeps operating rent in operating income, so it leaves the {m(lease_liab, 3)} operating-lease liability out of debt and takes it and the {m(rou, 3)} right-of-use asset out of book equity: {m(eq_rep, 3)} reported becomes {m(PROP['Input sheet!B14']['value'], 3)}. Counting the liability as debt would also require moving rent out of operating income.",
            ["main:financing-leases"], [f"{PE}:voltaic-05-nwc-peg"], evidence=["wdfc25-leases", "wdfc25-lease-expense"], cells=["Input sheet!B14", "Input sheet!B15", "Input sheet!B17"])],
      "PE Bench asks for a debt schedule, sources and uses, debt-like items and returns; FinanceBench asks whether debt rose. Together they test what a sponsor could pay for WD-40.")

# ---------------------------------------------------------------- market
q_ev = COMPS["quartiles"]["evToEbitda"]
own = COMPS["ownHistory"]
of = RES["operatingFacts"]
topic("market", "Market pricing", "What does the $216.04 price assume that the cases do not?",
      [origin(PE, "voltaic-02-comparables"), origin(FB, "financebench_id_00438")],
      [leaf("market-1", "calculation", "What EV to EBITDA did five listed peers trade at on 29 Aug 2025, after adding back tagged one-off charges?",
            f"25th percentile {q_ev[0]:.1f}x, median {q_ev[1]:.1f}x, 75th percentile {q_ev[2]:.1f}x.", ["valuation-range:market-1"], [f"{PE}:voltaic-02-comparables"],
            evidence=["sec-chd", "sec-clx", "sec-enr", "sec-rpm", "sec-kwr", "yahoo-peers"], methods=["comps"]),
       leaf("market-2", "calculation", "What EV to EBITDA did WD-40 trade at on 29 Aug 2025, and at its previous four fiscal year-ends?",
            ", ".join(f"FY{o['fiscalYear']} {o['evToEbitda']:.1f}x" for o in own) + ".", ["valuation-range:market-2"], [f"{FB}:financebench_id_00438"],
            evidence=[SX, "price-close"], methods=["own-history"]),
       leaf("market-3", "calculation", "Starting from Base, what single change reaches $216.04?",
            f"A WACC of {p(RV['wacc']['solution'], 2)} in every year, or a {p(RV['margin']['solution'])} operating margin by year 5, or {p(RV['growth']['solution'])} revenue growth in years 2-5. No terminal return on capital reaches it alone: at {p(RV['roic']['range'][1], 0)} the value is ${RV['roic']['valueAtBounds'][1]:.2f}.",
            ["valuation-range:market-3"], [f"{PE}:voltaic-02-comparables"], evidence=[MB, "price-close"], methods=["dcf"]),
       leaf("market-4", "fact", "What price targets had analysts published by 29 Aug 2025?",
            "DA Davidson $300 (Buy, 11 Jul 2025) and Jefferies $280 (Hold, 18 Oct 2024). Other firms' targets were not found.",
            ["valuation-range:market-4"], [f"{PE}:voltaic-02-comparables"], evidence=["target-dadavidson", "target-jefferies"]),
       leaf("market-5", "fact", f"Can the company-defined adjusted EBITDA of {m(of['issuerAdjustedEbitda'])} be reconciled to EBIT plus depreciation and amortization of {m(of['operatingEbitdaFromEbitPlusCashFlowDa'])}?",
            f"Not from the material collected. The {m(of['issuerAdjustedEbitda'] - of['operatingEbitdaFromEbitPlusCashFlowDa'])} difference sits in the company's non-GAAP reconciliation, which was not extracted.",
            ["valuation-range:market-5"], [f"{PE}:voltaic-02-comparables"], status="insufficient data", evidence=[S8K, "wd40-fy25-operating-research"])],
      "PE Bench requires peers and the target on one EBITDA definition; FinanceBench asks whether operating margin is improving. Here the facts measure how far the price sits from each method.")

# ---------------------------------------------------------------- risks
later_gm = None
if FY26:
    gm26 = FY26["grossProfit"] / FY26["revenue"]
    later_gm = {"text": f"The FY2026 10-K reports a gross margin of {p(gm26)} ({m(FY26['grossProfit'])} over {m(FY26['revenue'])}), below the range but on a changed perimeter. In July 2026 the company moved the homecare brands back into the business and lowered its gross margin guidance to {p(JULY['grossMarginLow'])}-{p(JULY['grossMarginHigh'])}, putting {JULY['grossMarginRevisionBp']['reclassifiedBrands']} bp of the cut on that move and {JULY['grossMarginRevisionBp']['costIncreases']} bp on higher costs. The reported figure therefore does not resolve the question on the original basis.",
                "sourceIds": ["wdfc26-10k", JULY_SRC]}
topic("risks", "Threats to the business", "What could break the margin and growth assumptions?",
      [origin(FC, "0100.00018", "A cause-effect pair in which oil prices pass through to a product price; the WD-40 question asks how oil reaches WD-40's own costs."),
       origin(FB, "financebench_id_01319"),
       origin(PE, "voltaic-07-operating-model", "The operating-model task asks for testable drivers; here the test is a published margin range.")],
      [leaf("risks-1", "fact", "Which inputs does WD-40 name as its main costs, and how does the price of oil reach them?",
            "Specialty chemicals and aerosol cans. The 10-K says oil price volatility indirectly affects specialty chemical costs, many of which are indexed to refined oil products.",
            ["valuation-range:risks-1"], [f"{FC}:0100.00018"], evidence=[S10K]),
       leaf("risks-2", "fact", "How did currency translation affect FY2025 net sales by segment?",
            "Americas -$4.7m, EIMEA +$3.5m, Asia-Pacific -$0.2m: -$1.4m in total.", ["valuation-range:risks-2"], [f"{FC}:0100.00018"], evidence=[S10K]),
       leaf("risks-3", "fact", "Are restructuring costs shown separately in the FY2025 income statement?",
            "No restructuring line or restructuring fact appears in the FY2025 XBRL data, so the FinanceBench rule gives 0.",
            ["valuation-range:risks-3"], [f"{FB}:financebench_id_01319"], evidence=[SX]),
       leaf("risks-4", "forecast", f"Will the FY2026 gross margin stay within the guided {p(GUIDE['grossMarginLow'])}-{p(GUIDE['grossMarginHigh'])} range?",
            "Open at the case date.", ["valuation-range:risks-4", "main:risks-falsification"], [f"{PE}:voltaic-07-operating-model"], status="open at case date", evidence=[S8K],
            resolution={"object": "FY2026 gross margin", "period": "FY ending 31 Aug 2026", "threshold": f"{p(GUIDE['grossMarginLow'])} to {p(GUIDE['grossMarginHigh'])}",
                        "rule": f"Compare FY2026 gross margin on the original guidance perimeter (without the brands then held for sale) with the range. A margin below it would contradict the Base and Bull paths, which raise operating margin to {p(drv['base']['marginTarget'], 0)} and {p(drv['bull']['marginTarget'], 0)}.",
                        "linkedAssumption": f"Input sheet!B27 and B29 (Base {p(drv['base']['margin1'])} and {p(drv['base']['marginTarget'], 0)} operating margin)"},
            later=later_gm)],
      "FinCausal extracts cause and effect from financial text; FinanceBench asks for restructuring costs. The WD-40 version asks which costs move margins, through what channel, and which published figure would test the margin paths.")

# ---------------------------------------------------------------- dispositions and checks
leaves = {l_["id"]: l_ for t in topics for l_ in t["leaves"]}
need(len(leaves) == sum(len(t["leaves"]) for t in topics), "duplicate leaf ids")
EXCLUDED = {}  # "branch:id" -> reason
known = {f"{br['branch']}:{q['id']}": q for br in MERGE_INPUTS["branches"] for q in br["questions"]}
covered = collections.defaultdict(list)
for l_ in leaves.values():
    for ref in l_["covers"]:
        if ref not in known:
            fail(f"{l_['id']} covers unknown question {ref}")
        covered[ref].append(l_["id"])
dispositions = []
for ref, q in known.items():
    if ref in EXCLUDED:
        dispositions.append({"question": ref, "text": q["question"], "disposition": "excluded", "reason": EXCLUDED[ref]})
    elif ref not in covered:
        fail(f"{ref} has no disposition")
    else:
        into = covered[ref]
        primary = [lid for lid in into if leaves[lid]["covers"][0] == ref]
        dispositions.append({"question": ref, "text": q["question"], "disposition": "kept" if primary else "merged", "into": into})
FIX = {"growth-1": ("fact", "6.2%"), "capital-2": ("calculation", "times"), "market-5": ("fact", "insufficient data"),
       "growth-5": ("forecast", "open at case date"), "tax-2": ("fact", p(b23, 2))}
for lid, (purpose, needle) in FIX.items():
    l_ = leaves[lid]
    need(l_["purpose"] == purpose and (needle in l_["answer"] or needle == l_["status"]), f"fixture {lid}: {l_['purpose']} / {l_['status']} / {l_['answer'][:80]}")
for l_ in leaves.values():
    if l_["purpose"] == "forecast":
        need(l_["resolution"] and l_["status"] == "open at case date", f"{l_['id']}: a forecast needs a resolution rule and its case-date status")
    if l_["laterInformation"]:
        need(all(s in SOURCES or s in POOL for s in l_["laterInformation"]["sourceIds"]), f"{l_['id']}: later information cites an unknown source")
for t in topics:
    for l_ in t["leaves"]:
        for s in l_["evidence"] + (l_["laterInformation"] or {}).get("sourceIds", []):
            if s not in SOURCES and s in POOL:
                SOURCES[s] = POOL[s]

used = collections.defaultdict(set)
for t in topics:
    for o in t["origins"]:
        used[o["source"]].add(o["sourceId"])
counts = collections.Counter(r["source"] for r in MERGED)
coverage = {s: {"records": counts[s], "usedAsOrigin": len(used[s])} for s in counts}
coverage["FinTextQA"]["why"] = "The public part is 240 questions on banking regulation (Federal Reserve, HKMA, EU). None applies to a non-bank consumer products company; the textbook part was not released."
coverage["FinCausal"]["why"] = "Cause-effect pairs from news about other companies; two shape the form of the disposal and oil-cost questions, and no figure from them enters an answer."
coverage["FinLFQA"]["why"] = "Records were chosen by their question text: the dataset's topic labels often do not match it, and no validation question asks about the cost of capital."
datasets = {r["source"]: {"dataset": r["dataset"], "revision": r["revision"], "sha256": r["datasetSha256"], "url": r["datasetUrl"], "licenseKnown": r["licenseKnown"]} for r in MERGED}
out = {"asOf": CUT, "note": "Questions adapted to WD-40 from the benchmarks; answers computed from filings and the model. Not a result of any benchmark.",
       "topics": topics, "coverage": coverage, "datasets": datasets, "sources": SOURCES, "dispositions": dispositions,
       "mergeInputs": {br["branch"]: br["commit"] for br in MERGE_INPUTS["branches"]},
       "fixtures": {k: {"purpose": a, "expect": b_} for k, (a, b_) in FIX.items()}}
with open(ROOT / "models" / "questions" / "questions.json", "w", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")

n_leaves = len(leaves)
disp = collections.Counter((d["question"].split(":")[0], d["disposition"]) for d in dispositions)
L = ["# Stage 6: diligence questions", "",
     f"`python -I models/questions/extract.py` merged {sum(counts.values()):,} records from the pinned benchmark files: " + ", ".join(f"{k} {v_:,}" for k, v_ in counts.items()) + f". `python -I models/questions/build_questions.py` adapts them to WD-40 in {n_leaves} questions under {len(topics)} topics and computes every answer from filings filed by 27 Oct 2025, the original case's proposals, the FY2025 8-K and 10-K passages, or the model. The adapted set is not a benchmark result.", "",
     "Each topic starts from a judgement question. Following The Mom Test, the judgement is not asked directly: it is split into questions about specific past facts, then a question about which model input those facts test. Forecast questions state the object, period, threshold and resolution rule. Information from after the case date is shown apart and labelled; it is computed from the FY2026 10-K and the July 2026 guidance revision and never enters a valuation.", "",
     "| Source | Records | Used as origin | Note |", "|---|---:|---:|---|"]
for s, c in coverage.items():
    L.append(f"| {s} | {c['records']:,} | {c['usedAsOrigin']} | {c.get('why', '')} |")
L += ["", "## Merge of the two earlier question sets", "",
      f"Both earlier sets were merged by meaning, not by benchmark record: `main` ({MERGE_INPUTS['branches'][0]['commit'][:7]}) had {len(MERGE_INPUTS['branches'][0]['questions'])} questions, `valuation-range` ({MERGE_INPUTS['branches'][1]['commit'][:7]}) had {len(MERGE_INPUTS['branches'][1]['questions'])}. "
      + "; ".join(f"{br}: {n} {d}" for (br, d), n in sorted(disp.items())) + ("." if EXCLUDED else ". Nothing was excluded."), "",
      "| Earlier question | Disposition | Now |", "|---|---|---|"]
for d in dispositions:
    L.append(f"| `{d['question']}` {d['text']} | {d['disposition']} | {', '.join(f'`{x}`' for x in d.get('into', []))}{d.get('reason', '')} |")
L.append("")
for t in topics:
    L += [f"## {t['title']}", "", f"**{t['parent']}**", "", t["adaptation"], "",
          "Origins: " + "; ".join(f"{o['source']} `{o['sourceId']}`" + (f" ({o['originalText'][:110]}…)" if len(o.get("originalText", "")) > 110 else f" ({o['originalText']})" if o.get("originalText") else f" (cause: {o['cause'][:60]}; effect: {o['effect'][:60]})" if o.get("cause") else "") for o in t["origins"]), ""]
    for l_ in t["leaves"]:
        L.append(f"- *{l_['purpose']}* `{l_['id']}`: {l_['text']}  ")
        L.append(f"  {l_['answer']}" + (f" Status: {l_['status']}." if l_["status"] != "answered" else ""))
        if l_["resolution"]:
            r = l_["resolution"]
            L.append(f"  Resolution: {r['rule']} Threshold {r['threshold']}; linked to {r['linkedAssumption']}.")
        if l_["laterInformation"]:
            L.append(f"  Later information (after the case date): {l_['laterInformation']['text']}")
    L.append("")
with open(ROOT / "reports" / "06-questions.md", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))
print(len(topics), "topics", n_leaves, "questions;", dict(disp))
