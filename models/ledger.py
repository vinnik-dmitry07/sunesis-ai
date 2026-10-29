"""Appends one row to reports/08-change-ledger.md with the values of the current build.

Each integration step runs a build, then `python -I models/ledger.py "<state>" "<what changed>"`, so the effect of
every change is recorded on its own. Deltas are against the previous row and depend on the order of the steps.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "models" / "out"
REPORT = ROOT / "reports" / "08-change-ledger.md"
state, change = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""

E = json.loads((OUT / "scenarios_eval.json").read_text())["results"]
methods = {m["id"]: m for m in json.loads((OUT / "valuation.json").read_text(encoding="utf-8"))["methods"]}
row = {"Original": E["original"]["result"]["value"], "Bear": E["bear"]["result"]["value"], "Base": E["base"]["result"]["value"],
       "Bull": E["bull"]["result"]["value"]}
for mid, label in [("comps", "Comps median"), ("precedents", "Precedents median"), ("ddm", "DDM base"), ("lbo", "LBO base"), ("synergies", "Strategic base")]:
    row[label] = methods[mid]["base"] if mid in methods else None
cols = list(row)
if not REPORT.exists():
    head = ["# Change ledger", "",
            "One row per integration step, each measured with a full build. A delta is against the row above and depends on the order of the steps; the deltas are not independent effects.", "",
            "| State | What changed | " + " | ".join(cols) + " |", "|---|---|" + "|".join("---:" for _ in cols) + "|"]
    REPORT.write_text("\n".join(head) + "\n", encoding="utf-8")
lines = REPORT.read_text(encoding="utf-8").rstrip("\n").split("\n")
prev = None
for l in reversed(lines):
    if l.startswith("| ") and not l.startswith("| State") and "<!--" in l:
        prev = json.loads(l.split("<!--")[1].split("-->")[0])
        break
fmt = lambda k, v: "" if v is None else f"${v:,.2f}" + ("" if not prev or prev.get(k) is None or abs(v - prev[k]) < 0.005 else f" ({v - prev[k]:+,.2f})")  # noqa: E731
line = f"| {state} | {change} | " + " | ".join(fmt(k, row[k]) for k in cols) + f" |<!--{json.dumps(row)}-->"
with open(REPORT, "a", encoding="utf-8", newline="\n") as f:
    f.write(line + "\n")
print(line.split("<!--")[0])
