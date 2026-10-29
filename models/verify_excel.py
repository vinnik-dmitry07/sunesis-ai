"""Recalculates an exported workbook in Microsoft Excel and compares every formula cell to the Python value.

Steps: open, full rebuild recalculation, read, save a recalculated copy, reopen it, read again.
Usage: python -I models/verify_excel.py path/to/book.xlsx path/to/cells.json [--set "Sheet!B2=0.07" ...]
With --set, the listed inputs are changed in Excel before recalculation and the comparison is skipped
for cells downstream of them (their expected values are in a separate cells file).
Exit code 0 when all formula cells match within 1e-9 relative (or absolute near zero).
"""
import json
import pathlib
import sys
import time

import pythoncom
import win32com.client as win32


def read_values(wb, ids):
    out = {}
    for cid in ids:
        sheet, addr = cid.rsplit("!", 1)
        out[cid] = wb.Worksheets(sheet).Range(addr).Value
    return out


def compare(vals, cells):
    bad, worst = [], 0.0
    for cid, v in vals.items():
        py = cells[cid]["pythonValue"]
        if isinstance(py, bool):
            py = float(py)
        if isinstance(py, (int, float)) and isinstance(v, (int, float)):
            d = abs(v - py)
            worst = max(worst, d / max(1.0, abs(py)))
            if not (d <= 1e-9 or d <= 1e-9 * abs(py)):
                bad.append((cid, cells[cid]["formula"], py, v))
        elif str(py) != str(v):
            bad.append((cid, cells[cid]["formula"], py, v))
    return bad, worst


def main():
    xlsx = pathlib.Path(sys.argv[1]).resolve()
    cells = json.loads(pathlib.Path(sys.argv[2]).read_text())
    sets = [a.split("=", 1) for a in sys.argv[3:] if "=" in a and not a.startswith("--")]
    formula_ids = [k for k, c in cells.items() if c.get("formula")]
    pythoncom.CoInitialize()
    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    recalced = xlsx.with_name(xlsx.stem + ".recalculated.xlsx")
    try:
        wb = excel.Workbooks.Open(str(xlsx))
        for cid, v in sets:
            sheet, addr = cid.rsplit("!", 1)
            wb.Worksheets(sheet).Range(addr).Value = float(v) if v.replace(".", "", 1).replace("-", "", 1).isdigit() else v
        excel.CalculateFullRebuild()
        first = read_values(wb, formula_ids)
        wb.SaveAs(str(recalced))
        wb.Close(SaveChanges=False)
        time.sleep(0.5)
        wb2 = excel.Workbooks.Open(str(recalced))
        second = read_values(wb2, formula_ids)
        wb2.Close(SaveChanges=False)
    finally:
        excel.Quit()
    bad, worst = compare(first, cells)
    reread_diff = [k for k in formula_ids if first[k] != second[k]]
    print(f"excel check {xlsx.name}: {len(formula_ids)} formulas, {len(bad)} mismatches, worst relative difference {worst:.2e}, "
          f"{len(reread_diff)} cells changed after save and reopen")
    for b in bad[:20]:
        print("  MISMATCH", *b)
    report = {"workbook": str(xlsx.name), "checked": len(formula_ids), "failed": len(bad), "worstRelative": worst,
              "changedAfterReopen": reread_diff, "mismatches": [list(map(str, b)) for b in bad]}
    pathlib.Path(sys.argv[2]).with_suffix(".excel-check.json").write_text(json.dumps(report, indent=1))
    sys.exit(1 if bad or reread_diff else 0)


if __name__ == "__main__":
    main()
