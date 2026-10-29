"""Contract checks of the merged models, run by models/build.py after the artifacts are built.

They read the current build's outputs and fail when a contract breaks: the original case, each scenario's year-1
guidance, the regional build, terminal validity, EVA, the buyout schedule, question provenance, and the match
between the check reports and the files they certify. Old values and payload schemas are not requirements.
Run:  python -I -m unittest discover -s models/tests -v   (from the repository root, after a build)
"""
import hashlib
import json
import math
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
M = ROOT / "models"
OUT = M / "out"
sys.path.insert(0, str(M))
import segments  # noqa: E402

read = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))  # noqa: E731
sha = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()  # noqa: E731
GC = read("models/out/ginzu_cases.json")["cases"]
EV = read("models/out/scenarios_eval.json")["results"]
CORE = read("models/out/valuation_book/core_results.json")
CELLS = read("models/out/valuation_book/valuation_cells.json")
RES = read("models/data/research.json")
GUIDE = next(g for g in RES["guidance"] if g["id"] == "fy26-original")
A2 = read("models/out/stage2_assumptions.json")
Q = read("models/questions/questions.json")
CASES = ("bear", "base", "bull")


def drv(case, key):
    return GC[case]["drivers"][key]["value"]


def guided(case, low, high):
    return {"bear": low, "base": (low + high) / 2, "bull": high}[case]


class OriginalAndScenarios(unittest.TestCase):
    def test_original_case_is_unchanged(self):
        self.assertEqual(EV["original"]["result"]["value"], 88.15029580134913)

    def test_year_1_reproduces_each_scenarios_own_guidance(self):
        for k in CASES:
            with self.subTest(case=k):
                sales = guided(k, GUIDE["netSalesLow"], GUIDE["netSalesHigh"])
                income = guided(k, GUIDE["operatingIncomeLow"], GUIDE["operatingIncomeHigh"]) + A2["rndAdjustment"]
                rows = GC[k]["rows"]
                self.assertAlmostEqual(rows["revenue"][1], sales, places=9)
                self.assertAlmostEqual(rows["ebit"][1], income, places=9)
                self.assertEqual(drv(k, "growth1"), sales / drv("original", "revenue0") - 1)

    def test_python_dcf_rows_match_the_engine_for_every_saved_case(self):
        report = read("models/out/dcf/compare.json")
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["inputs"]["ginzu_cases.json"], sha("models/out/ginzu_cases.json"))
        self.assertEqual(report["inputs"]["dcf/dcf_rows.json"], sha("models/out/dcf/dcf_rows.json"))

    def test_terminal_rates_are_valid(self):
        for k in GC:
            with self.subTest(case=k):
                g, w = drv(k, "growthT"), drv(k, "waccT")
                self.assertGreater(w, g)
                if drv(k, "roicOverride") == 1:
                    self.assertGreater(drv(k, "roicT"), g)


class RegionalBuild(unittest.TestCase):
    def test_year_1_allocates_guidance_in_proportion_to_base_times_growth(self):
        rates = segments.REGIONAL_GROWTH["base"]
        r = segments.build(642.5, rates, 0.025)
        self.assertAlmostEqual(sum(r["year1Regions"].values()), 642.5, places=9)
        base = {k: x["revenue"] for k, x in segments.REGIONS.items()}
        q = {k: base[k] * (1 + rates[k]) for k in base}
        for k in base:
            self.assertAlmostEqual(r["year1Regions"][k] / r["year1Regions"]["americas"], q[k] / q["americas"], places=12)

    def test_compression_keeps_year_1_and_year_5_revenue(self):
        for k, rates in segments.REGIONAL_GROWTH.items():
            with self.subTest(case=k):
                r = segments.build(guided(k, GUIDE["netSalesLow"], GUIDE["netSalesHigh"]), rates, drv(k, "growthT"))
                self.assertAlmostEqual(r["residuals"][0], 0, places=9)
                self.assertAlmostEqual(r["residuals"][4], 0, places=9)
                self.assertAlmostEqual(r["ginzuRevenue"][4], r["rows"][4]["revenue"], places=9)
                self.assertEqual(drv(k, "growth25"), r["growth2to5"])

    def test_invalid_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            segments.build(642.5, {"americas": 0.04, "eimea": 0.07}, 0.025)
        with self.assertRaises(ValueError):
            segments.build(0, segments.REGIONAL_GROWTH["base"], 0.025)
        with self.assertRaises(ValueError):
            segments.build(642.5, {**segments.REGIONAL_GROWTH["base"], "eimea": float("nan")}, 0.025)


def sheet_values(sheet):
    """{(row label, column label): value} for an exported method sheet."""
    out = {}
    for c in CELLS.values():
        if c["sheet"] == sheet and c.get("label") and " · " in c["label"]:
            row, col = c["label"].rsplit(" · ", 1)
            out[(row, col)] = c["pythonValue"] if c.get("formula") else c["value"]
    return out


