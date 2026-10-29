"""Helpers around portable-spreadsheet 2.2.1.

- export_cells(sheets): page-schema cells ("Sheet!B2" -> {formula|value, label, dependencies, pythonValue})
  using each cell's Excel word, so the browser engine and Excel evaluate the same formula text.
- write_xlsx(sheets, path): one workbook with formulas.
Known library behaviour (see models/spike_portable_spreadsheet.py): parentheses typed in Python are not
written into the Excel word; wrap grouped terms in sheet.fn.brackets(). verify_cells.mjs catches any miss.
"""
import math
import re

import portable_spreadsheet as ps

REF = re.compile(r"(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_]*))!(\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)|(?<![A-Za-z_'!$])(\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)(?![A-Za-z_0-9(])")
ALLOWED = {"IF", "SUM", "AVERAGE", "ROUND", "EXP", "LN", "NORMSDIST", "VLOOKUP"}


def col_letter(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _deps(formula, sheet):
    deps = []
    for m in REF.finditer(formula):
        if m.group(3):
            deps.append(f"{(m.group(1) or m.group(2)).replace(chr(39) * 2, chr(39))}!{m.group(3).replace('$', '')}")
        elif m.group(4):
            deps.append(f"{sheet}!{m.group(4).replace('$', '')}")
    return sorted(set(deps))


def _functions(formula):
    return set(re.findall(r"([A-Z][A-Z0-9.]*)\(", re.sub(r"'[^']*'", "", formula)))


def export_cells(sheets, units=None):
    """Return {cell_id: cell} for the page engine. Row labels go to column A, column labels to row 1."""
    units = units or {}
    cells = {}
    for sh in sheets:
        d = sh.to_dictionary(languages=["excel"], by_row=True)
        rows = list(d["table"]["data"]["rows"].items())
        col_labels = list(rows[0][1]["columns"].keys()) if rows else []
        for c_i, cl in enumerate(col_labels):
            addr = f"{col_letter(c_i + 1)}1"
            cells[f"{sh.name}!{addr}"] = {"id": f"{sh.name}!{addr}", "sheet": sh.name, "address": addr, "value": cl, "formula": None,
                                         "classification": "label", "dependencies": [], "input": False}
        for r_i, (rl, row) in enumerate(rows):
            addr = f"A{r_i + 2}"
            cells[f"{sh.name}!{addr}"] = {"id": f"{sh.name}!{addr}", "sheet": sh.name, "address": addr, "value": rl, "formula": None,
                                         "classification": "label", "dependencies": [], "input": False}
            for c_i, (cl, cell) in enumerate(row["columns"].items()):
                word, val = cell.get("excel"), cell.get("value")
                if word is None and val is None:
                    continue
                addr = f"{col_letter(c_i + 1)}{r_i + 2}"
                cid = f"{sh.name}!{addr}"
                is_formula = isinstance(word, str) and word.startswith("=")
                if isinstance(val, float) and not math.isfinite(val):
                    raise ValueError(f"non-finite value at {cid}")
                if is_formula:
                    bad = _functions(word) - ALLOWED
                    if bad:
                        raise ValueError(f"{cid} uses functions the page engine lacks: {bad}")
                cells[cid] = {"id": cid, "sheet": sh.name, "address": addr, "value": None if is_formula else val,
                              "formula": word if is_formula else None, "pythonValue": val, "label": f"{rl} · {cl}",
                              "unit": units.get((sh.name, rl)), "classification": "derived" if is_formula else "model_input",
                              "dependencies": _deps(word, sh.name) if is_formula else [], "input": not is_formula}
    return cells


def write_xlsx(sheets, path):
    wb = ps.WorkBook(*sheets)
    wb.to_excel(str(path), export_parameters=tuple(ps.ExcelParameters() for _ in sheets))
