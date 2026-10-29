'''Export the valuation snapshots as editable portable-spreadsheet models.

The page-book graph and the Excel file are emitted from the same sheets.  The
library evaluates expressions in Python; its cached results are not evidence of
a fresh calculation by Microsoft Excel.
'''

from __future__ import annotations

import json
import math
import re
import textwrap
import zipfile
from pathlib import Path
from typing import Any

import portable_spreadsheet as ps


INPUT_KEYS = [
    ('revenue', 'Revenue FY2025 / USD m'),
    ('reportedEbit', 'Reported EBIT FY2025 / USD m'),
    ('bookEquity', 'Adjusted book equity / USD m'),
    ('debt', 'Interest-bearing debt / USD m'),
    ('cash', 'Cash / USD m'),
    ('nonoperatingAssets', 'Nonoperating assets / USD m'),
    ('minorityInterests', 'Minority interests / USD m'),
    ('shares', 'Valuation dilution proxy / million shares'),
    ('price', 'Historical reference price / USD per share'),
    ('taxRate', 'Normalized starting tax rate'),
    ('terminalTaxRate', 'Terminal tax rate'),
    ('growth1', 'Revenue growth year 1'),
    ('growth2to5', 'Revenue growth years 2-5'),
    ('margin1', 'Adjusted EBIT margin year 1'),
    ('targetMargin', 'Target adjusted EBIT margin'),
    ('marginConvergenceYear', 'Margin convergence year'),
    ('salesToCapital1', 'Sales to capital years 1-5'),
    ('salesToCapital2', 'Sales to capital years 6-10'),
    ('waccInitial', 'WACC years 1-5'),
    ('waccTerminal', 'Terminal WACC'),
    ('terminalGrowth', 'Terminal growth'),
    ('terminalExcessReturns', 'Use explicit terminal ROIC / 1=yes'),
    ('terminalRoic', 'Explicit terminal ROIC'),
    ('rdCurrent', 'Current R&D / USD m'),
    ('rdLife', 'R&D amortization life / years'),
    ('capitalizeRd', 'Capitalize R&D / 1=yes'),
    ('initialNol', 'Starting NOL / USD m'),
    ('holdTaxRate', 'Hold starting tax rate / 1=yes'),
    ('lagOverride', 'Override reinvestment timing / 1=yes'),
    ('lagYears', 'Reinvestment growth lead / years'),
    ('failureProbability', 'Distress probability'),
    ('failureRecovery', 'Distress recovery fraction'),
    ('failureBookBasis', 'Use book-value distress basis / 1=yes'),
    ('trappedCash', 'Trapped overseas cash / USD m'),
    ('overseasTaxRate', 'Overseas tax rate'),
    ('cashHaircut', 'Apply trapped-cash tax / 1=yes'),
]

DCF_ROWS = [
    'Year', 'Revenue growth', 'Revenue / USD m', 'Adjusted EBIT margin',
    'Adjusted EBIT / USD m', 'Tax rate', 'Opening NOL / USD m',
    'NOPAT / USD m', 'Reinvestment / USD m', 'FCFF / USD m',
    'Closing NOL / USD m', 'WACC', 'Cumulative discount factor',
    'PV FCFF / USD m', 'Opening invested capital / USD m',
    'Closing invested capital / USD m', 'Economic profit / USD m',
    'PV economic profit / USD m', 'Sales to capital',
    'Terminal value / USD m', 'PV terminal value / USD m',
    'PV forecast FCFF / USD m', 'Undistressed operating value / USD m',
    'Distress proceeds / USD m', 'Operating value / USD m',
    'Equity value / USD m', 'Value per share / USD', 'Terminal value share',
    'Terminal reinvestment rate', 'EVA recurring terminal value / USD m',
    'EVA terminal capital transition / USD m',
    'EVA terminal value / USD m', 'EVA operating value / USD m',
    'EVA minus DCF / USD m',
]


def _native(value: Any) -> Any:
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('A non-finite result cannot be exported.')
    return value


def _literal(sheet: ps.Sheet, value: Any) -> ps.Cell:
    return ps.Cell(None, None, value=value, cell_indices=sheet.cell_indices)


def _b(cell: ps.Cell) -> ps.Cell:
    # The portable-spreadsheet library does not insert precedence parentheses.
    return ps.Cell.brackets(cell)


def _if(sheet: ps.Sheet, condition: ps.Cell, yes: ps.Cell,
        no: ps.Cell) -> ps.Cell:
    return sheet.fn.conditional(condition, yes, no)


def _cross(sheet: ps.Sheet, target: ps.Sheet, row: int,
           col: int = 0) -> ps.Cell:
    return (sheet.fn.cross_reference(target.iloc[row, col], target)
            + _literal(sheet, 0))


def _new_sheet(name: str, labels: list[str], columns: list[str]) -> ps.Sheet:
    return ps.Sheet.create_new_sheet(
        len(labels), len(columns), name=name, rows_labels=labels,
        columns_labels=columns,
    )


def _number_format(cell: ps.Cell, percentage: bool = False,
                   output: bool = False, input_cell: bool = False) -> None:
    cell.excel_format = {
        'num_format': '0.0%' if percentage else '#,##0.000;[Red](#,##0.000);–',
        'font_color': '#0000FF' if input_cell else '#29332C',
        'bg_color': ('#DCE5D7' if output else
                     '#F2F6FB' if input_cell else '#FFFFFF'),
        'bold': output,
    }


def _inputs_sheet(result: dict[str, Any],
                  suffix: str) -> tuple[ps.Sheet, dict]:
    inputs = result['inputs']
    rows = INPUT_KEYS + [
        (f'rdHistory{i + 1}', f'R&D {i + 1} years prior / USD m')
        for i in range(4)
    ] + [
        ('rdAmortization', 'R&D amortization / USD m'),
        ('rdAsset', 'Unamortized R&D asset / USD m'),
        ('adjustedEbit', 'R&D-adjusted base EBIT / USD m'),
        ('openingCapital', 'Base invested capital / USD m'),
        ('effectiveTerminalTax', 'Effective terminal tax rate'),
        ('effectiveTerminalRoic', 'Effective terminal ROIC'),
        ('effectiveCash', 'Cash after explicit haircut / USD m'),
    ]
    index = {key: row for row, (key, _) in enumerate(rows)}
    sheet = _new_sheet(
        f'WD40_Inputs_{suffix}', [label for _, label in rows], ['Value'],
    )
    defaults = {
        'nonoperatingAssets': 0, 'minorityInterests': 0,
        'initialNol': 0, 'holdTaxRate': False, 'lagOverride': False,
        'lagYears': 1, 'failureProbability': 0, 'failureRecovery': 0.5,
        'failureBookBasis': False, 'trappedCash': 0, 'overseasTaxRate': 0,
        'cashHaircut': False,
    }
    percentage_keys = {
        'taxRate', 'terminalTaxRate', 'growth1', 'growth2to5', 'margin1',
        'targetMargin', 'waccInitial', 'waccTerminal', 'terminalGrowth',
        'terminalRoic', 'failureProbability', 'failureRecovery',
        'overseasTaxRate',
    }
    for key, _ in INPUT_KEYS:
        value = inputs.get(key, defaults.get(key))
        if value is None:
            raise ValueError(f'Missing required workbook input: {key}')
        if isinstance(value, bool):
            value = int(value)
        sheet.iloc[index[key], 0] = value
        _number_format(sheet.iloc[index[key], 0], key in percentage_keys,
                       input_cell=True)

    history = inputs.get('rdHistory', [])
    for i in range(4):
        key = f'rdHistory{i + 1}'
        sheet.iloc[index[key], 0] = history[i] if i < len(history) else 0
        _number_format(sheet.iloc[index[key], 0], input_cell=True)

    def v(key: str) -> ps.Cell:
        return sheet.iloc[index[key], 0]

    zero, one = _literal(sheet, 0), _literal(sheet, 1)
    amort = zero
    rd_asset = v('rdCurrent')
    for i in range(1, 5):
        age = _literal(sheet, i)
        expense = v(f'rdHistory{i}')
        amort = amort + _if(
            sheet, age <= v('rdLife'), _b(expense / v('rdLife')), zero,
        )
        rd_asset = rd_asset + _if(
            sheet, age < v('rdLife'),
            _b(expense * _b(_b(v('rdLife') - age) / v('rdLife'))), zero,
        )
    sheet.iloc[index['rdAmortization'], 0] = amort
    sheet.iloc[index['rdAsset'], 0] = rd_asset
    sheet.iloc[index['adjustedEbit'], 0] = v('reportedEbit') + _if(
        sheet, v('capitalizeRd') == one,
        _b(v('rdCurrent') - v('rdAmortization')), zero,
    )
    sheet.iloc[index['openingCapital'], 0] = (
        v('bookEquity') + v('debt') - v('cash') + _if(
            sheet, v('capitalizeRd') == one, v('rdAsset'), zero,
        )
    )
    sheet.iloc[index['effectiveTerminalTax'], 0] = _if(
        sheet, v('holdTaxRate') == one, v('taxRate'), v('terminalTaxRate'),
    )
    sheet.iloc[index['effectiveTerminalRoic'], 0] = _if(
        sheet, v('terminalExcessReturns') == one,
        v('terminalRoic'), v('waccTerminal'),
    )
    sheet.iloc[index['effectiveCash'], 0] = v('cash') - _if(
        sheet, v('cashHaircut') == one,
        _b(v('trappedCash') * _b(v('terminalTaxRate') - v('overseasTaxRate'))),
        zero,
    )
    if inputs.get('margin1FromAdjusted', False):
        sheet.iloc[index['margin1'], 0] = v('adjustedEbit') / v('revenue')
    if inputs.get('targetMarginFromMargin1', False):
        sheet.iloc[index['targetMargin'], 0] = v('margin1') + zero
    if inputs.get('growth2FromGrowth1', False):
        sheet.iloc[index['growth2to5'], 0] = v('growth1') + zero
    if inputs.get('salesToCapital2From1', False):
        sheet.iloc[index['salesToCapital2'], 0] = v('salesToCapital1') + zero
    return sheet, index


