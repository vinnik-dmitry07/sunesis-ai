'''Read the original embedded case without modifying its proposal history.'''

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


INPUT_CELLS = {
    'revenue': 'Input sheet!B11',
    'reportedEbit': 'Input sheet!B12',
    'bookEquity': 'Input sheet!B14',
    'debt': 'Input sheet!B15',
    'cash': 'Input sheet!B18',
    'nonoperatingAssets': 'Input sheet!B19',
    'minorityInterests': 'Input sheet!B20',
    'shares': 'Input sheet!B21',
    'price': 'Input sheet!B22',
    'taxRate': 'Input sheet!B23',
    'terminalTaxRate': 'Input sheet!B24',
    'growth1': 'Input sheet!B26',
    'margin1': 'Input sheet!B27',
    'growth2to5': 'Input sheet!B28',
    'targetMargin': 'Input sheet!B29',
    'marginConvergenceYear': 'Input sheet!B30',
    'salesToCapital1': 'Input sheet!B31',
    'salesToCapital2': 'Input sheet!B32',
    'waccInitial': 'Cost of capital worksheet!B12',
    'waccTerminal': 'Input sheet!B46',
    'terminalRoic': 'Input sheet!B49',
    'terminalGrowth': 'Input sheet!B68',
    'rdCurrent': 'R& D converter!F7',
    'rdLife': 'R& D converter!F6',
    'lagYears': 'Input sheet!B57',
}

FLAG_CELLS = {
    'capitalizeRd': 'Input sheet!B16',
    'capitalizeLeases': 'Input sheet!B17',
    'terminalExcessReturns': 'Input sheet!B48',
    'holdTaxRate': 'Input sheet!B59',
    'lagOverride': 'Input sheet!B56',
    'useNol': 'Input sheet!B61',
    'distressAdjustment': 'Input sheet!B51',
    'trappedCashAdjustment': 'Input sheet!B70',
    'employeeOptions': 'Input sheet!B37',
}

DEFAULTS = {
    'revenue': 619.985, 'reportedEbit': 103.793,
    'bookEquity': 268.472, 'debt': 86.995, 'cash': 58.13,
    'nonoperatingAssets': 0.0, 'minorityInterests': 0.0,
    'shares': 13.633263, 'price': 216.04,
    'taxRate': 0.22200027552004406, 'terminalTaxRate': 0.25,
    'growth1': 0.05, 'marginConvergenceYear': 5,
    'salesToCapital1': 2.0, 'waccInitial': 0.09,
    'waccTerminal': 0.08, 'terminalRoic': 0.15,
    'terminalGrowth': 0.025, 'rdCurrent': 8.7, 'rdLife': 3,
    'lagYears': 1,
}

FLAG_DEFAULTS = {
    'capitalizeRd': True, 'capitalizeLeases': False,
    'terminalExcessReturns': False, 'holdTaxRate': False,
    'lagOverride': False, 'useNol': False,
    'distressAdjustment': False, 'trappedCashAdjustment': False,
    'employeeOptions': False,
}


def embedded_json(index_path: str | Path, name: str) -> dict[str, Any]:
    '''Decode a JSON constant, without evaluating browser JavaScript.'''
    text = Path(index_path).read_text(encoding='utf-8')
    marker = f'const {name}='
    if text.count(marker) != 1:
        raise ValueError(f'Expected one {name} declaration.')
    return json.JSONDecoder().raw_decode(text.split(marker, 1)[1])[0]


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def as_flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() == 'yes'
    return bool(value)


