#!/usr/bin/env bash
# Restores the raw inputs that are not committed: peer SEC XBRL company facts and the five benchmark datasets.
# Market data, Damodaran files, Treasury yields, SOFR and WD-40's own XBRL facts are committed under models/data.
# Usage: bash models/data/fetch.sh   (run from the repository root)
set -euo pipefail
cd "$(dirname "$0")"
UA="Sunesis research (set your contact address here)"
mkdir -p sec benchmarks/financebench benchmarks/finlfqa benchmarks/fincausal benchmarks/pebench benchmarks/fintextqa
for p in chd:0000313927 clx:0000021076 enr:0001632790 rpm:0000110621 kwr:0000081362; do
  curl -s --compressed -A "$UA" "https://data.sec.gov/api/xbrl/companyfacts/CIK${p##*:}.json" -o "sec/${p%%:*}_companyfacts.json"
  sleep 0.3
done
curl -sL https://raw.githubusercontent.com/patronus-ai/financebench/main/data/financebench_open_source.jsonl -o benchmarks/financebench/financebench_open_source.jsonl
curl -sL https://huggingface.co/datasets/Dragongon/FinLFQA/resolve/main/data/validation.json -o benchmarks/finlfqa/validation.json
curl -sL https://raw.githubusercontent.com/yseop/YseopLab/develop/FNP_2020_FinCausal/data/practice/fnp2020-fincausal2-task2.csv -o benchmarks/fincausal/fnp2020-fincausal2-task2.csv
curl -sL https://raw.githubusercontent.com/GetCompoundAI/pe-bench/main/tasks/voltaic.jsonl -o benchmarks/pebench/voltaic.jsonl
curl -sL "https://raw.githubusercontent.com/AlexJJJChen/FinTextQA/main/manual-qa-regulation%20policy.xlsx" -o benchmarks/fintextqa/manual-qa-regulation_policy.xlsx
echo "done"