def _segments_sheet(result: dict, suffix: str, inputs_sheet: ps.Sheet,
                    input_index: dict) -> tuple[ps.Sheet, dict] | None:
    build = result.get('segmentBuild')
    if not build:
        return None
    regions = list(build['baseRegions'])
    rows = [
        ('base', 'Reported FY2025 revenue / USD m'),
        ('removed', 'Explicit divestment revenue removal / USD m'),
        ('remaining', 'Revenue after removal / USD m'),
        ('growth', 'Analyst regional growth years 1-5'),
        ('terminalGrowth', 'Terminal growth'),
    ]
    for year in range(1, 11):
        rows.extend([
            (f'growth{year}', f'Y{year} revenue growth'),
            (f'revenue{year}', f'Y{year} regional revenue / USD m'),
            (f'ginzu{year}', f'Y{year} compressed Ginzu revenue / USD m'),
            (f'residual{year}',
             f'Y{year} Ginzu minus regional revenue / USD m'),
        ])
    rows.extend([
        ('growth1Output', 'Consolidated year-one growth'),
        ('cagrOutput', 'Year-one to year-five revenue CAGR'),
        ('basis', 'Basis and compression interpretation'),
    ])
    sheet = _new_sheet(
        f'WD40_Regions_{suffix}', [label for _, label in rows],
        regions + ['Consolidated'],
    )
    index = {key: row for row, (key, _) in enumerate(rows)}
    zero, one, five = (_literal(sheet, n) for n in (0, 1, 5))
    total_col = len(regions)
    for col, region in enumerate(regions):
        sheet.iloc[index['base'], col] = build['baseRegions'][region]
        sheet.iloc[index['removed'], col] = (
            build.get('divestmentRevenueByRegion', {}).get(region, 0)
        )
        sheet.iloc[index['remaining'], col] = (
            sheet.iloc[index['base'], col] - sheet.iloc[index['removed'], col]
        )
        sheet.iloc[index['growth'], col] = (
            build['regionGrowthAssumptions'][region]
        )
        sheet.iloc[index['terminalGrowth'], col] = _cross(
            sheet, inputs_sheet, input_index['terminalGrowth'],
        )
        for key in ('base', 'removed', 'growth'):
            _number_format(sheet.iloc[index[key], col], key == 'growth',
                           input_cell=True)
        for year in range(1, 11):
            rate = sheet.iloc[index['growth'], col]
            if year > 5:
                rate = rate - _b(
                    _b(_b(rate - sheet.iloc[index['terminalGrowth'], col])
                       / five) * _literal(sheet, year - 5)
                )
            sheet.iloc[index[f'growth{year}'], col] = rate + zero
            previous = (sheet.iloc[index['remaining'], col] if year == 1
                        else sheet.iloc[index[f'revenue{year - 1}'], col])
            sheet.iloc[index[f'revenue{year}'], col] = (
                previous * _b(one + sheet.iloc[index[f'growth{year}'], col])
            )
    for key in ('base', 'removed', 'remaining'):
        sheet.iloc[index[key], total_col] = (
            sheet.iloc[index[key], :total_col].sum()
        )
    for year in range(1, 11):
        sheet.iloc[index[f'revenue{year}'], total_col] = (
            sheet.iloc[index[f'revenue{year}'], :total_col].sum()
        )
        previous = (sheet.iloc[index['base'], total_col] if year == 1
                    else sheet.iloc[index[f'revenue{year - 1}'], total_col])
        sheet.iloc[index[f'growth{year}'], total_col] = (
            _b(sheet.iloc[index[f'revenue{year}'], total_col] / previous) - one
        )
    sheet.iloc[index['growth1Output'], total_col] = (
        sheet.iloc[index['growth1'], total_col] + zero
    )
    sheet.iloc[index['cagrOutput'], total_col] = (
        _b(sheet.iloc[index['revenue5'], total_col]
           / sheet.iloc[index['revenue1'], total_col]) ** _literal(sheet, 0.25)
    ) - one
    sheet.iloc[index['basis'], 0] = (
        'Reported regional base; analyst growth and constant FX. '
        'Two Ginzu growth inputs preserve Y1/Y5 endpoints; other years differ.'
    )
    inputs_sheet.iloc[input_index['revenue'], 0] = _cross(
        inputs_sheet, sheet, index['base'], total_col,
    )
    inputs_sheet.iloc[input_index['growth1'], 0] = _cross(
        inputs_sheet, sheet, index['growth1Output'], total_col,
    )
    inputs_sheet.iloc[input_index['growth2to5'], 0] = _cross(
        inputs_sheet, sheet, index['cagrOutput'], total_col,
    )
    return sheet, index


def _segment_residuals(regional: tuple[ps.Sheet, dict], dcf: ps.Sheet) -> None:
    sheet, index = regional
    total_col = len(sheet.to_dictionary()['table']['columns']) - 1
    for year in range(1, 11):
        sheet.iloc[index[f'ginzu{year}'], total_col] = _cross(
            sheet, dcf, 2, year,
        )
        sheet.iloc[index[f'residual{year}'], total_col] = (
            sheet.iloc[index[f'ginzu{year}'], total_col]
            - sheet.iloc[index[f'revenue{year}'], total_col]
        )


