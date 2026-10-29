"""Precedent transactions on portable-spreadsheet: EV / trailing EBITDA before synergies, from disclosed figures.

Data: models/data/precedents/deals.json (each figure with its source). Deals whose EBITDA is a forecast are listed
but kept out of the range. The engine has no PERCENTILE, so quartiles are computed here and written as constants.
Importable: exposes `sheets`, `method`, `sources`.
"""
import json
import pathlib
import statistics
import sys

import portable_spreadsheet as ps

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
D = json.loads((HERE / "data" / "precedents" / "deals.json").read_text(encoding="utf-8"))
deals = D["deals"]
COLS = ["Announced", "Enterprise value ($m)", "EBITDA ($m)", "EV / EBITDA", "Revenue ($m)", "Announced synergies ($m)", "Synergies / target revenue", "In range (1 = yes)"]
C = {k: i for i, k in enumerate(COLS)}
sh = ps.Sheet.create_new_sheet(len(deals), len(COLS), name="Precedent deals", rows_labels=[f"{d['acquirer']} / {d['target']}" for d in deals], columns_labels=COLS)
for i, d in enumerate(deals):
    sh.iloc[i, C["Announced"]] = d["announced"]
    sh.iloc[i, C["Enterprise value ($m)"]] = float(d["ev"])
    sh.iloc[i, C["EBITDA ($m)"]] = float(d["ebitda"])
    sh.iloc[i, C["EV / EBITDA"]] = sh.iloc[i, C["Enterprise value ($m)"]] / sh.iloc[i, C["EBITDA ($m)"]]
    sh.iloc[i, C["Revenue ($m)"]] = float(d["revenue"])
    sh.iloc[i, C["In range (1 = yes)"]] = 1.0 if d["inRange"] else 0.0
    if d["synergies"]:
        sh.iloc[i, C["Announced synergies ($m)"]] = float(d["synergies"])
        sh.iloc[i, C["Synergies / target revenue"]] = sh.iloc[i, C["Announced synergies ($m)"]] / sh.iloc[i, C["Revenue ($m)"]]
mult = sorted(sh.iloc[i, C["EV / EBITDA"]].value for i, d in enumerate(deals) if d["inRange"])
q = statistics.quantiles(mult, n=4, method="inclusive")
quart = (q[0], statistics.median(mult), q[2])
syn_pct = sorted(d["synergies"] / d["revenue"] for d in deals if d["synergies"])

VROWS = ["EBITDA FY2025", "Debt", "Cash", "Shares, DCF denominator (m)", "Deal EV / EBITDA (computed in Python from Precedent deals)",
         "Implied enterprise value", "Implied equity value", "Value per share"]
V = {k: i for i, k in enumerate(VROWS)}
val = ps.Sheet.create_new_sheet(len(VROWS), 3, name="Precedent valuation", rows_labels=VROWS, columns_labels=["25th percentile", "Median", "75th percentile"])
for j in range(3):
    for k, x in [("EBITDA FY2025", 103.793 + 8.191), ("Debt", 86.995), ("Cash", 58.13), ("Shares, DCF denominator (m)", 13.633263),
                 ("Deal EV / EBITDA (computed in Python from Precedent deals)", quart[j])]:
        val.iloc[V[k], j] = float(x)
    r = lambda row: val.iloc[V[row], j]  # noqa: E731
    val.iloc[V["Implied enterprise value"], j] = r("EBITDA FY2025") * r("Deal EV / EBITDA (computed in Python from Precedent deals)")
    val.iloc[V["Implied equity value"], j] = r("Implied enterprise value") - r("Debt") + r("Cash")
    val.iloc[V["Value per share"], j] = r("Implied equity value") / r("Shares, DCF denominator (m)")
per_share = [val.iloc[V["Value per share"], j].value for j in range(3)]
sheets = [sh, val]

sources = {f"deal-{d['id']}": {"title": f"{d['acquirer']} / {d['target']}, announced {d['announced']}", "url": d["sources"][0], "publishedAt": d["announced"]} for d in deals}
table = [["Deal", "Announced", "Buyer", "EV ($m)", "EBITDA ($m), basis", "EV / EBITDA", "In range", "Why it is here"]]
for i, d in enumerate(deals):
    table.append([f"{d['acquirer']} / {d['target']}", d["announced"], d["buyerType"], f"{d['ev']:,}", f"{d['ebitda']}: {d['ebitdaBasis']}",
                  f"{sh.iloc[i, C['EV / EBITDA']].value:.1f}x", "yes" if d["inRange"] else "no", d["comparability"]])
method = {
    "id": "precedents", "group": "multiples", "label": "Precedent transactions", "sublabel": f"EV / LTM EBITDA, 25th to 75th percentile of {len(mult)} deals",
    "kind": "range", "low": per_share[0], "base": per_share[1], "high": per_share[2], "status": "workbook",
    "note": (f"Control transactions for branded maintenance, auto-care, lubricant and asset-light consumer businesses, 2017-2022, with enterprise value and trailing EBITDA "
             f"before synergies disclosed by the parties. The multiples ({', '.join(f'{x:.1f}x' for x in mult)}) are computed from those figures; the parties' own stated multiples are listed where they exist. "
             f"Two forward-basis deals are shown but left out of the range. Quartiles {quart[0]:.1f}x / {quart[1]:.1f}x / {quart[2]:.1f}x applied to WD-40's FY2025 EBITDA of $112.0m. "
             f"Every deal sits far below the 26.4x WD-40 traded at, even with a control premium."),
    "table": table, "excluded": D["excluded"], "quartiles": quart, "synergyPctOfRevenue": syn_pct,
    "cells": ["Precedent valuation!B9", "Precedent valuation!C9", "Precedent valuation!D9"], "sourceIds": list(sources),
}

if __name__ == "__main__":
    print("multiples in range", [round(x, 2) for x in mult], "quartiles", [round(x, 2) for x in quart], "per share", [round(x, 2) for x in per_share])
    print("synergies / target revenue", [round(x, 4) for x in syn_pct])
