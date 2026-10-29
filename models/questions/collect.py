"""Downloads the five benchmark files from pinned revisions and checks them against the committed lock.

models/data/benchmarks/manifest.json is the lock: each source has a pinned revision, URL, sha256 and size.
A download or cached file whose bytes do not match the lock is an error. Only `--relock` writes new hashes,
and it should be used when a new revision is chosen on purpose. Files are inert data; nothing in them is executed.
Availability does not establish reuse rights; every source is recorded with licenseKnown false.
Run:  python -I models/questions/collect.py [--refresh] [--relock]
"""
import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "models" / "data" / "benchmarks"
LOCK = DATA / "manifest.json"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Sunesis-benchmark-snapshot/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="download even when a cached file exists")
    ap.add_argument("--relock", action="store_true", help="record the downloaded hashes as the new lock")
    args = ap.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    DATA.mkdir(parents=True, exist_ok=True)
    problems = []
    for src in lock["sources"]:
        path = DATA / src["filename"]
        data = path.read_bytes() if path.exists() and not args.refresh else fetch(src["url"])
        digest = hashlib.sha256(data).hexdigest()
        if args.relock:
            src.update({"sha256": digest, "sizeBytes": len(data)})
        elif digest != src["sha256"] or len(data) != src["sizeBytes"]:
            problems.append(f"{src['id']}: sha256 {digest[:12]}… / {len(data)} bytes, lock says {src['sha256'][:12]}… / {src['sizeBytes']} bytes")
            continue
        if not path.exists() or args.refresh:
            path.write_bytes(data)
        print(f"ok   {src['id']}: {len(data):,} bytes, sha256 {digest[:12]}…, revision {src['revision'][:12]}")
    if args.relock:
        with open(LOCK, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(lock, indent=2) + "\n")
        print("lock rewritten on request (--relock)")
    if problems:
        print("FAIL content does not match the lock:\n  " + "\n  ".join(problems))
        sys.exit(1)


if __name__ == "__main__":
    main()