def _dcf_sheet(result: dict[str, Any], suffix: str, inputs_sheet: ps.Sheet,
               input_index: dict[str, int]) -> ps.Sheet:
    sheet = _new_sheet(
        f'WD40_DCF_{suffix}', DCF_ROWS,
        ['Base'] + [f'Y{i}' for i in range(1, 11)] + ['Terminal'],
    )
    zero, one, five = (_literal(sheet, n) for n in (0, 1, 5))

    def v(key: str) -> ps.Cell:
        return _cross(sheet, inputs_sheet, input_index[key])

    sheet.iloc[0, 0] = 0
    sheet.iloc[2, 0] = v('revenue')
    sheet.iloc[4, 0] = v('adjustedEbit')
    sheet.iloc[3, 0] = sheet.iloc[4, 0] / sheet.iloc[2, 0]
    sheet.iloc[5, 0] = v('taxRate')
    sheet.iloc[7, 0] = _if(
        sheet, sheet.iloc[4, 0] > zero,
        _b(sheet.iloc[4, 0] * _b(one - sheet.iloc[5, 0])), sheet.iloc[4, 0],
    )
    sheet.iloc[10, 0] = v('initialNol')
    sheet.iloc[15, 0] = v('openingCapital')

    # Set growth, sales, margins, tax and discount rates before reinvestment.
    for year in range(1, 12):
        c = year
        sheet.iloc[0, c] = year
        if year == 1:
            growth = v('growth1')
        elif year <= 5:
            growth = v('growth2to5')
        elif year <= 10:
            growth = v('growth2to5') - _b(
                _b(_b(v('growth2to5') - v('terminalGrowth')) / five)
                * _literal(sheet, year - 5)
            )
        else:
            growth = v('terminalGrowth')
        sheet.iloc[1, c] = growth
        sheet.iloc[2, c] = sheet.iloc[2, c - 1] * _b(one + sheet.iloc[1, c])
        if year == 1:
            margin = v('margin1')
        elif year == 11:
            margin = sheet.iloc[3, 10]
        else:
            margin = _if(
                sheet, _literal(sheet, year) > v('marginConvergenceYear'),
                v('targetMargin'),
                v('targetMargin') - _b(
                    _b(_b(v('targetMargin') - v('margin1'))
                       / v('marginConvergenceYear'))
                    * _b(v('marginConvergenceYear') - _literal(sheet, year))
                ),
            )
        sheet.iloc[3, c] = margin
        sheet.iloc[4, c] = sheet.iloc[3, c] * sheet.iloc[2, c]
        if year <= 5:
            tax_rate = v('taxRate')
        elif year <= 10:
            tax_rate = sheet.iloc[5, c - 1] + _b(
                _b(v('effectiveTerminalTax') - v('taxRate')) / five
            )
        else:
            tax_rate = v('effectiveTerminalTax')
        sheet.iloc[5, c] = tax_rate
        sheet.iloc[6, c] = sheet.iloc[10, c - 1]
        if year == 11:
            nopat = sheet.iloc[4, c] * _b(one - sheet.iloc[5, c])
        else:
            nopat = _if(
                sheet, sheet.iloc[4, c] > zero,
                _if(
                    sheet, sheet.iloc[4, c] < sheet.iloc[6, c],
                    sheet.iloc[4, c],
                    sheet.iloc[4, c] - _b(
                        _b(sheet.iloc[4, c] - sheet.iloc[6, c])
                        * sheet.iloc[5, c]
                    ),
                ), sheet.iloc[4, c],
            )
        sheet.iloc[7, c] = nopat
        sheet.iloc[10, c] = _if(
            sheet, sheet.iloc[4, c] < zero,
            _b(sheet.iloc[6, c] - sheet.iloc[4, c]),
            _if(sheet, sheet.iloc[6, c] > sheet.iloc[4, c],
                _b(sheet.iloc[6, c] - sheet.iloc[4, c]), zero),
        )
        if year <= 5:
            wacc = v('waccInitial')
        elif year <= 10:
            wacc = sheet.iloc[11, c - 1] - _b(
                _b(v('waccInitial') - v('waccTerminal')) / five
            )
        else:
            wacc = v('waccTerminal')
        sheet.iloc[11, c] = wacc
        if year <= 10:
            previous_discount = one if year == 1 else sheet.iloc[12, c - 1]
            sheet.iloc[12, c] = previous_discount * _b(
                one / _b(one + sheet.iloc[11, c])
            )
            sheet.iloc[18, c] = v(
                'salesToCapital1' if year <= 5 else 'salesToCapital2'
            )

    def revenue_delta(year: int, lead: int) -> ps.Cell:
        if year + lead <= 11:
            return _b(sheet.iloc[2, year + lead]
                      - sheet.iloc[2, year + lead - 1])
        if year + lead == 12:
            return _b(sheet.iloc[2, 11] * sheet.iloc[1, 11])
        # Ginzu uses K8*(1+terminal growth) for the Y10/lead3 branch.
        return _b(sheet.iloc[8, 9] * _b(one + sheet.iloc[1, 11])
                  * sheet.iloc[18, year])

    for year in range(1, 11):
        default = _b(revenue_delta(year, 1) / sheet.iloc[18, year])
        lagged = _if(
            sheet, v('lagYears') == zero,
            _b(revenue_delta(year, 0) / sheet.iloc[18, year]),
            _if(
                sheet, v('lagYears') == _literal(sheet, 2),
                _b(revenue_delta(year, 2) / sheet.iloc[18, year]),
                _if(
                    sheet, v('lagYears') == _literal(sheet, 3),
                    _b(revenue_delta(year, 3) / sheet.iloc[18, year]), default,
                ),
            ),
        )
        sheet.iloc[8, year] = _if(
            sheet, v('lagOverride') == one, lagged, default,
        )
        sheet.iloc[9, year] = sheet.iloc[7, year] - sheet.iloc[8, year]
        sheet.iloc[13, year] = sheet.iloc[9, year] * sheet.iloc[12, year]
        sheet.iloc[14, year] = sheet.iloc[15, year - 1]
        sheet.iloc[15, year] = sheet.iloc[14, year] + sheet.iloc[8, year]
        sheet.iloc[16, year] = sheet.iloc[7, year] - _b(
            sheet.iloc[11, year] * sheet.iloc[14, year]
        )
        sheet.iloc[17, year] = sheet.iloc[16, year] * sheet.iloc[12, year]

    terminal_roic = v('effectiveTerminalRoic')
    # Ginzu's default uses L12 (the actually faded year-10 WACC).
    terminal_roic = _if(sheet, v('terminalExcessReturns') == one,
                        v('terminalRoic'), sheet.iloc[11, 10])
    sheet.iloc[28, 0] = _if(sheet, sheet.iloc[1, 11] > zero,
                           _b(sheet.iloc[1, 11] / terminal_roic), zero)
    sheet.iloc[8, 11] = sheet.iloc[28, 0] * sheet.iloc[7, 11]
    sheet.iloc[9, 11] = sheet.iloc[7, 11] - sheet.iloc[8, 11]
    sheet.iloc[19, 0] = sheet.iloc[9, 11] / _b(
        sheet.iloc[11, 11] - sheet.iloc[1, 11]
    )
    sheet.iloc[20, 0] = sheet.iloc[19, 0] * sheet.iloc[12, 10]
    sheet.iloc[21, 0] = sheet.iloc[13, 1:11].sum()
    sheet.iloc[22, 0] = sheet.iloc[20, 0] + sheet.iloc[21, 0]
    sheet.iloc[23, 0] = _if(
        sheet, v('failureBookBasis') == one,
        _b(_b(v('bookEquity') + v('debt')) * v('failureRecovery')),
        _b(sheet.iloc[22, 0] * v('failureRecovery')),
    )
    sheet.iloc[24, 0] = _b(
        sheet.iloc[22, 0] * _b(one - v('failureProbability'))
    ) + _b(sheet.iloc[23, 0] * v('failureProbability'))
    sheet.iloc[25, 0] = (
        sheet.iloc[24, 0] - v('debt') - v('minorityInterests')
        + v('effectiveCash') + v('nonoperatingAssets')
    )
    price_value = sheet.iloc[25, 0] / v('shares')
    guards = [
        (v('waccTerminal') > v('terminalGrowth'),
         'Blocked: terminal WACC must exceed growth'),
        (v('waccInitial') > zero, 'Blocked: starting WACC must be positive'),
        (v('shares') > zero, 'Blocked: shares must be positive'),
        (v('salesToCapital1') > zero,
         'Blocked: years 1-5 sales to capital must be positive'),
        (v('salesToCapital2') > zero,
         'Blocked: years 6-10 sales to capital must be positive'),
        (_if(sheet, v('terminalExcessReturns') == one,
             _if(sheet, v('terminalRoic') > zero, one, zero), one) == one,
         'Blocked: active terminal ROIC must be positive'),
        (_if(sheet, v('terminalExcessReturns') == one,
             _if(sheet, v('terminalRoic') >= v('terminalGrowth'), one, zero),
             one) == one,
         'Blocked: terminal reinvestment exceeds NOPAT'),
    ]
    for condition, message in reversed(guards):
        price_value = _if(sheet, condition, price_value,
                          _literal(sheet, message))
    sheet.iloc[26, 0] = price_value
    sheet.iloc[27, 0] = sheet.iloc[20, 0] / sheet.iloc[22, 0]

    # Sum future economic profit independently using its geometric series.
    # For g>0, capital grows by g*NOPAT/ROIC each year.  Its recurring EP
    # and the initial terminal capital mismatch have separate closed forms.
    # This is not a plug set to DCF minus invested capital.
    term_nopat = sheet.iloc[7, 11]
    term_wacc = sheet.iloc[11, 11]
    term_growth = sheet.iloc[1, 11]
    sheet.iloc[29, 0] = _if(
        sheet, term_growth > zero,
        _b(_b(term_nopat * _b(one - _b(term_wacc / terminal_roic)))
           / _b(term_wacc - term_growth)),
        _b(term_nopat / _b(term_wacc - term_growth)),
    )
    sheet.iloc[30, 0] = _if(
        sheet, term_growth > zero,
        _b(_b(term_nopat / terminal_roic) - sheet.iloc[15, 10]),
        _b(zero - sheet.iloc[15, 10]),
    )
    sheet.iloc[31, 0] = sheet.iloc[29, 0] + sheet.iloc[30, 0]
    sheet.iloc[32, 0] = (
        sheet.iloc[15, 0] + sheet.iloc[17, 1:11].sum()
        + _b(sheet.iloc[31, 0] * sheet.iloc[12, 10])
    )
    sheet.iloc[33, 0] = sheet.iloc[32, 0] - sheet.iloc[22, 0]
    for row in range(len(DCF_ROWS)):
        for col in range(12):
            if sheet.iloc[row, col].value is not None:
                _number_format(sheet.iloc[row, col],
                               row in {1, 3, 5, 11, 27, 28},
                               output=row in {24, 25, 26, 33})
    return sheet


def _col_name(number: int) -> str:
    result = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _dependencies(formula: str, sheet: str) -> list[str]:
    formula = re.sub(r'"(?:[^"]|"")*"', '', formula)
    pattern = re.compile(
        r'''(?:(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_]*))!)?'''
        r'(\$?[A-Za-z]{1,3}\$?\d+)(?::(\$?[A-Za-z]{1,3}\$?\d+))?'
    )
    found = []
    for match in pattern.finditer(formula):
        quote = chr(39)
        target_sheet = (match[1] or match[2] or sheet).replace(
            quote * 2, quote,
        )
        address = match[3].replace('$', '').upper()
        if match[4]:
            address += ':' + match[4].replace('$', '').upper()
        found.append(f'{target_sheet}!{address}')
    return list(dict.fromkeys(found))


