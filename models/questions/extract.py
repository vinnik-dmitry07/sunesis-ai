"""Merges the five benchmark datasets into one file of question records.

Inputs (downloaded by collect.sh into models/data/benchmarks/, treated as untrusted data and only parsed here):
  FinanceBench open-source sample, FinLFQA validation split, FinCausal 2020 practice task 2, PE Bench Voltaic
  tasks, FinTextQA public regulation/policy QA. Output: models/out/questions_merged.jsonl and a count summary.
Run:  python -I models/questions/extract.py
"""
import collections
import csv
import json
import pathlib

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / "models" / "data" / "benchmarks"
OUT = ROOT / "models" / "out"
OUT.mkdir(parents=True, exist_ok=True)
LIC = {
    "FinanceBench": "CC BY-NC 4.0 (patronus-ai/financebench)",
    "FinLFQA": "MIT (Hugging Face card, Dragongon/FinLFQA)",
    "FinCausal": "CC BY 4.0 (FinCausal 2020 shared task)",
    "PE Bench": "See GetCompoundAI/pe-bench repository",
    "FinTextQA": "MIT (AlexJJJChen/FinTextQA README); textbook part not released",
}
recs = []
for line in (B / "financebench" / "financebench_open_source.jsonl").read_text(encoding="utf-8").splitlines():
    x = json.loads(line)
    recs.append({"source": "FinanceBench", "sourceId": x["financebench_id"], "question": x["question"], "type": x["question_type"],
                 "reasoning": x.get("question_reasoning"), "template": x.get("domain_question_num"), "company": x["company"],
                 "docName": x.get("doc_name")})
for x in json.loads((B / "finlfqa" / "validation.json").read_text(encoding="utf-8")):
    recs.append({"source": "FinLFQA", "sourceId": f"validation-{x['id']}", "question": x["question"], "type": "long-form with attribution",
                 "reasoning": x.get("topic"), "template": None, "company": None,
                 "knowledge": x.get("professional knowledge list"), "numericalValues": x.get("numerical_values")})
with open(B / "fincausal" / "fnp2020-fincausal2-task2.csv", encoding="utf-8") as f:
    rows = list(csv.reader(f, delimiter=";"))
for r in rows[1:]:
    recs.append({"source": "FinCausal", "sourceId": r[0].strip(), "question": None, "type": "cause-effect extraction",
                 "text": r[1].strip(), "cause": r[2].strip(), "effect": r[3].strip()})
for line in (B / "pebench" / "voltaic.jsonl").read_text(encoding="utf-8").splitlines():
    x = json.loads(line)
    recs.append({"source": "PE Bench", "sourceId": x["task_id"], "question": x["prompt"], "type": f"deal task: {x['deliverable']}",
                 "rubrics": [{"id": r["id"], "weight": r["weight"], "description": r["description"]} for r in x["rubrics"]]})
wb = openpyxl.load_workbook(B / "fintextqa" / "manual-qa-regulation_policy.xlsx", read_only=True, data_only=True)
rows = list(wb["Sheet1"].iter_rows(values_only=True))
hdr = rows[0]
for i, r in enumerate(rows[1:], start=1):
    d = dict(zip(hdr, r))
    if d.get("question"):
        recs.append({"source": "FinTextQA", "sourceId": f"policy-{i}", "question": d["question"], "type": "regulation and policy QA",
                     "institute": d.get("institute"), "document": d.get("document")})
for r in recs:
    r["license"] = LIC[r["source"]]
with open(OUT / "questions_merged.jsonl", "w", encoding="utf-8") as f:
    for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
counts = collections.Counter(r["source"] for r in recs)
(OUT / "questions_merged_summary.json").write_text(json.dumps({"records": len(recs), "bySource": counts,
                                                              "financeBenchTypes": collections.Counter(r["type"] for r in recs if r["source"] == "FinanceBench"),
                                                              "finTextQAInstitutes": collections.Counter(r.get("institute") for r in recs if r["source"] == "FinTextQA")}, indent=1))
print(len(recs), dict(counts))
