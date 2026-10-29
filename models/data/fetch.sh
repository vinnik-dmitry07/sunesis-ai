#!/usr/bin/env bash
# Restores the raw inputs that are not committed: peer SEC XBRL company facts, then the five benchmark datasets
# from the revisions pinned in models/data/benchmarks/manifest.json.
# Market data, Damodaran files, Treasury yields, SOFR and WD-40's own XBRL facts are committed under models/data.
# Usage: bash models/data/fetch.sh   (run from the repository root)
set -euo pipefail
cd "$(dirname "$0")"
UA="Sunesis research (set your contact address here)"
mkdir -p sec
for p in chd:0000313927 clx:0000021076 enr:0001632790 rpm:0000110621 kwr:0000081362; do
  curl -s --compressed -A "$UA" "https://data.sec.gov/api/xbrl/companyfacts/CIK${p##*:}.json" -o "sec/${p%%:*}_companyfacts.json"
  sleep 0.3
done
cd ../..
python -I models/questions/collect.py   # benchmark files from pinned revisions, checked against the lock
echo "done"