def _page_book(sheet: ps.Sheet) -> dict[str, Any]:
    name = sheet.name
    table = sheet.to_dictionary()['table']
    rows = table['rows']
    columns = table['columns']
    cells = {}
    for row_index, row_meta in enumerate(rows):
        row_label = row_meta['name']
        label_address = f'A{row_index + 2}'
        label_id = f'{name}!{label_address}'
        cells[label_id] = {
            'id': label_id, 'sheet': name, 'address': label_address,
            'value': row_label, 'label': row_label, 'dependencies': [],
            'classification': 'reference_label',
        }
        for col_index, col_meta in enumerate(columns):
            col_label = col_meta['name']
            source = table['data']['rows'][row_label]['columns'][col_label]
            value = _native(source['value'])
            word = source.get('excel', '')
            if value is None and not word:
                continue
            address = f'{_col_name(col_index + 2)}{row_index + 2}'
            cell_id = f'{name}!{address}'
            formula = word if word.startswith('=') else None
            c = {
                'id': cell_id, 'sheet': name, 'address': address,
                'value': None if formula else value,
                'cachedValue': value, 'label': f'{row_label} · {col_label}',
                'dependencies': (_dependencies(formula, name)
                                 if formula else []),
                'classification': 'derived' if formula else 'snapshot_input',
            }
            if formula:
                c['formula'] = formula
            cells[cell_id] = c
    for col_index, col_meta in enumerate(columns):
        address = f'{_col_name(col_index + 2)}1'
        cell_id = f'{name}!{address}'
        cells[cell_id] = {
            'id': cell_id, 'sheet': name, 'address': address,
            'value': col_meta['name'], 'label': col_meta['name'],
            'dependencies': [], 'classification': 'reference_label',
        }
    return {'name': name, 'cells': cells}


def _summary(results: list[dict[str, Any]],
             dcf_sheets: list[ps.Sheet]) -> ps.Sheet:
    sheet = _new_sheet(
        'WD40_Summary',
        ['DCF value / USD per share', 'Operating value / USD m',
         'Equity value / USD m', 'PV terminal value / USD m',
         'Terminal value share', 'Historical reference / USD per share',
         'DCF / historical reference minus 1', 'EVA minus DCF / USD m',
         'Scenario input hash', 'Scenario classification',
         'Financial basis', 'Price date', 'Excel calculation status'],
        [str(r.get('label', r.get('id', i))) for i, r in enumerate(results)],
    )
    for col, (result, target) in enumerate(zip(results, dcf_sheets)):
        for row, target_row in enumerate([26, 24, 25, 20, 27]):
            sheet.iloc[row, col] = _cross(sheet, target, target_row)
            _number_format(sheet.iloc[row, col], row == 4, output=row == 0)
        sheet.iloc[5, col] = result['inputs']['price']
        sheet.iloc[6, col] = (
            _b(sheet.iloc[0, col] / sheet.iloc[5, col]) - _literal(sheet, 1)
        )
        _number_format(sheet.iloc[6, col], percentage=True)
        sheet.iloc[7, col] = _cross(sheet, target, 33)
        sheet.iloc[8, col] = result.get(
            'inputHash', result.get('snapshotId', ''),
        )
        sheet.iloc[9, col] = result.get(
            'kind', 'Analyst scenario; not a probability interval',
        )
        sheet.iloc[10, col] = (
            'FY2025 retrospective; later filings with historical price'
        )
        sheet.iloc[11, col] = '2025-08-29'
        sheet.iloc[12, col] = (
            'Python/browser verification; native Excel calculation pending'
        )
    return sheet


def _notes_sheet(results: list[dict[str, Any]], methods: list[dict[str, Any]],
                 questions: dict[str, Any]) -> ps.Sheet:
    notes = [
        ('Purpose', 'Inspect editable assumptions and formulas behind the '
         'WD-40 retrospective demo.'),
        ('Financial units', 'USD millions, except USD per share; '
         'shares are in millions.'),
        ('Price basis', 'Historical 2025-08-29 reference; '
         'FY2025 results were published later.'),
        ('Share count', 'DCF denominator includes an explicit dilution proxy; '
         'it is not asserted as historical market shares outstanding.'),
        ('Scenario interpretation', 'Named analyst scenarios are fixed '
         'snapshots, not statistical confidence intervals.'),
        ('Reinvestment timing', 'Ginzu default uses next-year revenue '
         'increase, not same-year revenue increase.'),
        ('R&D adjustment', 'Adjusted EBIT adds current R&D and subtracts '
         'amortization of capitalized historical R&D.'),
        ('EVA terminal', 'Recurring economic profit and terminal capital '
         'transition follow the same NOPAT and reinvestment paths.'),
        ('EVA interpretation', 'EVA is an algebraic consistency check of DCF, '
         'not independent valuation evidence.'),
        ('Excel verification', 'Formulas and Python cached values are '
         'exported; native Microsoft Excel calculation is pending.'),
    ]
    for method in methods:
        method_id = method.get('id', len(notes))
        label = method.get('label', '')
        status = method.get('status', 'unknown')
        notes.append((f'Method {method_id}', f'{label}: {status}. '
                      + ' '.join(method.get('limitations', []))))
    for i, source in enumerate(questions.get('sources', [])):
        title = source.get('title', source.get('id', ''))
        url = source.get('url', '')
        notes.append((f'Question source {i + 1}',
                      f'{title} · {url}'))
    sheet = _new_sheet('WD40_Basis', [name for name, _ in notes], ['Record'])
    for row, (_, text) in enumerate(notes):
        sheet.iloc[row, 0] = text
    return sheet


def _questions_sheet(questions: dict[str, Any]) -> ps.Sheet | None:
    records = questions.get('questions', [])
    if not records:
        return None
    columns = [
        'Question', 'Category', 'Status', 'Benchmark', 'Original record',
        'Original question', 'WD40 answer or resolution', 'Evidence cells',
        'Source IDs',
    ]
    sheet = _new_sheet('WD40_Questions', [r['id'] for r in records], columns)
    for row, item in enumerate(records):
        benchmark = item.get('benchmark') or {}
        answer = item.get('answer')
        if answer is None:
            answer = item.get('note') or item.get('resolution') or ''
        if not isinstance(answer, str):
            answer = json.dumps(answer, ensure_ascii=False, sort_keys=True)
        values = [
            item.get('question', ''), item.get('category', ''),
            item.get('status', ''),
            benchmark.get('name', ''), str(benchmark.get('recordId', '')),
            benchmark.get('originalQuestion', ''), answer,
            ', '.join(item.get('cellIds', [])),
            ', '.join(item.get('sourceIds', [])),
        ]
        for col, value in enumerate(values):
            sheet.iloc[row, col] = value
    return sheet


def _sources_sheet(results: list[dict], questions: dict) -> ps.Sheet | None:
    sources = {}
    for result in results:
        for source in result['inputs'].get('sources', []):
            sources[source['id']] = source
    for source in questions.get('sources', []):
        sources[source['id']] = source
    path = Path(__file__).parent / 'data' / 'sources.json'
    if path.exists():
        for source in json.loads(path.read_text()).get('sources', []):
            sources[source['id']] = source
    if not sources:
        return None
    rows = sorted(sources)
    sheet = _new_sheet(
        'WD40_Sources', rows,
        ['Title', 'URL', 'As of', 'Published', 'Locator', 'Summary / scope'],
    )
    for row, source_id in enumerate(rows):
        source = sources[source_id]
        values = [
            source.get('title', source_id), source.get('url', ''),
            source.get('asOf', ''), source.get('publishedAt', ''),
            source.get('locator', ''),
            source.get('summary', source.get('scope', '')),
        ]
        for col, value in enumerate(values):
            sheet.iloc[row, col] = str(value) if value is not None else ''
    return sheet


def _parameter_sheet(name: str, rows: list[tuple[str, str]],
                     scenarios: list[dict[str, Any]]) -> tuple[ps.Sheet, dict]:
    sheet = _new_sheet(
        name, [label for _, label in rows],
        [case.get('label', case['id']) for case in scenarios],
    )
    return sheet, {key: row for row, (key, _) in enumerate(rows)}


def _put_parameter(sheet: ps.Sheet, index: dict, key: str, col: int,
                   value: Any, percentage: bool = False) -> None:
    sheet.iloc[index[key], col] = value
    _number_format(sheet.iloc[index[key], col], percentage, input_cell=True)


def _method_check(sheet: ps.Sheet, index: dict, scenarios: list,
                  output_key: str = 'value') -> None:
    for col, case in enumerate(scenarios):
        expected = case.get('value')
        actual = sheet.iloc[index[output_key], col].value
        if expected is not None and not math.isclose(
                float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-7):
            case_id = case['id']
            raise ValueError(
                f'{sheet.name} {case_id} mismatch: {actual} != {expected}'
            )