class Methods(unittest.TestCase):
    def test_eva_restates_the_dcf_exactly(self):
        for k, e in CORE["eva"].items():
            with self.subTest(case=k):
                self.assertLess(abs(e["difference"]), 1e-6)

    def test_buyout_schedule_follows_the_lender_rules(self):
        for k, sol in CORE["lbo"].items():
            v = sheet_values(f"LBO {k.title()}")
            e = lambda row: v[(row, "Entry / FY2025")]  # noqa: E731
            y = lambda row, t: v[(row, f"Year {t}")]  # noqa: E731
            with self.subTest(case=k):
                self.assertIn(sol["status"].split(":")[0], {"boundary found", "no solution", "infeasible", "search ceiling reached"})
                self.assertAlmostEqual(e("Sources minus uses"), 0, places=9)
                self.assertAlmostEqual(e("IRR"), e("MOIC") ** 0.2 - 1, places=12)
                debt = e("Debt, end of year")
                for t in range(1, 6):
                    mandatory, sweep = y("Mandatory repayment", t), y("Cash sweep", t)
                    self.assertLessEqual(mandatory, debt + 1e-9)
                    self.assertGreaterEqual(sweep, 0)
                    self.assertLessEqual(sweep, debt - mandatory + 1e-9)
                    self.assertLessEqual(sweep, max(0.0, y("Cash available above minimum", t) - mandatory) + 1e-9)
                    self.assertAlmostEqual(y("Debt, end of year", t), debt - mandatory - sweep, places=9)
                    if e("Feasible (1 = no funding shortfall)") == 1:
                        self.assertGreaterEqual(y("Cash, end of year", t), e("Minimum cash") - 1e-9)
                    debt = y("Debt, end of year", t)
                if sol["status"] == "boundary found":
                    self.assertGreaterEqual(e("IRR"), sol["hurdle"] - 1e-12)
                    self.assertAlmostEqual(e("Entry price per share"), sol["price"], places=9)


class Questions(unittest.TestCase):
    def test_origins_carry_the_pinned_revision_and_hash(self):
        lock = {s["id"]: s for s in read("models/data/benchmarks/manifest.json")["sources"]}
        for t in Q["topics"]:
            for o in t["origins"]:
                with self.subTest(origin=o["key"]):
                    self.assertEqual(o["datasetSha256"], lock[o["dataset"]]["sha256"])
                    self.assertEqual(o["revision"], lock[o["dataset"]]["revision"])
                    self.assertIs(o["licenseKnown"], False)
                    if o["source"] == "FinCausal":
                        self.assertTrue(o["text"] and o["cause"] and o["effect"])

    def test_every_earlier_question_has_one_disposition(self):
        known = {f"{b['branch']}:{q['id']}" for b in read("models/questions/merge_inputs.json")["branches"] for q in b["questions"]}
        seen = [d["question"] for d in Q["dispositions"]]
        self.assertEqual(sorted(seen), sorted(known))
        for d in Q["dispositions"]:
            self.assertIn(d["disposition"], {"kept", "merged", "excluded"})
            self.assertTrue(d.get("into") or d.get("reason"))

    def test_every_question_cites_evidence_and_forecasts_state_their_rule(self):
        for t in Q["topics"]:
            for l in t["leaves"]:
                with self.subTest(question=l["id"]):
                    self.assertTrue(l["evidence"])
                    if l["purpose"] == "forecast":
                        self.assertEqual(l["status"], "open at case date")
                        self.assertTrue(all(l["resolution"][k] for k in ("object", "period", "threshold", "rule", "linkedAssumption")))

    def test_later_information_stays_apart_from_answers(self):
        later_sources = {s for t in Q["topics"] for l in t["leaves"] if l["laterInformation"] for s in l["laterInformation"]["sourceIds"]}
        self.assertTrue(later_sources)
        for s in later_sources:
            self.assertGreater(Q["sources"][s]["publishedAt"], Q["asOf"])
        later_texts = [l["laterInformation"]["text"] for t in Q["topics"] for l in t["leaves"] if l["laterInformation"]]
        for t in Q["topics"]:
            for l in t["leaves"]:
                with self.subTest(question=l["id"]):
                    for needle in ("$688.0m", "55.3%", "54.5%", "July 2026"):
                        self.assertNotIn(needle, l["answer"])
        self.assertTrue(any("$688.0m" in x for x in later_texts))


class Artifacts(unittest.TestCase):
    def test_check_reports_certify_the_current_files(self):
        checks = read("models/out/checks.json")
        cells = sha("models/out/valuation_book/valuation_cells.json")
        self.assertEqual(checks["engine"]["cellsSha256"], cells)
        self.assertEqual(checks["engine"]["failed"], 0)
        self.assertGreater(checks["engine"]["checked"], 0)
        if "excel" not in checks:
            self.skipTest("no Excel check in this build")
        self.assertEqual(checks["excel"]["cellsSha256"], cells)
        self.assertEqual(checks["excel"]["publishedSha256"], sha(checks["excel"]["publishedPath"]))
        self.assertEqual(checks["excel"]["failed"], 0)
        self.assertTrue(checks["excelInputChanges"])
        for x in checks["excelInputChanges"]:
            self.assertEqual(x["failed"], 0, x["change"])
            self.assertGreater(x["checked"], 0)

    def test_page_payload_is_the_built_payload(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        a = html.index("/*BUNDLED_VALUATION:start*/const BUNDLED_VALUATION=") + len("/*BUNDLED_VALUATION:start*/const BUNDLED_VALUATION=")
        embedded = json.JSONDecoder().raw_decode(html, a)[0]
        self.assertEqual(embedded, read("models/out/valuation.json"))
        self.assertTrue(math.isfinite(embedded["methods"][0]["base"]))


if __name__ == "__main__":
    unittest.main()
