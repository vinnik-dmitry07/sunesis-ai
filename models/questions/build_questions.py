"""WD-40 diligence questions adapted from the five benchmarks, each split into narrow sub-questions.

Selection: models/out/questions_merged.jsonl (extract.py). Answers are computed here from SEC XBRL facts filed by
27 Oct 2025 (the FY2025 10-K date), the FY2025 8-K and 10-K passages recorded below, and the model outputs.
Following The Mom Test, a judgement question ("Is WD-40 capital-intensive?") is broken into questions about
specific past facts, then a question about which model input the facts test. Forecast questions name the
object, period, threshold and resolution rule; later information that resolves them is labelled as such and
is not used in any valuation.
Run:  python -I models/questions/build_questions.py  ->  models/out/questions.json, reports/06-questions.md
"""
import collections
import datetime as dt
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "models" / "out"
CUT = "2025-10-27"
MERGED = [json.loads(l) for l in (OUT / "questions_merged.jsonl").read_text(encoding="utf-8").splitlines()]
G = json.loads((ROOT / "models" / "data" / "sec" / "wdfc_companyfacts.json").read_text())["facts"]["us-gaap"]
GC = json.loads((OUT / "ginzu_cases.json").read_text())["cases"]
CORE = json.loads((OUT / "valuation_book" / "core_results.json").read_text())
COMPS = json.loads((OUT / "methods_comps.json").read_text())["methods"][0]
A2 = json.loads((OUT / "stage2_assumptions.json").read_text())
RV = {r["id"]: r for r in json.loads((OUT / "scenarios_eval.json").read_text())["reverseFromBase"]}


def fy(tag, year, cut=CUT):
    vals = [f for f in G[tag]["units"]["USD" if tag in G and "USD" in G[tag]["units"] else "USD/shares"]
            if f["form"] == "10-K" and f["filed"] <= cut and "start" in f and f["end"] == f"{year}-08-31"
            and 360 < (dt.date.fromisoformat(f["end"]) - dt.date.fromisoformat(f["start"])).days < 372]
    f = max(vals, key=lambda f: f["filed"])
    return f["val"] / (1 if abs(f["val"]) < 1000 else 1e6), f["accn"]


def inst(tag, year, cut=CUT):
    vals = [f for f in G[tag]["units"]["USD"] if f["form"] == "10-K" and f["filed"] <= cut and "start" not in f and f["end"] == f"{year}-08-31"]
    f = max(vals, key=lambda f: f["filed"])
    return f["val"] / 1e6, f["accn"]


def v(tag, year):
    return fy(tag, year)[0]


def b(tag, year):
    return inst(tag, year)[0]


rev = {y: v("RevenueFromContractWithCustomerExcludingAssessedTax", y) for y in range(2021, 2026)}
gp = {y: v("GrossProfit", y) for y in range(2021, 2026)}
oi = {y: v("OperatingIncomeLoss", y) for y in range(2021, 2026)}
cogs = {y: v("CostOfGoodsAndServicesSold", y) for y in range(2021, 2026)}
capex = {y: v("PaymentsToAcquirePropertyPlantAndEquipment", y) for y in range(2021, 2026)}
da = {y: v("DepreciationDepletionAndAmortization", y) for y in range(2021, 2026)}
ocf = {y: v("NetCashProvidedByUsedInOperatingActivities", y) for y in range(2021, 2026)}
ni = {y: v("NetIncomeLoss", y) for y in range(2021, 2026)}
dps = {y: v("CommonStockDividendsPerShareCashPaid", y) for y in range(2021, 2026)}
tax = {y: v("IncomeTaxExpenseBenefit", y) for y in (2024, 2025)}
pretax = {y: v("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", y) for y in (2024, 2025)}
inv = {y: b("InventoryNet", y) for y in range(2021, 2026)}
ar = {y: b("AccountsReceivableNetCurrent", y) for y in (2024, 2025)}
ap = {y: b("AccountsPayableCurrent", y) for y in (2024, 2025)}
ppe = {y: b("PropertyPlantAndEquipmentNet", y) for y in (2024, 2025)}
debt = {y: b("LongTermDebtNoncurrent", y) + b("ShortTermBorrowings", y) for y in (2024, 2025)}
interest25 = v("InterestExpenseNonoperating", 2025)
cf25 = {k: v(t, 2025) for k, t in [("operating", "NetCashProvidedByUsedInOperatingActivities"), ("investing", "NetCashProvidedByUsedInInvestingActivities"),
                                    ("financing", "NetCashProvidedByUsedInFinancingActivities")]}