def _ddm_sheet(method: dict, dcf: ps.Sheet, inputs: ps.Sheet,
               input_index: dict, result: dict) -> tuple[ps.Sheet, int]:
    cases = method['scenarios']
    rows = [
        ('dividend0', 'Annualized starting dividend / USD per share'),
        ('growth', 'Stage-one dividend growth'),
        ('terminalGrowth', 'Terminal dividend growth'),
        ('costOfEquity', 'Cost of equity / analyst assumption'),
        ('years', 'Stage-one horizon / years'),
        ('shares', 'Valuation dilution proxy / million shares'),
        ('interest', 'Historical interest expense / USD m'),
    ]
    for year in range(1, 11):
        rows.extend([
            (f'dividend{year}', f'Y{year} dividend / USD per share'),
            (f'discount{year}', f'Y{year} discount factor'),
            (f'pv{year}', f'Y{year} PV dividend / USD per share'),
            (f'fcfe{year}', f'Y{year} constant-debt FCFE proxy / USD m'),
            (f'total{year}', f'Y{year} total dividends / USD m'),
            (f'covered{year}', f'Y{year} payout covered / 1=yes'),
        ])
    rows.extend([
        ('terminalDividend', 'Terminal dividend / USD per share'),
        ('terminalValue', 'Terminal value / USD per share'),
        ('pvTerminal', 'PV terminal value / USD per share'),
        ('value', 'DDM value / USD per share'),
        ('coveredYears', 'Covered years / count'),
    ])
    sheet, index = _parameter_sheet('WD40_DDM', rows, cases)
    zero, one = (_literal(sheet, n) for n in (0, 1))
    interest = result['inputs'].get('overrides', {}).get(
        'Input sheet!B13', 3.441,
    )
    for col, case in enumerate(cases):
        assumptions = case['assumptions']
        for key in ('dividend0', 'growth', 'terminalGrowth', 'costOfEquity',
                    'years'):
            _put_parameter(sheet, index, key, col, assumptions[key],
                           key in {'growth', 'terminalGrowth', 'costOfEquity'})
        sheet.iloc[index['shares'], col] = _cross(
            sheet, inputs, input_index['shares'],
        )
        _put_parameter(sheet, index, 'interest', col, interest)

        def v(key: str) -> ps.Cell:
            return sheet.iloc[index[key], col]

        pv_sum, covered_sum = zero, zero
        for year in range(1, 11):
            exponent = _literal(sheet, year)
            sheet.iloc[index[f'dividend{year}'], col] = (
                v('dividend0') * _b(_b(one + v('growth')) ** exponent)
            )
            sheet.iloc[index[f'discount{year}'], col] = (
                one / _b(_b(one + v('costOfEquity')) ** exponent)
            )
            sheet.iloc[index[f'pv{year}'], col] = (
                v(f'dividend{year}') * v(f'discount{year}')
            )
            sheet.iloc[index[f'fcfe{year}'], col] = (
                _cross(sheet, dcf, 9, year)
                - _b(v('interest') * _b(
                    one - _cross(sheet, dcf, 5, year)
                ))
            )
            sheet.iloc[index[f'total{year}'], col] = (
                v(f'dividend{year}') * v('shares')
            )
            sheet.iloc[index[f'covered{year}'], col] = _if(
                sheet, v(f'total{year}') <= v(f'fcfe{year}'), one, zero,
            )
            pv_sum = pv_sum + v(f'pv{year}')
            covered_sum = covered_sum + v(f'covered{year}')
        sheet.iloc[index['terminalDividend'], col] = (
            v('dividend10') * _b(one + v('terminalGrowth'))
        )
        sheet.iloc[index['terminalValue'], col] = (
            v('terminalDividend')
            / _b(v('costOfEquity') - v('terminalGrowth'))
        )
        sheet.iloc[index['pvTerminal'], col] = (
            v('terminalValue') * v('discount10')
        )
        calculated_value = pv_sum + v('pvTerminal')
        calculated_value = _if(
            sheet, v('costOfEquity') > v('terminalGrowth'), calculated_value,
            _literal(sheet, 'Blocked: cost of equity must exceed growth'),
        )
        sheet.iloc[index['value'], col] = _if(
            sheet, v('years') == _literal(sheet, 10), calculated_value,
            _literal(sheet, 'Blocked: this schedule requires 10 years'),
        )
        sheet.iloc[index['coveredYears'], col] = covered_sum
        _number_format(v('value'), output=True)
    _method_check(sheet, index, cases)
    return sheet, index['value']


def _synergy_sheet(method: dict, dcf: ps.Sheet, inputs: ps.Sheet,
                   input_index: dict) -> tuple[ps.Sheet, int]:
    cases = method['scenarios']
    rows = [
        ('fraction', 'Incremental cost savings fraction'),
        ('costBase', 'Historical cost base / USD m'),
        ('rampYears', 'Years to full savings'),
        ('upfrontCost', 'Upfront cost / initial annual savings / USD m'),
        ('baseRevenue', 'Base revenue / USD m'),
        ('shares', 'Valuation dilution proxy / million shares'),
        ('terminalGrowth', 'Terminal growth'),
        ('terminalWacc', 'Terminal WACC'),
        ('terminalTax', 'Terminal tax rate'),
        ('standalone', 'Standalone DCF / USD per share'),
    ]
    for year in range(1, 11):
        rows.extend([
            (f'revenue{year}', f'Y{year} revenue / USD m'),
            (f'ramp{year}', f'Y{year} ramp to full savings'),
            (f'pretax{year}', f'Y{year} incremental pretax savings / USD m'),
            (f'aftertax{year}', f'Y{year} after-tax savings / USD m'),
            (f'pv{year}', f'Y{year} PV savings / USD m'),
        ])
    rows.extend([
        ('terminalSavings', 'Terminal after-tax savings / USD m'),
        ('terminalValue', 'Terminal synergy value / USD m'),
        ('pvTerminal', 'PV terminal synergies / USD m'),
        ('pvSynergies', 'Net PV incremental synergies / USD m'),
        ('value', 'Buyer-specific value / USD per share'),
    ])
    sheet, index = _parameter_sheet('WD40_Synergies', rows, cases)
    one = _literal(sheet, 1)
    for col, case in enumerate(cases):
        assumptions = case['assumptions']
        for key, field in [
                ('fraction', 'costSavingsFraction'), ('costBase', 'costBase'),
                ('rampYears', 'rampYears'),
                ('terminalGrowth', 'terminalGrowth')]:
            _put_parameter(sheet, index, key, col, assumptions[field],
                           key in {'fraction', 'terminalGrowth'})
        for key, source_key in [
                ('baseRevenue', 'revenue'), ('shares', 'shares'),
                ('terminalTax', 'terminalTaxRate')]:
            sheet.iloc[index[key], col] = _cross(
                sheet, inputs, input_index[source_key],
            )
        sheet.iloc[index['standalone'], col] = _cross(sheet, dcf, 26)
        sheet.iloc[index['terminalWacc'], col] = _cross(sheet, dcf, 11, 10)

        def v(key: str) -> ps.Cell:
            return sheet.iloc[index[key], col]

        sheet.iloc[index['upfrontCost'], col] = v('costBase') * v('fraction')
        pv_sum = _literal(sheet, 0)
        for year in range(1, 11):
            sheet.iloc[index[f'revenue{year}'], col] = _cross(
                sheet, dcf, 2, year,
            )
            ratio = _b(_literal(sheet, year) / v('rampYears'))
            sheet.iloc[index[f'ramp{year}'], col] = _if(
                sheet, ratio > one, one, ratio,
            )
            sheet.iloc[index[f'pretax{year}'], col] = (
                v('costBase') * v('fraction')
                * _b(v(f'revenue{year}') / v('baseRevenue'))
                * v(f'ramp{year}')
            )
            sheet.iloc[index[f'aftertax{year}'], col] = (
                v(f'pretax{year}')
                * _b(one - _cross(sheet, dcf, 5, year))
            )
            sheet.iloc[index[f'pv{year}'], col] = (
                v(f'aftertax{year}') * _cross(sheet, dcf, 12, year)
            )
            pv_sum = pv_sum + v(f'pv{year}')
        sheet.iloc[index['terminalSavings'], col] = (
            v('costBase') * v('fraction')
            * _b(v('revenue10') / v('baseRevenue'))
            * _b(one + v('terminalGrowth'))
            * _b(one - v('terminalTax'))
        )
        sheet.iloc[index['terminalValue'], col] = (
            v('terminalSavings')
            / _b(v('terminalWacc') - v('terminalGrowth'))
        )
        sheet.iloc[index['pvTerminal'], col] = (
            v('terminalValue') * _cross(sheet, dcf, 12, 10)
        )
        sheet.iloc[index['pvSynergies'], col] = (
            pv_sum + v('pvTerminal') - v('upfrontCost')
        )
        sheet.iloc[index['value'], col] = (
            v('standalone') + _b(v('pvSynergies') / v('shares'))
        )
        _number_format(v('value'), output=True)
    _method_check(sheet, index, cases)
    return sheet, index['value']


