"""Embeds models/out/valuation.json into index.html as one line between unique markers.

Idempotent: the same payload gives the same file. Atomic: writes a temp file, then replaces.
Run:  python -I models/inject.py [--check]
"""
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
START = b"/*BUNDLED_VALUATION:start*/"
END = b"/*BUNDLED_VALUATION:end*/"
ANCHOR = b"\nclass FormulaError extends Error"


def payload_line():
    data = json.loads((ROOT / "models" / "out" / "valuation.json").read_text(encoding="utf-8"))
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False, sort_keys=False)
    text = text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return START + b"const BUNDLED_VALUATION=" + text.encode("utf-8") + b";" + END


def main():
    html = INDEX.read_bytes()
    assert not html.startswith(b"\xef\xbb\xbf"), "index.html must not start with a BOM"
    line = payload_line()
    s, e = html.count(START), html.count(END)
    if s == 1 and e == 1:
        a = html.index(START)
        b = html.index(END) + len(END)
        new = html[:a] + line + html[b:]
    elif s == 0 and e == 0:
        assert html.count(ANCHOR) == 1, "anchor must appear exactly once"
        i = html.index(ANCHOR)
        new = html[:i] + b"\n" + line + html[i:]
    else:
        raise SystemExit(f"marker count mismatch: start={s} end={e}")
    if "--check" in sys.argv:
        if new != html:
            print("payload differs from index.html")
            sys.exit(1)
        print("up to date")
        return
    if new == html:
        print("index.html unchanged")
        return
    tmp = INDEX.with_suffix(".html.tmp")
    tmp.write_bytes(new)
    os.replace(tmp, INDEX)
    assert INDEX.read_bytes().count(START) == 1
    print(f"index.html updated: payload {len(line):,} bytes")


if __name__ == "__main__":
    main()