def resolve_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    '''Resolve semantic inputs; explicit semantic keys override raw cells.

    Pass only ``{'overrides': full_cell_map}`` when editing raw cells, or edit
    semantic keys directly. This avoids ambiguity between two representations.
    '''
    overrides = dict(inputs.get('overrides', {}))
    resolved: dict[str, Any] = dict(DEFAULTS)
    for key, cell_id in INPUT_CELLS.items():
        if cell_id in overrides:
            resolved[key] = overrides[cell_id]
        if key in inputs:
            resolved[key] = inputs[key]
    for key, cell_id in FLAG_CELLS.items():
        value = overrides.get(cell_id, FLAG_DEFAULTS[key])
        resolved[key] = as_flag(inputs.get(key, value))

    history = [overrides.get(f'R& D converter!B{row}', value)
               for row, value in zip(range(11, 15), [8.0, 6.2, 5.1, 5.6])]
    resolved['rdHistory'] = list(inputs.get('rdHistory', history))
    resolved['initialNol'] = inputs.get(
        'initialNol', overrides.get('Input sheet!B62', 0.0),
    ) if resolved['useNol'] else 0.0
    life = int(resolved['rdLife'])
    active = resolved['rdHistory'][:life]
    resolved['rdAmortization'] = sum(active) / life if life else 0.0
    resolved['rdAsset'] = resolved['rdCurrent'] + sum(
        value * (life - age) / life
        for age, value in enumerate(active, 1)
    ) if life else 0.0
    rd_adjustment = resolved['rdCurrent'] - resolved['rdAmortization']
    resolved['adjustedEbit'] = (
        resolved['reportedEbit']
        + (rd_adjustment if resolved['capitalizeRd'] else 0.0)
    )
    resolved['openingCapital'] = (
        resolved['bookEquity'] + resolved['debt'] - resolved['cash']
        + (resolved['rdAsset'] if resolved['capitalizeRd'] else 0.0)
    )

    linked = {
        'margin1FromAdjusted': ('margin1', 'Input sheet!B27'),
        'targetMarginFromMargin1': ('targetMargin', 'Input sheet!B29'),
        'growth2FromGrowth1': ('growth2to5', 'Input sheet!B28'),
        'salesToCapital2From1': ('salesToCapital2', 'Input sheet!B32'),
    }
    for flag, (key, cell_id) in linked.items():
        resolved[flag] = bool(inputs.get(
            flag, cell_id not in overrides and key not in inputs,
        ))
    if resolved.get('margin1') is None or resolved['margin1FromAdjusted']:
        resolved['margin1'] = resolved['adjustedEbit'] / resolved['revenue']
    if (resolved.get('targetMargin') is None
            or resolved['targetMarginFromMargin1']):
        resolved['targetMargin'] = resolved['margin1']
    if (resolved.get('growth2to5') is None
            or resolved['growth2FromGrowth1']):
        resolved['growth2to5'] = resolved['growth1']
    if (resolved.get('salesToCapital2') is None
            or resolved['salesToCapital2From1']):
        resolved['salesToCapital2'] = resolved['salesToCapital1']

    resolved['overrides'] = overrides
    for key in ('inputHash', 'basis', 'priceAsOf', 'financialPeriod',
                'sources', 'originalProposalCount'):
        if key in inputs:
            resolved[key] = inputs[key]
    return resolved


def load_original_inputs(index_path: str | Path) -> dict[str, Any]:
    '''Return a separate immutable-by-convention original proposal snapshot.'''
    book = embedded_json(index_path, 'BUNDLED_BOOK')
    case = embedded_json(index_path, 'BUNDLED_CASE')
    overrides = {
        proposal['cell']: proposal['value']
        for proposal in case['proposals']
        if proposal.get('operation') != 'retain_formula'
    }
    # Inactive helper defaults are copied only where the simple DCF uses them.
    for cell_id in ('Input sheet!B49', 'Input sheet!B57'):
        if cell_id not in overrides:
            overrides[cell_id] = book['cells'][cell_id].get('value')
    return resolve_inputs({
        'overrides': overrides,
        'inputHash': stable_hash(overrides),
        'basis': ('Retrospective FY2025 financials; filings were published '
                  'after the historical reference price.'),
        'priceAsOf': '2025-08-29',
        'financialPeriod': 'FY2025',
        'sources': case.get('sources', []),
        'originalProposalCount': len(case['proposals']),
    })