def _lbo_sheet(method: dict, dcf: ps.Sheet, inputs: ps.Sheet,
               input_index: dict) -> tuple[ps.Sheet, int]:
    cases = [case for case in method['scenarios']
             if case.get('value') is not None]
    rows = [
        ('targetIrr', 'Sponsor return hurdle'),
        ('years', 'Hold period / years'),
        ('debtMultiple', 'Entry debt / reported EBITDA'),
        ('debtRate', 'Debt interest rate'),
        ('exitMultiple', 'Fixed exit EV / EBITDA'),
        ('minimumCash', 'Minimum operating cash / USD m'),
        ('sweepRate', 'Cash sweep fraction'),
        ('amortRate', 'Mandatory annual fraction of initial debt'),
        ('exitFeeRate', 'Exit fees / exit enterprise value'),
        ('transactionFeeRate', 'Transaction fees / entry enterprise value'),
        ('financingFeeRate', 'Financing fees / new debt'),
        ('dandA0', 'Historical cash-flow D&A / USD m'),
        ('reportedEbit0', 'Historical reported EBIT / USD m'),
        ('revenue0', 'Historical revenue / USD m'),
        ('shares', 'Valuation dilution proxy / million shares'),
        ('oldDebt', 'Existing refinanced debt / USD m'),
        ('oldCash', 'Target cash / USD m'),
        ('rdMargin', 'R&D adjusted EBIT uplift / historical sales'),
        ('daMargin', 'Historical cash-flow D&A / sales'),
        ('ebitda0', 'Historical reported EBITDA proxy / USD m'),
        ('newDebt', 'New borrowing / USD m'),
        ('targetCashUsed', 'Target cash used at closing / USD m'),
        ('initialCash', 'Cash retained before top-up / USD m'),
        ('cashTopUp', 'Sponsor-funded cash top-up / USD m'),
    ]
    schedule_keys = [
        ('revenue', 'Revenue'), ('ebit', 'Adjusted EBIT'),
        ('reportedEbit', 'Reported EBIT proxy'), ('ebitda', 'EBITDA proxy'),
        ('fcff', 'FCFF proxy'), ('tax', 'Tax rate'),
        ('openingDebt', 'Opening debt'), ('interest', 'Interest'),
        ('shield', 'Interest tax shield'), ('openingCash', 'Opening cash'),
        ('cashBeforePrincipal', 'Cash generated before principal'),
        ('available', 'Cash available above minimum'),
        ('mandatoryRequired', 'Required amortization'),
        ('feasible', 'Funding feasible / 1=yes'),
        ('mandatoryPaid', 'Mandatory amortization paid'),
        ('sweep', 'Additional cash sweep'), ('closingDebt', 'Closing debt'),
        ('closingCash', 'Closing cash'), ('shortfall', 'Funding shortfall'),
    ]
    for year in range(1, 6):
        rows.extend((f'{key}{year}', f'Y{year} {label} / USD m'
                     if key not in {'tax', 'feasible'} else f'Y{year} {label}')
                    for key, label in schedule_keys)
    rows.extend([
        ('exitEv', 'Exit enterprise value / USD m'),
        ('exitFees', 'Exit transaction fees / USD m'),
        ('exitEquity', 'Sponsor exit equity / USD m'),
        ('equityCapacity', 'Entry equity capacity at hurdle / USD m'),
        ('entryFixedCosts', 'Entry fixed uses net of other sources / USD m'),
        ('unboundedPrice', 'Analytic entry price before grid bounds / USD'),
        ('value', 'Ability to pay within $50-$400 grid / USD per share'),
        ('equityPurchase', 'Target equity purchase / USD m'),
        ('entryEv', 'Entry enterprise value / USD m'),
        ('transactionFees', 'Entry transaction fees / USD m'),
        ('financingFees', 'Entry financing fees / USD m'),
        ('totalUses', 'Total acquisition uses / USD m'),
        ('sponsorEquity', 'Sponsor initial equity / USD m'),
        ('totalSources', 'Total acquisition sources / USD m'),
        ('sourcesMinusUses', 'Sources minus uses / USD m'),
        ('moic', 'Sponsor MOIC'), ('irr', 'Sponsor annualized IRR'),
    ])
    sheet, index = _parameter_sheet('WD40_LBO', rows, cases)
    zero, one = (_literal(sheet, n) for n in (0, 1))

    def minimum(a: ps.Cell, b: ps.Cell) -> ps.Cell:
        return _if(sheet, a < b, a, b)

    def positive(a: ps.Cell) -> ps.Cell:
        return _if(sheet, a > zero, a, zero)

    for col, case in enumerate(cases):
        assumptions = case['assumptions']
        for key, field in [
                ('targetIrr', 'targetIrr'), ('years', 'holdYears'),
                ('debtMultiple', 'debtMultiple'), ('debtRate', 'debtRate'),
                ('exitMultiple', 'fixedExitMultiple'),
                ('minimumCash', 'minimumCash'), ('sweepRate', 'cashSweepRate'),
                ('exitFeeRate', 'exitFeeRate'),
                ('transactionFeeRate', 'transactionFeeRate'),
                ('financingFeeRate', 'financingFeeRate'),
                ('dandA0', 'dandA0')]:
            _put_parameter(sheet, index, key, col, assumptions[field],
                           key.endswith('Rate') or key == 'targetIrr')
        new_debt = case['sourcesAndUses']['newDebt']
        amort_rate = (assumptions['annualMandatoryAmortization'] / new_debt
                      if new_debt else 0)
        _put_parameter(sheet, index, 'amortRate', col, amort_rate, True)
        for key, source_key in [
                ('reportedEbit0', 'reportedEbit'), ('revenue0', 'revenue'),
                ('shares', 'shares'), ('oldDebt', 'debt'),
                ('oldCash', 'cash')]:
            sheet.iloc[index[key], col] = _cross(
                sheet, inputs, input_index[source_key],
            )

        def v(key: str) -> ps.Cell:
            return sheet.iloc[index[key], col]

        sheet.iloc[index['rdMargin'], col] = (
            _cross(sheet, inputs, input_index['margin1'])
            - _b(v('reportedEbit0') / v('revenue0'))
        )
        sheet.iloc[index['daMargin'], col] = v('dandA0') / v('revenue0')
        sheet.iloc[index['ebitda0'], col] = v('reportedEbit0') + v('dandA0')
        sheet.iloc[index['newDebt'], col] = v('ebitda0') * v('debtMultiple')
        sheet.iloc[index['targetCashUsed'], col] = positive(
            _b(v('oldCash') - v('minimumCash')),
        )
        sheet.iloc[index['initialCash'], col] = (
            v('oldCash') - v('targetCashUsed')
        )
        sheet.iloc[index['cashTopUp'], col] = positive(
            _b(v('minimumCash') - v('initialCash')),
        )
        feasible_sum = zero
        for year in range(1, 6):
            sheet.iloc[index[f'revenue{year}'], col] = _cross(
                sheet, dcf, 2, year,
            )
            sheet.iloc[index[f'ebit{year}'], col] = _cross(sheet, dcf, 4, year)
            sheet.iloc[index[f'fcff{year}'], col] = _cross(sheet, dcf, 9, year)
            sheet.iloc[index[f'tax{year}'], col] = _cross(sheet, dcf, 5, year)
            sheet.iloc[index[f'reportedEbit{year}'], col] = (
                v(f'ebit{year}') - _b(v(f'revenue{year}') * v('rdMargin'))
            )
            sheet.iloc[index[f'ebitda{year}'], col] = (
                v(f'reportedEbit{year}')
                + _b(v(f'revenue{year}') * v('daMargin'))
            )
            opening_debt = (v('newDebt') if year == 1
                            else v(f'closingDebt{year - 1}'))
            sheet.iloc[index[f'openingDebt{year}'], col] = opening_debt + zero
            opening_cash = (_b(v('initialCash') + v('cashTopUp')) if year == 1
                            else v(f'closingCash{year - 1}'))
            sheet.iloc[index[f'openingCash{year}'], col] = opening_cash + zero
            sheet.iloc[index[f'interest{year}'], col] = (
                v(f'openingDebt{year}') * v('debtRate')
            )
            sheet.iloc[index[f'shield{year}'], col] = (
                minimum(v(f'interest{year}'),
                        positive(v(f'reportedEbit{year}')))
                * v(f'tax{year}')
            )
            sheet.iloc[index[f'cashBeforePrincipal{year}'], col] = (
                v(f'fcff{year}') - v(f'interest{year}') + v(f'shield{year}')
            )
            sheet.iloc[index[f'available{year}'], col] = (
                v(f'openingCash{year}') + v(f'cashBeforePrincipal{year}')
                - v('minimumCash')
            )
            sheet.iloc[index[f'mandatoryRequired{year}'], col] = minimum(
                v(f'openingDebt{year}'), _b(v('newDebt') * v('amortRate')),
            )
            sheet.iloc[index[f'feasible{year}'], col] = _if(
                sheet, v(f'available{year}') >= v(f'mandatoryRequired{year}'),
                one, zero,
            )
            sheet.iloc[index[f'mandatoryPaid{year}'], col] = _if(
                sheet, v(f'feasible{year}') == one,
                v(f'mandatoryRequired{year}'), positive(v(f'available{year}')),
            )
            sheet.iloc[index[f'sweep{year}'], col] = _if(
                sheet, v(f'feasible{year}') == one,
                minimum(
                    _b(v(f'openingDebt{year}') - v(f'mandatoryPaid{year}')),
                    _b(positive(_b(
                        v(f'available{year}') - v(f'mandatoryPaid{year}')
                    )) * v('sweepRate')),
                ), zero,
            )
            sheet.iloc[index[f'closingDebt{year}'], col] = (
                v(f'openingDebt{year}') - v(f'mandatoryPaid{year}')
                - v(f'sweep{year}')
            )
            sheet.iloc[index[f'closingCash{year}'], col] = (
                v(f'openingCash{year}') + v(f'cashBeforePrincipal{year}')
                - v(f'mandatoryPaid{year}') - v(f'sweep{year}')
            )
            sheet.iloc[index[f'shortfall{year}'], col] = positive(
                _b(v(f'mandatoryRequired{year}') - v(f'available{year}')),
            )
            feasible_sum = feasible_sum + v(f'feasible{year}')
        sheet.iloc[index['exitEv'], col] = v('ebitda5') * v('exitMultiple')
        sheet.iloc[index['exitFees'], col] = v('exitEv') * v('exitFeeRate')
        sheet.iloc[index['exitEquity'], col] = positive(_b(
            v('exitEv') - v('exitFees') - v('closingDebt5') + v('closingCash5')
        ))
        sheet.iloc[index['equityCapacity'], col] = (
            v('exitEquity') / _b(_b(one + v('targetIrr')) ** v('years'))
        )
        sheet.iloc[index['entryFixedCosts'], col] = (
            _b(v('oldDebt') * _b(one + v('transactionFeeRate')))
            - _b(v('oldCash') * v('transactionFeeRate'))
            + _b(v('newDebt') * v('financingFeeRate'))
            + v('cashTopUp') - v('newDebt') - v('targetCashUsed')
        )
        sheet.iloc[index['unboundedPrice'], col] = (
            _b(v('equityCapacity') - v('entryFixedCosts'))
            / _b(v('shares') * _b(one + v('transactionFeeRate')))
        )
        capped = _if(sheet, v('unboundedPrice') > _literal(sheet, 400),
                     _literal(sheet, 400), v('unboundedPrice'))
        calculated_value = _if(
            sheet, feasible_sum == _literal(sheet, 5),
            _if(sheet, capped >= _literal(sheet, 50), capped,
                _literal(sheet, 'No solution in grid')),
            _literal(sheet, 'Blocked: funding shortfall'),
        )
        sheet.iloc[index['value'], col] = _if(
            sheet, v('years') == _literal(sheet, 5), calculated_value,
            _literal(sheet, 'Blocked: this schedule requires 5 years'),
        )
        sheet.iloc[index['equityPurchase'], col] = v('value') * v('shares')
        sheet.iloc[index['entryEv'], col] = (
            v('equityPurchase') + v('oldDebt') - v('oldCash')
        )
        sheet.iloc[index['transactionFees'], col] = (
            positive(v('entryEv')) * v('transactionFeeRate')
        )
        sheet.iloc[index['financingFees'], col] = (
            v('newDebt') * v('financingFeeRate')
        )
        sheet.iloc[index['totalUses'], col] = (
            v('equityPurchase') + v('oldDebt') + v('transactionFees')
            + v('financingFees') + v('cashTopUp')
        )
        sheet.iloc[index['sponsorEquity'], col] = (
            v('totalUses') - v('newDebt') - v('targetCashUsed')
        )
        sheet.iloc[index['totalSources'], col] = (
            v('newDebt') + v('targetCashUsed') + v('sponsorEquity')
        )
        sheet.iloc[index['sourcesMinusUses'], col] = (
            v('totalSources') - v('totalUses')
        )
        sheet.iloc[index['moic'], col] = v('exitEquity') / v('sponsorEquity')
        sheet.iloc[index['irr'], col] = (
            v('moic') ** _b(one / v('years'))
        ) - one
        _number_format(v('value'), output=True)
        _number_format(v('irr'), percentage=True, output=True)
    _method_check(sheet, index, cases)
    return sheet, index['value']


