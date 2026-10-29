"""Regional revenue build for the WD-40 scenarios (adapted from PR #1's segment illustration).

Year-1 consolidated revenue is fixed by FY2026 guidance. It is allocated to the three reported segments in
proportion to b_i (1 + r_i), where b_i is FY2025 reported segment revenue and r_i the analyst's regional rate:
an analyst allocation of total guidance, not a company regional forecast. Regional rates then apply in years
2-5 and fade to terminal growth in years 6-10. The Ginzu takes one growth rate for years 2-5, so the regional
build is compressed to g = (sum_i R_i5 / Guidance)^(1/4) - 1. That keeps year-1 and year-5 revenue; the
revenue differences in the other years are recorded as residuals.

The guidance base (currency-adjusted pro forma FY2025 net sales of about $603m) leaves out the homecare brands
held for sale and the divested 1001 brands. The release does not split that difference by segment, so b_i is
reported revenue; `perimeter_bound` reports how far the years 2-5 rate moves if the whole difference is taken
out of the Americas.
"""
import json
import math
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
RESEARCH = json.loads((HERE / "data" / "research.json").read_text(encoding="utf-8"))
REGIONS = {r["id"]: r for r in RESEARCH["operatingFacts"]["regions"]}
HISTORY = RESEARCH["operatingFacts"].get("regionalHistory", {})

# Analyst regional rates for years 1-5 (year 1 only sets the split of the guided total).
REGIONAL_GROWTH = {
    "bear": {"americas": 0.02, "eimea": 0.04, "asiaPacific": 0.05},
    "base": {"americas": 0.04, "eimea": 0.07, "asiaPacific": 0.08},
    "bull": {"americas": 0.06, "eimea": 0.09, "asiaPacific": 0.11},
}
# PR #1's rates, kept as a sensitivity (no source was given for them).
PR1_GROWTH = {
    "bear": {"americas": 0.01, "eimea": 0.04, "asiaPacific": 0.06},
    "base": {"americas": 0.04, "eimea": 0.07, "asiaPacific": 0.10},
    "bull": {"americas": 0.06, "eimea": 0.09, "asiaPacific": 0.13},
}


def build(guidance_total, rates, terminal_growth, base=None):
    base = base or {k: r["revenue"] for k, r in REGIONS.items()}
    if set(rates) != set(base):
        raise ValueError("regional rate keys must match the reported segments")
    for k, v in list(rates.items()) + [("terminal", terminal_growth)]:
        if not math.isfinite(v) or v <= -1:
            raise ValueError(f"{k} growth must be finite and above -100%")
    if not math.isfinite(guidance_total) or guidance_total <= 0:
        raise ValueError("guidance total must be positive")
    q = {k: base[k] * (1 + rates[k]) for k in base}
    year1 = {k: guidance_total * q[k] / sum(q.values()) for k in base}
    rows = [{"year": 1, "regions": year1, "revenue": sum(year1.values())}]
    cur = dict(year1)
    for y in range(2, 11):
        g = {k: rates[k] if y <= 5 else rates[k] - (rates[k] - terminal_growth) * (y - 5) / 5 for k in base}
        cur = {k: cur[k] * (1 + g[k]) for k in base}
        rows.append({"year": y, "regions": dict(cur), "revenue": sum(cur.values())})
    g25 = (rows[4]["revenue"] / rows[0]["revenue"]) ** 0.25 - 1
    # The Ginzu path: year 1 = guidance, years 2-5 at g25, years 6-10 fading linearly to terminal growth.
    ginzu, prev = [guidance_total], guidance_total
    for y in range(2, 11):
        gy = g25 if y <= 5 else g25 - (g25 - terminal_growth) * (y - 5) / 5
        prev *= 1 + gy
        ginzu.append(prev)
    residuals = [rows[i]["revenue"] - ginzu[i] for i in range(10)]
    return {"year1Regions": year1, "rows": rows, "growth2to5": g25, "ginzuRevenue": ginzu, "residuals": residuals,
            "checks": {"year1MatchesGuidance": abs(rows[0]["revenue"] - guidance_total) < 1e-9,
                       "year5Preserved": abs(residuals[4]) < 1e-9}}


def scenario(guidance_total, rates, terminal_growth):
    main = build(guidance_total, rates, terminal_growth)
    gap = sum(r["revenue"] for r in REGIONS.values()) - RESEARCH["guidance"][0]["fy25ProFormaCurrencyAdjustedRevenueApprox"]
    adjusted = {k: r["revenue"] for k, r in REGIONS.items()}
    adjusted["americas"] -= gap
    bound = build(guidance_total, rates, terminal_growth, base=adjusted)
    main["perimeterBound"] = {"unassignedFY2025Revenue": gap, "growth2to5IfAllFromAmericas": bound["growth2to5"],
                              "differencePp": (bound["growth2to5"] - main["growth2to5"]) * 100}
    return main


def regional_history():
    """FY2022-FY2025 segment revenue and growth (FY2022-FY2023 under the earlier EMEA / Asia-Pacific definitions)."""
    out = {}
    for k, r in REGIONS.items():
        h = dict(HISTORY.get(k, {}))
        h["FY2024"], h["FY2025"] = r["priorRevenue"], r["revenue"]
        years = sorted(h)
        out[k] = {"revenue": h, "growthFY2025": r["revenue"] / r["priorRevenue"] - 1,
                  "cagr": (h[years[-1]] / h[years[0]]) ** (1 / (len(years) - 1)) - 1 if len(years) > 1 else None,
                  "cagrPeriod": f"{years[0]}-{years[-1]}"}
    return out
