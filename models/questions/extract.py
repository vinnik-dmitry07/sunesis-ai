"""Merges the five benchmark datasets into one file of question records.

Inputs: the pinned files listed in models/data/benchmarks/manifest.json (fetched by collect.py). Each file's sha256 is
checked against the lock before it is parsed; a mismatch stops the run. The files are inert data and only parsed here.
Every record carries its dataset id, pinned revision and file hash. Reuse rights are not established
(licenseKnown is false), so the page quotes at most a short original text per question.
Run:  python -I models/questions/extract.py  ->  models/out/questions_merged.jsonl
"""
import collections
import csv
import hashlib
import io
import json
import pathlib
import sys

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / "models" / "data" / "benchmarks"
OUT = ROOT / "models" / "out"
OUT.mkdir(parents=True, exist_ok=True)
LOCK = {s["id"]: s for s in json.loads((B / "manifest.json").read_text(encoding="utf-8"))["sources"]}
NAMES = {"financebench": "FinanceBench", "finlfqa": "FinLFQA", "fincausal": "FinCausal", "pe-bench": "PE Bench", "fintextqa": "FinTextQA"}


def load(dataset):
    src = LOCK[dataset]
    data = (B / src["filename"]).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != src["sha256"]:
        sys.exit(f"{dataset}: content hash {digest[:12]}… does not match the lock {src['sha256'][:12]}…; run collect.py")
    return data


def stamp(dataset, rec):
    src = LOCK[dataset]
    return {"source": NAMES[dataset], "dataset": dataset, "revision": src["revision"], "datasetSha256": src["sha256"],
            "datasetUrl": src["page"], "licenseKnown": False, **rec}


recs = []
for line in load("financebench").decode("utf-8").splitlines():
    x = json.loads(line)
    recs.append(stamp("financebench", {"sourceId": x["financebench_id"], "question": x["question"], "type": x["question_type"],
                                       "reasoning": x.get("question_reasoning"), "template": x.get("domain_question_num"),
                                       "company": x["company"], "docName": x.get("doc_name")}))
for x in json.loads(load("finlfqa").decode("utf-8")):
    recs.append(stamp("finlfqa", {"sourceId": f"validation-{x['id']}", "question": x["question"], "type": "long-form with attribution",
                                  "reasoning": x.get("topic"), "knowledge": x.get("professional knowledge list"),
                                  "numericalValues": x.get("numerical_values")}))
rows = list(csv.reader(io.StringIO(load("fincausal").decode("utf-8")), delimiter=";"))
for r in rows[1:]:
    recs.append(stamp("fincausal", {"sourceId": r[0].strip(), "question": None, "type": "cause-effect extraction",
                                    "text": r[1].strip(), "cause": r[2].strip(), "effect": r[3].strip()}))
for line in load("pe-bench").decode("utf-8").splitlines():
    x = json.loads(line)
    recs.append(stamp("pe-bench", {"sourceId": x["task_id"], "question": x["prompt"], "type": f"deal task: {x['deliverable']}",
                                   "rubrics": [{"id": r["id"], "weight": r["weight"], "description": r["description"]} for r in x["rubrics"]]}))
wb = openpyxl.load_workbook(io.BytesIO(load("fintextqa")), read_only=True, data_only=True)
rows = list(wb["Sheet1"].iter_rows(values_only=True))
hdr = rows[0]
for i, r in enumerate(rows[1:], start=1):
    d = dict(zip(hdr, r))
    if d.get("question"):
        recs.append(stamp("fintextqa", {"sourceId": f"policy-{i}", "question": d["question"], "type": "regulation and policy QA",
                                        "institute": d.get("institute"), "document": d.get("document")}))
with open(OUT / "questions_merged.jsonl", "w", encoding="utf-8", newline="\n") as f:
    for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
counts = collections.Counter(r["source"] for r in recs)
print(len(recs), dict(counts))