def _observation_sheet(method: dict, original_inputs: ps.Sheet,
                       input_index: dict) -> tuple[ps.Sheet, int]:
    cases = method['scenarios']
    observations = method.get('observations', [])
    rows = [
        ('multiple', 'Fixed observation statistic / rebuild after changes'),
        ('targetMetric', 'Target metric / USD m or EPS'),
        ('netDebt', 'Net debt / USD m'),
        ('shares', 'Valuation dilution proxy / million shares'),
        ('value', 'Indicative value / USD per share'),
        ('basis', 'Observation basis'),
    ]
    for number, observation in enumerate(observations):
        rows.extend([
            (f'observation{number}', f'Observation {number + 1} multiple'),
            (f'name{number}', f'Observation {number + 1} identity'),
            (f'sources{number}', f'Observation {number + 1} source IDs'),
        ])
    name = ('WD40_Precedents' if method['kind'] == 'precedents'
            else 'WD40_' + method['id'].replace('-', '_')[:20])
    sheet, index = _parameter_sheet(name, rows, cases)
    for col, case in enumerate(cases):
        _put_parameter(sheet, index, 'multiple', col, case['multiple'])
        metric = case.get('metric', 'ebitda')
        if metric == 'sales':
            target = _cross(sheet, original_inputs, input_index['revenue'])
        elif metric == 'eps':
            target = _literal(sheet, case['targetMetric'])
        else:
            da = case.get('targetEbitda', case.get('targetMetric', 111.984))
            reported = original_inputs.iloc[
                input_index['reportedEbit'], 0,
            ].value
            target = (
                _cross(sheet, original_inputs, input_index['reportedEbit'])
                + _literal(sheet, da - reported)
            )
        sheet.iloc[index['targetMetric'], col] = target + _literal(sheet, 0)
        sheet.iloc[index['netDebt'], col] = (
            _cross(sheet, original_inputs, input_index['debt'])
            - _cross(sheet, original_inputs, input_index['cash'])
        )
        sheet.iloc[index['shares'], col] = _cross(
            sheet, original_inputs, input_index['shares'],
        )
        gross = _b(sheet.iloc[index['multiple'], col]
                   * sheet.iloc[index['targetMetric'], col])
        sheet.iloc[index['value'], col] = (
            gross if metric == 'eps' else
            _b(gross - sheet.iloc[index['netDebt'], col])
            / sheet.iloc[index['shares'], col]
        )
        sheet.iloc[index['basis'], col] = method['rangeType']
        _number_format(sheet.iloc[index['value'], col], output=True)
    for number, observation in enumerate(observations):
        sheet.iloc[index[f'observation{number}'], 0] = observation['multiple']
        sheet.iloc[index[f'name{number}'], 0] = observation.get(
            'target', observation.get('id', ''),
        )
        sheet.iloc[index[f'sources{number}'], 0] = ', '.join(
            observation.get('sourceIds', []),
        )
    _method_check(sheet, index, cases)
    return sheet, index['value']


def _methods_summary(methods: list[dict], outputs: dict) -> ps.Sheet:
    sheet = _new_sheet(
        'WD40_Methods', [method['label'] for method in methods],
        ['Low / USD per share', 'Central / USD per share',
         'High / USD per share', 'Status', 'Range interpretation',
         'Limitations'],
    )
    for row, method in enumerate(methods):
        target = outputs.get(method['id'])
        if target:
            source, output_row = target
            for col in range(min(3, len(method['scenarios']))):
                sheet.iloc[row, col] = _cross(sheet, source, output_row, col)
                _number_format(sheet.iloc[row, col], output=True)
        else:
            for col in range(3):
                sheet.iloc[row, col] = 'Unavailable'
        sheet.iloc[row, 3] = method['status']
        sheet.iloc[row, 4] = method['rangeType']
        sheet.iloc[row, 5] = ' '.join(method.get('limitations', []))
    return sheet


