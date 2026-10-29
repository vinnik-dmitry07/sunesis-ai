"""Spike: what portable-spreadsheet 2.2.1 actually emits, before any model depends on it.

Finding: parentheses written in Python are not carried into the Excel words; fn.brackets() is required.
Builds a two-sheet toy book (arithmetic, power, IF, a cross-sheet reference, row and column labels),
exports .xlsx and the per-cell Excel words, and writes models/out/spike/spike.json for the engine check.
Run:  python -I models/spike_portable_spreadsheet.py
"""
import json
import pathlib

import portable_spreadsheet as ps

OUT = pathlib.Path(__file__).resolve().parent / "out" / "spike"
OUT.mkdir(parents=True, exist_ok=True)

inputs = ps.Sheet.create_new_sheet(3, 1, rows_labels=["Revenue", "Growth", "Margin"], columns_labels=["Value"], name="Inputs")
inputs.iloc[0, 0] = 100.0
inputs.iloc[1, 0] = 0.05
inputs.iloc[2, 0] = 0.2

calc = ps.Sheet.create_new_sheet(4, 2, rows_labels=["Revenue", "EBIT", "Compounded", "Flag"], columns_labels=["Year 1", "Year 2"], name="Calc")
rev = calc.fn.cross_reference(inputs.iloc[0, 0], inputs)
g = calc.fn.cross_reference(inputs.iloc[1, 0], inputs)
m = calc.fn.cross_reference(inputs.iloc[2, 0], inputs)
calc.iloc[0, 0] = rev * calc.fn.brackets(calc.fn.const(1) + g)
calc.iloc[0, 1] = calc.iloc[0, 0] * calc.fn.brackets(calc.fn.const(1) + g)
calc.iloc[1, 0] = calc.iloc[0, 0] * m
calc.iloc[1, 1] = calc.iloc[0, 1] * m
calc.iloc[2, 0] = calc.fn.brackets(calc.fn.const(1) + g) ** calc.fn.const(2)
calc.iloc[2, 1] = calc.iloc[0, 0] / calc.iloc[2, 0]
calc.iloc[3, 0] = calc.fn.conditional(calc.iloc[1, 0] > calc.fn.const(20), calc.fn.const(1), calc.fn.const(0))
calc.iloc[3, 1] = calc.fn.conditional(calc.iloc[1, 1] > calc.fn.const(22), calc.fn.const(1), calc.fn.const(0))

wb = ps.WorkBook(inputs, calc)
wb.to_excel(str(OUT / "spike.xlsx"), export_parameters=(ps.ExcelParameters(), ps.ExcelParameters()))

cells = {}
for sheet in (inputs, calc):
    d = sheet.to_dictionary(languages=["excel"], by_row=True)
    rows = d["table"]["data"]["rows"]
    for r_i, (rk, row) in enumerate(rows.items()):
        for c_i, (ck, cell) in enumerate(row["columns"].items()):
            cells[f"{sheet.name}|{r_i},{c_i}"] = {"value": cell["value"], "excel": cell.get("excel"), "rowLabel": rk, "colLabel": ck}
(OUT / "spike.json").write_text(json.dumps(cells, indent=1, default=str))
for k, v in cells.items():
    print(k, v)

# page-schema export for the engine and Excel checks
import sys  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib.pss import export_cells  # noqa: E402

(OUT / "spike_cells.json").write_text(json.dumps(export_cells([inputs, calc]), indent=1))