buyback25 = v("PaymentsForRepurchaseOfCommonStock", 2025)
dividends25 = v("PaymentsOfDividends", 2025)
p = lambda x, d=1: f"{x * 100:.{d}f}%"  # noqa: E731
m = lambda x, d=1: f"${x:,.{d}f}m"  # noqa: E731

S10K = "wdfc25-10k"
S8K = "wdfc-8k-2025-10-22"
SX = "sec-xbrl"
SOURCES = {
    S10K: {"title": "WD-40 Company FY2025 Form 10-K", "url": "https://www.sec.gov/Archives/edgar/data/105132/000010513225000067/wdfc-20250831.htm", "publishedAt": "2025-10-27"},
    "wdfc26-10k": {"title": "WD-40 Company FY2026 Form 10-K (later information, outside the case)", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000105132&type=10-K", "publishedAt": "2026-10-26"},
}


def first(source, **kw):
    for r in MERGED:
        if r["source"] == source and all(r.get(k) == val for k, val in kw.items()):
            return r
    raise KeyError((source, kw))


def origin(source, rec=None, note=""):
    o = {"source": source, "license": rec["license"] if rec else None, "note": note}
    if rec:
        o["sourceId"] = rec["sourceId"]
        if rec.get("question"):
            o["originalText"] = re.sub(r"\s+", " ", rec["question"]).strip()[:240]
    return o


fb = lambda dg: first("FinanceBench", type="domain-relevant", template=dg)  # noqa: E731
lf_topic = lambda t: first("FinLFQA", reasoning=t)  # noqa: E731
pe = lambda tid: first("PE Bench", sourceId=tid)  # noqa: E731
causal_kw = re.compile(r"\b(oil|crude|commodit\w*|currenc\w*|dollar|tariff\w*|raw material\w*|freight)\b", re.I)
causal = [r for r in MERGED if r["source"] == "FinCausal" and (causal_kw.search(r["cause"]) or causal_kw.search(r["effect"]))]

base = GC["base"]["drivers"]
B = lambda k: base[k]["value"]  # noqa: E731
q_ev = COMPS["quartiles"]["evToEbitda"]
own = COMPS["ownHistory"]
lbo = CORE["lbo"]
ddm = CORE["ddm"]
syn = CORE["synergies"]
eva = CORE["eva"]

topics = []


def topic(tid, title, parent, origins, leaves, adaptation):
    topics.append({"id": tid, "title": title, "parent": parent, "origins": origins, "adaptation": adaptation, "leaves": leaves})


def leaf(lid, purpose, text, answer, status="answered", evidence=(), cells=(), methods=(), resolution=None, later=None):
    return {"id": lid, "purpose": purpose, "text": text, "answer": answer, "status": status, "evidence": list(evidence),
            "cells": list(cells), "methods": list(methods), "resolution": resolution, "laterInformation": later}


cagr = (rev[2025] / rev[2021]) ** 0.25 - 1
topic("growth", "Revenue growth", "Is WD-40's revenue growth in line with the growth the scenarios assume?",
      [origin("FinanceBench", fb("dg05")), origin("FinanceBench", fb("dg15"))],
      [leaf("growth-1", "fact", "What were net sales in FY2021 and FY2025, and the compound annual growth rate between them?",
            f"{m(rev[2021])} in FY2021 and {m(rev[2025])} in FY2025: {p(cagr)} a year.", evidence=[SX], cells=["Input sheet!B11", "Input sheet!C11"]),
       leaf("growth-2", "fact", "How much of the FY2025 change in net sales came from volume, price and currency?",
            "Volume added about $25.2m, price about $5.6m and currency translation took off $1.4m, on a $29.4m increase.", evidence=[S10K]),
       leaf("growth-3", "fact", "What growth did management guide for FY2026, from what base and at what exchange rates?",
            "5-9% from FY2025 pro forma results, which exclude the Americas homecare and cleaning brands held for sale, at FY2025 average exchange rates: $630-655m.", evidence=[S8K]),
       leaf("growth-4", "assumption", "Which growth rates do the scenarios use after year 1, and how do they compare with the FY2021-FY2025 rate?",
            f"Bear 4%, Base 6%, Bull 7% a year in years 2-5, against {p(cagr)} actual. Year 1 is set at the guidance range on the reported base: {p(A2['year1Growth']['bear'])}, {p(A2['year1Growth']['base'])}, {p(A2['year1Growth']['bull'])}.",
            cells=["Input sheet!B26", "Input sheet!B28"], methods=["dcf"]),
       leaf("growth-5", "forecast", "Will FY2026 net sales on the guidance basis (pro forma, FY2025 exchange rates) reach the $642.5m midpoint?",
            "Open at the case date.", status="open at case date",
            resolution={"object": "FY2026 net sales, pro forma and constant currency", "period": "FY ending 31 Aug 2026", "threshold": "$642.5m",
                        "rule": "Compare the constant-currency pro forma net sales in the FY2026 results release with $642.5m.", "linkedAssumption": "Input sheet!B26 (Base 3.63%)"},
            later={"text": "The FY2026 10-K reports net sales of $688.0m. That figure is on the reported basis: it includes the Americas homecare brands the company decided to keep and currency translation, so it does not resolve the question on the guidance basis.",
                   "sourceId": "wdfc26-10k"})],
      "FinanceBench asks whether a company's financials are those of a high-growth company and what drove revenue change. The WD-40 version asks the same about the years the scenarios extrapolate from, then tests the scenario inputs against them.")

gm = {y: gp[y] / rev[y] for y in rev}
om = {y: oi[y] / rev[y] for y in rev}
topic("margin", "Margins", "Does WD-40's margin history support the Base path from 16.9% to 18%?",
      [origin("FinanceBench", fb("dg13")), origin("FinanceBench", fb("dg17")), origin("FinanceBench", fb("dg03"))],
      [leaf("margin-1", "fact", "What was the gross margin in each fiscal year from 2021 to 2025?",
            ", ".join(f"FY{y} {p(gm[y])}" for y in gm) + ". It moved by more than 2 points in FY2022 and FY2023.", evidence=[SX]),
       leaf("margin-2", "fact", "What explained the change in gross margin from FY2024 to FY2025?",
            "Lower specialty chemical costs (+80 bp), lower aerosol can costs (+60 bp) and higher average selling prices (+50 bp), less higher warehousing, distribution and freight costs (-50 bp); 30 bp of the 170 bp rise is not attributed in the filing.", evidence=[S10K]),
       leaf("margin-3", "fact", "What was the operating margin in each fiscal year from 2021 to 2025?",
            ", ".join(f"FY{y} {p(om[y])}" for y in om) + ".", evidence=[SX], cells=["Valuation output!B4"]),
       leaf("margin-4", "fact", "How far was FY2025 cost of doing business from the company's own target?",
            "37% of net sales against a long-term target of 30%; gross margin was at its 55% target and adjusted EBITDA was 18% against 25%.", evidence=[S10K]),
       leaf("margin-5", "assumption", "Which margin paths do the scenarios use, and on what basis?",
            f"Year-1 margins come from operating-income guidance plus the workbook's R&D adjustment: {p(A2['year1Margin']['bear'])}, {p(A2['year1Margin']['base'])}, {p(A2['year1Margin']['bull'])}. Targets by year 5: Bear stays flat, Base 18%, Bull 20%. FY2017-FY2020 averaged {p(A2['marginFY2017_2020'])} reported.",
            cells=["Input sheet!B27", "Input sheet!B29"], methods=["dcf"])],
      "FinanceBench asks whether margins are improving and what drove the change. Here the facts are the filed margins and the drivers named in the FY2025 10-K, and the last question checks the Base path against them.")

capint = {y: capex[y] / rev[y] for y in rev}
bic = {y: b("StockholdersEquity", y) + b("LongTermDebtNoncurrent", y) + b("ShortTermBorrowings", y) - b("CashAndCashEquivalentsAtCarryingValue", y) for y in (2021, 2025)}
topic("capital", "Capital intensity and reinvestment", "Does WD-40 need as much capital to grow as the sales-to-capital ratio of 2.0 implies?",
      [origin("FinanceBench", fb("dg06")), origin("FinanceBench", fb("dg25")), origin("PE Bench", pe("voltaic-05-nwc-peg"), "Working-capital peg task, used for the working-capital questions.")],
      [leaf("capital-1", "fact", "What were capital expenditures as a share of net sales in each year from FY2021 to FY2025?",
            ", ".join(f"FY{y} {p(capint[y])}" for y in capint) + f". FY2025 capex was {m(capex[2025])} against depreciation and amortization of {m(da[2025])}.", evidence=[SX]),
       leaf("capital-2", "calculation", "How many times did inventory turn in FY2025 (cost of products sold over average inventory)?",
            f"{cogs[2025] / ((inv[2024] + inv[2025]) / 2):.2f} times: {m(cogs[2025])} over average inventory of {m((inv[2024] + inv[2025]) / 2)}.", evidence=[SX]),
       leaf("capital-3", "calculation", "What were receivables plus inventory minus payables at the end of FY2025, as a share of FY2025 net sales?",
            f"{m(ar[2025] + inv[2025] - ap[2025])}, or {p((ar[2025] + inv[2025] - ap[2025]) / rev[2025])} of net sales.", evidence=[SX]),
       leaf("capital-4", "calculation", "How much revenue did each dollar of added invested capital bring between FY2021 and FY2025?",
            f"Net sales rose {m(rev[2025] - rev[2021])}. Book equity plus borrowings minus cash rose from {m(bic[2021])} to {m(bic[2025])}, so each added dollar brought about ${(rev[2025] - rev[2021]) / (bic[2025] - bic[2021]):.2f} of revenue. This book measure excludes the capitalized R&D the workbook adds.",
            evidence=[SX], cells=["Valuation output!B39"]),
       leaf("capital-5", "assumption", "Which sales-to-capital ratio does the model use, and does the history above support it?",
            "2.0 in years 1-10 in every case. The FY2021-FY2025 book measure is close to 2, so the ratio is not changed in the scenarios.", cells=["Input sheet!B31", "Input sheet!B32"], methods=["dcf"])],
      "FinanceBench asks whether a company is capital-intensive and how fast it turns inventory; PE Bench asks for a working-capital peg. Here those facts test the single reinvestment input of the DCF.")

fcf = {y: ocf[y] - capex[y] for y in ocf}
lf = lf_topic("Cash Flow Return on Investment (CFROI) & Free Cash Flow Margin")
topic("cash", "Cash conversion", "How much of WD-40's profit turns into cash?",
      [origin("FinanceBench", fb("dg19")), origin("FinLFQA", lf, "FinLFQA questions compare free-cash-flow measures between dates with cited evidence; the same form is used here.")],
      [leaf("cash-1", "fact", "What were operating cash flow and capital expenditures in each year from FY2021 to FY2025?",
            "; ".join(f"FY{y} {m(ocf[y])} and {m(capex[y])}" for y in ocf) + ". FY2022 operating cash flow was low because inventory rose by $52.7m.", evidence=[SX]),
       leaf("cash-2", "calculation", "What was free cash flow (operating cash flow minus capex) as a share of net income in FY2023, FY2024 and FY2025?",
            ", ".join(f"FY{y} {p(fcf[y] / ni[y], 0)}" for y in (2023, 2024, 2025)) + f". FY2025 net income includes an $11.9m one-time tax benefit.", evidence=[SX]),
       leaf("cash-3", "fact", "Among operating, investing and financing activities, which brought in the most cash in FY2025?",
            f"Operating activities: {m(cf25['operating'])}. Investing used {m(-cf25['investing'])} and financing used {m(-cf25['financing'])}.", evidence=[SX])],
      "FinanceBench asks which cash-flow category brought in the most cash; FinLFQA asks for free-cash-flow comparisons with evidence. Both are answered here from the filed cash-flow statements.")

etr = {y: tax[y] / pretax[y] for y in tax}
topic("tax", "Taxes", "Which tax rate should the forecast start from?",
      [origin("FinanceBench", fb("dg23"))],
      [leaf("tax-1", "calculation", "How much did the effective tax rate change between FY2024 and FY2025?",
            f"From {p(etr[2024])} to {p(etr[2025])}: {(etr[2025] - etr[2024]) * 100:.1f} points.", evidence=[SX]),
       leaf("tax-2", "fact", "What one-time item explains the FY2025 rate?",
            "An $11.9m release of a reserve for an uncertain tax position. Without it the FY2025 rate is 22.2%.", evidence=[S10K], cells=["Input sheet!B23"]),
       leaf("tax-3", "assumption", "Which starting tax rate do the scenarios use?",
            "Bear 23.5%, Base 23.0%, Bull 22.5%, from the FY2026 guidance range of 22.5-23.5%; the original case uses the normalized 22.2%. All fade to 25% by year 10.", cells=["Input sheet!B23", "Input sheet!B24"], methods=["dcf"])],
      "FinanceBench asks how much the effective tax rate changed between two years. The WD-40 version adds the cause of the change and the rate the model starts from.")

topic("cost-of-capital", "Cost of capital", "What discount rate do market data support for WD-40 at 29 Aug 2025?",
      [origin("FinLFQA", lf_topic("Weighted Average Cost of Capital (WACC) Refinements")), origin("PE Bench", pe("voltaic-02-comparables"), "Rubric requires a declared pricing date; every market input here is dated.")],
      [leaf("coc-1", "fact", "What was the 10-year Treasury yield on 29 Aug 2025, and Damodaran's implied equity risk premium at the start of September 2025?",
            f"{p(A2['riskFree'], 2)} and {p(A2['erp']['t12m'], 2)}.", evidence=["ust-par-2025-08-29", "damodaran-erp-2025-09"]),
       leaf("coc-2", "calculation", "What betas do regressions of WD-40 on the S&P 500 give, and how much of the variation do they explain?",
            "; ".join(f"{r['years']}-year {r['frequency']}: {r['beta']:.2f} (R² {r['r2']:.3f})" for r in A2["regressionBetas"]) + ". None explains more than 11% of WD-40's returns.", evidence=["yahoo-prices"]),
       leaf("coc-3", "fact", "What were Damodaran's January 2025 unlevered betas for Chemical (Specialty) and Household Products?",
            f"{A2['industryUnleveredBetas']['Chemical (Specialty)']:.2f} and {A2['industryUnleveredBetas']['Household Products']:.2f}, corrected for cash.", evidence=["damodaran-betas-2025-01"]),
       leaf("coc-4", "assumption", "Which WACC do the scenarios use, and what did the original case use?",
            f"Bear {p(A2['waccCases']['bear']['wacc'], 2)} drifting to {p(A2['marketTerminalBear'], 2)}, Base {p(A2['waccCases']['base']['wacc'], 2)}, Bull {p(A2['waccCases']['bull']['wacc'], 2)}. The original case used 9% fading to 8%, labelled as an illustrative placeholder.",
            cells=["Cost of capital worksheet!B12", "Input sheet!B46"], methods=["dcf"])],
      "FinLFQA's WACC questions ask for the inputs behind a cost of capital with evidence; PE Bench requires a declared pricing date. Each input here carries its date and source.")

roic_all = [r for c in GC.values() for r in c["rows"]["roic"][1:11]]
roic_lo, roic_hi = min(roic_all), max(roic_all)
topic("returns", "Return on capital", "How long can WD-40 keep earning more than its cost of capital?",
      [origin("FinLFQA", lf_topic("Advanced Economic Value Added (EVA) Analysis")), origin("FinanceBench", fb("dg09"))],
      [leaf("returns-1", "calculation", "What was FY2025 return on invested capital in the workbook (after-tax operating income over invested capital)?",
            f"{p(GC['original']['rows']['roic'][0])}, on invested capital of {m(GC['original']['rows']['investedCapital'][0])} including capitalized R&D.", cells=["Valuation output!B40", "Valuation output!B39"]),
       leaf("returns-2", "fact", "What share of FY2025 net sales came from WD-40 Multi-Use Product?",
            f"$478.0m of $620.0m, or {p(477.961 / 619.985)}. WD-40 Specialist added $82.0m.", evidence=[S8K]),
       leaf("returns-3", "fact", "What share of FY2025 net sales came from outside the United States, and did any customer reach 10%?",
            "About 66% came from outside the US. No customer reached 10% of consolidated net sales.", evidence=[S10K]),
       leaf("returns-4", "calculation", "Does restating the DCF as invested capital plus economic profit give the same operating value?",
            "Yes. " + "; ".join(f"{k} {m(e['evaValue'])} against {m(e['dcfValue'])}" for k, e in eva.items()) + ". The two are the same calculation arranged differently, so this checks consistency, not value.", methods=["eva"]),
       leaf("returns-5", "assumption", "What return on new capital after year 10 do the scenarios assume?",
            f"Bear: equal to the cost of capital (no excess return). Base: 15%. Bull: 20%. In years 1-10 the model earns {p(roic_lo, 0)} to {p(roic_hi, 0)} on capital across the four cases.", cells=["Input sheet!B48", "Input sheet!B49", "Valuation output!M40"], methods=["dcf"])],
      "FinLFQA's EVA questions ask how economic profit and capital efficiency compare across periods; FinanceBench asks whether any product exceeds 20% of revenue. Together they ask how durable WD-40's excess return is.")

topic("payouts", "Shareholder payouts", "Is the dividend sustainable at the scenarios' growth rates?",
      [origin("FinanceBench", fb("dg18")), origin("FinanceBench", first("FinanceBench", sourceId="financebench_id_01858"))],
      [leaf("payouts-1", "fact", "What dividend per share did WD-40 pay in each year from FY2021 to FY2025?",
            ", ".join(f"FY{y} ${dps[y]:.2f}" for y in dps) + ". It rose every year.", evidence=[SX]),
       leaf("payouts-2", "calculation", "What share of FY2025 earnings per share went to dividends?",
            f"${dps[2025]:.2f} paid against $5.82 non-GAAP diluted EPS ({p(dps[2025] / 5.82, 0)}) or $6.69 GAAP EPS, which includes the one-time tax benefit ({p(dps[2025] / 6.69, 0)}).", evidence=[SX, S8K]),
       leaf("payouts-3", "fact", "How did FY2025 share repurchases compare with dividends?",
            f"{m(buyback25)} of repurchases against {m(dividends25)} of dividends.", evidence=[SX]),
       leaf("payouts-4", "calculation", "What does a dividend discount model give with the scenarios' cost of equity?",
            "; ".join(f"{k.title()} ${d['value']:.2f} (cost of equity {p(d['costOfEquity'], 2)}, terminal payout {p(d['terminalPayout'], 0)})" for k, d in ddm.items()) + ".", methods=["ddm"])],
      "FinanceBench asks whether a company paid dividends and whether it keeps a stable dividend trend. The WD-40 version adds payout and a dividend-based value.")

topic("financing", "Financing a buyout", "What could a financial buyer pay for WD-40?",
      [origin("PE Bench", pe("voltaic-08-debt-schedule")), origin("PE Bench", pe("voltaic-09-sources-uses")), origin("PE Bench", pe("voltaic-11-returns-waterfall")), origin("FinanceBench", fb("dg22"))],
      [leaf("financing-1", "fact", "How did borrowings change between the end of FY2024 and FY2025?",
            f"From {m(debt[2024])} to {m(debt[2025])}.", evidence=[SX], cells=["Input sheet!B15", "Input sheet!C15"]),
       leaf("financing-2", "calculation", "What was FY2025 operating income over interest expense?",
            f"{oi[2025] / interest25:.0f} times: {m(oi[2025])} over {m(interest25, 2)}.", evidence=[SX]),
       leaf("financing-3", "calculation", "At 5.0 times FY2025 EBITDA of debt, SOFR on 29 Aug 2025 plus 3.5%, a 20% target return and an exit at the peer median multiple, what is the highest price per share that works?",
            f"${lbo['base']['price']:.2f}, an entry multiple of {lbo['base']['entryEvToEbitda']:.1f} times EBITDA. Bear (4.5x debt, 25% target, 25th percentile exit) gives ${lbo['bear']['price']:.2f}; Bull (5.5x, 17.5%, 75th percentile) ${lbo['bull']['price']:.2f}.",
            methods=["lbo"]),
       leaf("financing-4", "assumption", "Which operating case does the buyout model use?",
            "The Base DCF case: its revenue, EBIT, tax rate and free cash flow before financing in years 1-5. EBITDA is put on a reported basis by removing the R&D adjustment and adding depreciation and amortization at the FY2025 share of sales.", methods=["lbo", "dcf"])],
      "PE Bench asks for a debt schedule, sources and uses, and returns; FinanceBench asks whether debt rose. Together they test what a sponsor could pay for WD-40.")

topic("market", "Market pricing", "What does the $216.04 price assume that the cases do not?",
      [origin("PE Bench", pe("voltaic-02-comparables")), origin("FinanceBench", fb("dg14"))],
      [leaf("market-1", "calculation", "What EV to EBITDA did five listed peers trade at on 29 Aug 2025, after adding back tagged one-off charges?",
            f"25th percentile {q_ev[0]:.1f}x, median {q_ev[1]:.1f}x, 75th percentile {q_ev[2]:.1f}x.", methods=["comps"]),
       leaf("market-2", "calculation", "What EV to EBITDA did WD-40 trade at on 29 Aug 2025, and at its previous four fiscal year-ends?",
            ", ".join(f"FY{o['fiscalYear']} {o['evToEbitda']:.1f}x" for o in own) + ".", methods=["own-history"]),
       leaf("market-3", "calculation", "Starting from Base, what single change reaches $216.04?",
            f"A WACC of {p(RV['wacc']['solution'], 2)} in every year, or a {p(RV['margin']['solution'])} operating margin by year 5, or {p(RV['growth']['solution'])} revenue growth in years 2-5. No terminal return on capital reaches it alone: at {p(RV['roic']['range'][1], 0)} the value is ${RV['roic']['valueAtBounds'][1]:.2f}.", methods=["dcf"]),
       leaf("market-4", "fact", "What price targets had analysts published by 29 Aug 2025?",
            "DA Davidson $300 (Buy, 11 Jul 2025) and Jefferies $280 (Hold, 18 Oct 2024). Other firms' targets were not found.", evidence=["target-dadavidson", "target-jefferies"]),
       leaf("market-5", "fact", "Can the company-defined adjusted EBITDA of $114.4m be reconciled to EBIT plus depreciation and amortization of $112.0m?",
            "Not from the material collected. The $2.4m difference sits in the company's non-GAAP reconciliation, which was not extracted.", status="insufficient data", evidence=[S8K])],
      "PE Bench requires peers and the target on one EBITDA definition; FinanceBench asks whether operating margin is improving. Here the facts measure how far the price sits from each method.")

topic("risks", "Threats to the business", "What could break the margin and growth assumptions?",
      [origin("FinCausal", causal[0] if causal else None, f"FinCausal marks cause and effect spans in financial text; {len(causal)} of its 1,109 practice pairs mention oil, commodities, currencies, tariffs, raw materials or freight. The WD-40 questions ask for the same cause and effect in WD-40's filings."),
       origin("FinanceBench", fb("dg21")), origin("FinanceBench", fb("dg11"))],
      [leaf("risks-1", "fact", "Which inputs does WD-40 name as its main costs, and how does the price of oil reach them?",
            "Specialty chemicals and aerosol cans. The 10-K says oil price volatility indirectly affects specialty chemical costs, many of which are indexed to refined oil products.", evidence=[S10K]),
       leaf("risks-2", "fact", "How did currency translation affect FY2025 net sales by segment?",
            "Americas -$4.7m, EIMEA +$3.5m, Asia-Pacific -$0.2m: -$1.4m in total.", evidence=[S10K]),
       leaf("risks-3", "fact", "Are restructuring costs shown separately in the FY2025 income statement?",
            "No restructuring line or restructuring fact appears in the FY2025 XBRL data, so the FinanceBench rule gives 0.", evidence=[SX]),
       leaf("risks-4", "forecast", "Will the FY2026 gross margin stay within the guided 55.5-56.5% range?",
            "Open at the case date.", status="open at case date",
            resolution={"object": "FY2026 gross margin", "period": "FY ending 31 Aug 2026", "threshold": "55.5% to 56.5%",
                        "rule": "Read gross margin from the FY2026 10-K income statement.", "linkedAssumption": "Input sheet!B27 and B29 (Base 16.9% and 18% operating margin)"},
            later={"text": "The FY2026 10-K reports a gross margin of 55.3%, below the original range; the company lowered its guidance to 54.5-55.5% in July 2026.", "sourceId": "wdfc26-10k"})],
      "FinCausal extracts cause and effect from financial text; FinanceBench asks for restructuring costs and material legal matters. The WD-40 version asks which costs move margins and through what channel.")

# later-information check for the two forecast leaves (computed, not typed): FY2026 facts filed after the case date
def later_fy26(tag):
    vals = [f for f in G[tag]["units"]["USD"] if f["form"] == "10-K" and f["end"] == "2026-08-31" and "start" in f]
    return max(vals, key=lambda f: f["filed"])["val"] / 1e6 if vals else None


rev26, gp26 = later_fy26("RevenueFromContractWithCustomerExcludingAssessedTax"), later_fy26("GrossProfit")
assert rev26 is None or abs(rev26 - 688.0) < 0.1, rev26
assert gp26 is None or abs(gp26 / rev26 - 0.553) < 0.0006, gp26 / rev26

# fixtures: one answer of each kind, checked on every build
FIX = {"growth-1": ("fact", "6.2%"), "capital-2": ("calculation", "3.51 times"), "market-5": ("fact", "insufficient data"),
       "growth-5": ("forecast", "open at case date"), "tax-1": ("calculation", "-13.4 points")}
idx = {l["id"]: l for t in topics for l in t["leaves"]}
for lid, (purpose, needle) in FIX.items():
    lf_ = idx[lid]
    assert lf_["purpose"] == purpose, lid
    assert needle in lf_["answer"] or needle == lf_["status"], (lid, lf_["answer"], lf_["status"])

sel = {"FinanceBench": sorted({o["sourceId"] for t in topics for o in t["origins"] if o["source"] == "FinanceBench"}),
       "FinLFQA": sorted({o["sourceId"] for t in topics for o in t["origins"] if o["source"] == "FinLFQA"}),
       "PE Bench": sorted({o["sourceId"] for t in topics for o in t["origins"] if o["source"] == "PE Bench"}),
       "FinCausal": [causal[0]["sourceId"]] if causal else [], "FinTextQA": []}
counts = collections.Counter(r["source"] for r in MERGED)
coverage = {s: {"records": counts[s], "usedAsOrigin": len(sel[s])} for s in counts}
coverage["FinTextQA"]["why"] = "The public part is 240 questions on banking regulation (Federal Reserve, HKMA, EU). None applies to a non-bank consumer products company; the textbook part was not released."
coverage["FinCausal"]["why"] = f"{len(causal)} cause-effect pairs mention input costs, currencies, tariffs or freight; they are news texts about other companies, so they shape the form of the risk questions rather than supplying them."
out = {"asOf": "2025-10-27", "note": "Questions adapted to WD-40 from the benchmarks; answers computed from filings and the model. Not a result of any benchmark.",
       "topics": topics, "coverage": coverage, "sources": SOURCES,
       "fixtures": {k: {"purpose": a, "expect": b_} for k, (a, b_) in FIX.items()}}
(ROOT / "models" / "questions" / "questions.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

L = ["# Stage 6: diligence questions", "",
     f"`python -I models/questions/extract.py` merged {sum(counts.values()):,} records: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()) + ". `python -I models/questions/build_questions.py` adapts them to WD-40 and computes every answer from filings filed by 27 Oct 2025, the FY2025 8-K and 10-K passages, or the model. The adapted set is not a benchmark result.", "",
     "Each topic starts from a judgement question. Following The Mom Test, the judgement is not asked directly: it is split into questions about specific past facts, then a question about which model input those facts test. Forecast questions state the object, period, threshold and resolution rule. Where later filings already resolve them, the result is shown and labelled as information from after the case date.", "",
     "| Source | Records | Used as origin | Note |", "|---|---:|---:|---|"]
for s, c in coverage.items():
    L.append(f"| {s} | {c['records']:,} | {c['usedAsOrigin']} | {c.get('why', '')} |")
L.append("")
for t in topics:
    L += [f"## {t['title']}", "", f"**{t['parent']}**", "", t["adaptation"], "",
          "Origins: " + "; ".join(f"{o['source']} `{o.get('sourceId', '')}`" + (f" ({o['originalText'][:110]}…)" if o.get("originalText") and len(o["originalText"]) > 110 else f" ({o['originalText']})" if o.get("originalText") else "") for o in t["origins"]), ""]
    for l_ in t["leaves"]:
        L.append(f"- *{l_['purpose']}*: {l_['text']}  ")
        L.append(f"  {l_['answer']}" + (f" Status: {l_['status']}." if l_["status"] != "answered" else ""))
        if l_["resolution"]:
            r = l_["resolution"]
            L.append(f"  Resolution: {r['rule']} Threshold {r['threshold']}; linked to {r['linkedAssumption']}.")
        if l_["laterInformation"]:
            L.append(f"  Later information (after the case date): {l_['laterInformation']['text']}")
    L.append("")
(ROOT / "reports" / "06-questions.md").write_text("\n".join(L), encoding="utf-8")
print(len(topics), "topics", sum(len(t["leaves"]) for t in topics), "leaves", coverage)