def _layout_parameters(sheet: ps.Sheet) -> ps.ExcelParameters:
    '''Size each view for its actual text while preserving cell styles.'''
    table = sheet.to_dictionary()['table']
    count = len(table['columns'])
    widths = [58] + [22] * count
    if sheet.name == 'WD40_Summary':
        widths = [58, 32] + [26] * (count - 1)
    elif sheet.name == 'WD40_Methods':
        widths = [58, 23, 23, 23, 22, 40, 110]
    elif sheet.name == 'WD40_Questions':
        widths = [27, 74, 17, 25, 20, 32, 102, 112, 62, 54]
    elif sheet.name == 'WD40_Sources':
        widths = [40, 60, 90, 22, 22, 72, 112]
    elif sheet.name == 'WD40_Basis':
        widths = [34, 120]
    elif sheet.name.startswith('WD40_Regions_'):
        widths = [61] + [24] * count
    elif sheet.name.startswith('WD40_Inputs_'):
        widths = [65, 30]
    elif sheet.name in {'WD40_LBO', 'WD40_DDM', 'WD40_Synergies'}:
        widths = [65] + [31] * count
    elif sheet.name == 'WD40_Precedents':
        widths = [65] + [31] * count
    percentage_keys = {
        'taxRate', 'terminalTaxRate', 'growth1', 'growth2to5', 'margin1',
        'targetMargin', 'waccInitial', 'waccTerminal', 'terminalGrowth',
        'terminalRoic', 'failureProbability', 'failureRecovery',
        'overseasTaxRate',
    }
    integer_keys = {
        'marginConvergenceYear', 'rdLife', 'terminalExcessReturns',
        'capitalizeRd', 'holdTaxRate', 'lagOverride', 'lagYears',
        'failureBookBasis', 'cashHaircut',
    }
    money_format = '#,##0.000;[Red](#,##0.000);–'
    heights = [36.0]
    for row, metadata in enumerate(table['rows']):
        label = str(metadata['name'])
        line_counts = [_wrapped_lines(label, widths[0])]
        for col in range(count):
            cell = sheet.iloc[row, col]
            value = cell.value
            style = {
                **(cell.excel_format or {}),
                'font_name': 'Arial', 'font_size': 10,
                'valign': 'vcenter',
                'text_wrap': isinstance(value, str),
                'align': 'left' if isinstance(value, str) else 'right',
            }
            if value is not None and not isinstance(value, str):
                if 'num_format' not in style:
                    percentage_terms = (
                        'growth', 'margin', 'tax rate', 'wacc',
                        'cost of equity',
                    )
                    percentage_label = any(
                        phrase in label.lower() for phrase in percentage_terms
                    )
                    style['num_format'] = (
                        '0.0%' if percentage_label else money_format
                    )
                if label in {
                        'Stage-one horizon / years', 'Hold period / years',
                        'Years to full savings', 'Covered years / count',
                } or '/ 1=yes' in label:
                    style['num_format'] = '0'
                if sheet.name.startswith('WD40_Inputs_'):
                    key = INPUT_KEYS[row][0] if row < len(INPUT_KEYS) else ''
                    if key in percentage_keys or label in {
                            'Effective terminal tax rate',
                            'Effective terminal ROIC'}:
                        style['num_format'] = '0.0%'
                    elif key in integer_keys:
                        style['num_format'] = '0'
                    else:
                        style['num_format'] = money_format
                elif sheet.name.startswith('WD40_Regions_'):
                    style['num_format'] = (
                        '0.0%' if 'growth' in label.lower() or 'CAGR' in label
                        else money_format
                    )
                elif sheet.name.startswith('WD40_DCF_') and row == 0:
                    style['num_format'] = '0'
            cell.excel_format = style
            if isinstance(value, str):
                line_counts.append(_wrapped_lines(value, widths[col + 1]))
        minimum = 26.0
        if sheet.name in {'WD40_Questions', 'WD40_Sources'}:
            minimum = 48.0
        elif sheet.name == 'WD40_Basis':
            minimum = 42.0
        elif sheet.name == 'WD40_Summary' and row >= 8:
            minimum = 52.0
        heights.append(min(409.0, max(minimum, max(line_counts) * 14 + 8)))
    return ps.ExcelParameters(
        column_width=tuple(widths), row_height=tuple(heights),
        label_row_format={
            'bold': True, 'font_name': 'Arial', 'font_size': 10,
            'font_color': '#29332C', 'bg_color': '#F4F3ED',
            'text_wrap': True, 'valign': 'vcenter', 'align': 'left',
        },
        label_column_format={
            'bold': True, 'font_name': 'Arial', 'font_size': 10,
            'font_color': '#FFFFFF', 'bg_color': '#294B3C',
            'text_wrap': True, 'valign': 'vcenter', 'align': 'left',
        },
        top_left_corner_text=sheet.name,
    )


def _wrapped_lines(value: str, column_width: float) -> int:
    capacity = max(8, int(column_width * 0.9))
    return sum(max(1, len(textwrap.wrap(line, capacity)))
               for line in value.split('\n'))


def _freeze_headers(path: Path) -> None:
    '''Set worksheet views without rewriting any formulas or cached values.

    portable-spreadsheet 2.2.1 does not expose worksheet-view options. Only
    the generated sheetView element is replaced in the OOXML ZIP container.
    The data, formula, style and calculation XML stays byte-identical.
    '''
    temporary = path.with_suffix('.layout-tmp')
    view = re.compile(rb'<sheetView\b([^>]*?)(?:/>|>.*?</sheetView>)', re.S)
    try:
        with zipfile.ZipFile(path) as source:
            with zipfile.ZipFile(temporary, 'w') as target:
                for entry in source.infolist():
                    content = source.read(entry.filename)
                    if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',
                                    entry.filename):
                        match = view.search(content)
                        if match is None:
                            raise ValueError('Worksheet view is missing.')
                        attributes = re.sub(
                            rb'\s+showGridLines="[^"]*"', b'', match[1],
                        )
                        replacement = (
                            b'<sheetView' + attributes
                            + b' showGridLines="0">'
                            b'<pane xSplit="1" ySplit="1" topLeftCell="B2" '
                            b'activePane="bottomRight" state="frozen"/>'
                            b'<selection pane="bottomRight" activeCell="B2" '
                            b'sqref="B2"/></sheetView>'
                        )
                        content, count = view.subn(replacement, content, 1)
                        if count != 1:
                            raise ValueError('Expected one worksheet view.')
                    target.writestr(entry, content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def build_workbook(results: Any, methods: list[dict[str, Any]],
                   questions: dict[str, Any], output_path: str | Path) -> dict:
    '''Write Excel and return the identical formula graph for the browser.'''
    if isinstance(results, dict):
        results = results.get('scenarios', results.get('results', []))
    results = list(results)
    if not results:
        raise ValueError('At least one DCF result is required.')
    methods = list(methods or [])
    questions = questions or {}
    input_sheets, dcf_sheets, input_indices, regional_sheets = [], [], [], []
    for number, result in enumerate(results):
        suffix = re.sub(
            r'[^A-Za-z0-9_]', '_', str(result.get('id', number)),
        )[:15]
        inputs_sheet, index = _inputs_sheet(result, suffix)
        regional = _segments_sheet(result, suffix, inputs_sheet, index)
        dcf_sheet = _dcf_sheet(result, suffix, inputs_sheet, index)
        if regional:
            _segment_residuals(regional, dcf_sheet)
            regional_sheets.append(regional[0])
        input_sheets.append(inputs_sheet)
        dcf_sheets.append(dcf_sheet)
        input_indices.append(index)
        actual = float(dcf_sheet.iloc[26, 0].value)
        expected = float(result['value'])
        if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
            raise ValueError(
                f'Export DCF mismatch for {suffix}: {actual} != {expected}'
            )
        eva_difference = float(dcf_sheet.iloc[33, 0].value)
        if abs(eva_difference) > 1e-7:
            raise ValueError(
                f'EVA reconciliation failed for {suffix}: {eva_difference}'
            )

    selected = next((i for i, item in enumerate(results)
                     if item.get('id') == 'base'), 0)
    original = next((i for i, item in enumerate(results)
                     if item.get('id') == 'original'), 0)
    method_sheets, method_outputs = [], {}
    for method in methods:
        if not method.get('scenarios') or not any(
                case.get('value') is not None for case in method['scenarios']):
            continue
        if method['kind'] == 'ddm':
            sheet, output_row = _ddm_sheet(
                method, dcf_sheets[selected], input_sheets[selected],
                input_indices[selected], results[selected],
            )
        elif method['kind'] == 'synergy':
            sheet, output_row = _synergy_sheet(
                method, dcf_sheets[selected], input_sheets[selected],
                input_indices[selected],
            )
        elif method['kind'] == 'lbo':
            sheet, output_row = _lbo_sheet(
                method, dcf_sheets[selected], input_sheets[selected],
                input_indices[selected],
            )
        elif method['kind'] in {'precedents', 'comps'}:
            sheet, output_row = _observation_sheet(
                method, input_sheets[original], input_indices[original],
            )
        else:
            continue
        method_sheets.append(sheet)
        method_outputs[method['id']] = (sheet, output_row)

    summary = _summary(results, dcf_sheets)
    basis = _notes_sheet(results, methods, questions)
    sheets = [summary]
    if methods:
        sheets.append(_methods_summary(methods, method_outputs))
    sheets.extend(regional_sheets)
    for inputs_sheet, dcf_sheet in zip(input_sheets, dcf_sheets):
        sheets.extend([inputs_sheet, dcf_sheet])
    sheets.extend(method_sheets)
    sheets.append(basis)
    questions_sheet = _questions_sheet(questions)
    if questions_sheet:
        sheets.append(questions_sheet)
    sources_sheet = _sources_sheet(results, questions)
    if sources_sheet:
        sheets.append(sources_sheet)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    params = tuple(_layout_parameters(sheet) for sheet in sheets)
    ps.WorkBook(*sheets).to_excel(output_path, export_parameters=params)
    _freeze_headers(output_path)
    books = [_page_book(sheet) for sheet in sheets]
    expected_values = {
        cell_id: c['cachedValue']
        for book in books for cell_id, c in book['cells'].items()
        if c.get('formula')
    }
    return {
        'path': str(output_path), 'books': books,
        'expectedValues': expected_values,
        'sheetNames': [sheet.name for sheet in sheets],
        'formulaCount': len(expected_values),
        'methodSheets': {key: value[0].name
                         for key, value in method_outputs.items()},
        'verification': {
            'pythonDcfParity': True, 'evaReconciliation': True,
            'nativeExcelRecalculation': False,
            'browserFormulaParity': 'pending',
        },
        'warnings': [
            'Native Microsoft Excel recalculation has not been performed.',
        ],
    }
