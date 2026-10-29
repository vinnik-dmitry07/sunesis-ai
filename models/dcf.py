'''Independent implementation of the active Ginzu FCFF calculation path.'''

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from .common import (
    INPUT_CELLS, load_original_inputs, resolve_inputs, stable_hash,
)
from .segments import build_segments


def validate_inputs(inputs: dict[str, Any]) -> None:
    '''Check the active calculation path before division or discounting.'''
    for key, value in inputs.items():
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError(f'{key} must be finite.')
    for key in ('revenue', 'shares', 'salesToCapital1', 'salesToCapital2',
                'waccInitial', 'waccTerminal'):
        if inputs[key] <= 0:
            raise ValueError(f'{key} must be greater than zero.')
    if inputs['waccTerminal'] <= inputs['terminalGrowth']:
        raise ValueError('Terminal WACC must exceed terminal growth.')
    for key in ('growth1', 'growth2to5', 'terminalGrowth'):
        if inputs[key] <= -1:
            raise ValueError(f'{key} must be greater than -100%.')
    for key in ('taxRate', 'terminalTaxRate'):
        if not 0 <= inputs[key] <= 1:
            raise ValueError(f'{key} must be between zero and one.')
    convergence = inputs['marginConvergenceYear']
    if int(convergence) != convergence or not 1 <= convergence <= 10:
        raise ValueError('Margin convergence year must be an integer 1–10.')
    if (int(inputs['rdLife']) != inputs['rdLife']
            or not 1 <= inputs['rdLife'] <= len(inputs['rdHistory'])):
        raise ValueError('R&D life requires the corresponding history.')
    if inputs['terminalExcessReturns']:
        if inputs['terminalRoic'] <= 0:
            raise ValueError('Active terminal ROIC must be positive.')
        if inputs['terminalGrowth'] > inputs['terminalRoic']:
            raise ValueError('Terminal reinvestment exceeds positive NOPAT.')
    for key in ('capitalizeLeases', 'employeeOptions', 'distressAdjustment',
                'trappedCashAdjustment'):
        if inputs[key]:
            raise ValueError(f'{key} is outside this verified DCF path.')
    if inputs['lagOverride'] and inputs['lagYears'] not in (0, 1, 2, 3):
        raise ValueError('Supported reinvestment lag values are 0, 1, 2, 3.')


def evaluate_dcf(inputs: dict[str, Any]) -> dict[str, Any]:
    '''Calculate the original ten-year FCFF model at full precision.'''
    values = resolve_inputs(inputs)
    validate_inputs(values)
    terminal_growth = values['terminalGrowth']
    terminal_tax = (values['taxRate'] if values['holdTaxRate']
                    else values['terminalTaxRate'])
    growth = [values['growth1']] + [values['growth2to5']] * 4 + [
        values['growth2to5']
        - (values['growth2to5'] - terminal_growth) / 5 * step
        for step in range(1, 6)
    ] + [terminal_growth]
    revenues = [values['revenue']]
    for rate in growth:
        revenues.append(revenues[-1] * (1 + rate))

    forecast = []
    cumulative_discount = 1.0
    nol = values['initialNol']
    capital = values['openingCapital']
    tax_rate = values['taxRate']
    wacc = values['waccInitial']
    convergence = values['marginConvergenceYear']
    for year in range(1, 11):
        margin = values['margin1'] if year == 1 else (
            values['targetMargin'] if year > convergence else
            values['targetMargin']
            - ((values['targetMargin'] - values['margin1']) / convergence)
            * (convergence - year)
        )
        if year > 5:
            tax_rate += (terminal_tax - values['taxRate']) / 5
            wacc -= (values['waccInitial'] - values['waccTerminal']) / 5
        ebit = revenues[year] * margin
        nopat = (ebit if ebit < nol else ebit - (ebit - nol) * tax_rate
                 ) if ebit > 0 else ebit
        nol = nol - ebit if ebit < 0 or nol > ebit else 0.0
        sales_to_capital = (values['salesToCapital1'] if year <= 5
                            else values['salesToCapital2'])
        lag = values['lagYears'] if values['lagOverride'] else 1
        if lag == 0:
            incremental_revenue = revenues[year] - revenues[year - 1]
        elif lag == 1:
            incremental_revenue = revenues[year + 1] - revenues[year]
        elif lag == 2:
            incremental_revenue = (
                revenues[year + 2] - revenues[year + 1]
                if year <= 9 else revenues[11] * terminal_growth
            )
        elif year <= 8:
            incremental_revenue = revenues[year + 3] - revenues[year + 2]
        elif year == 9:
            incremental_revenue = revenues[11] * terminal_growth
        else:
            # Ginzu L8 explicitly extends K8, rather than another revenue diff.
            incremental_revenue = (
                forecast[-1]['reinvestment'] * (1 + terminal_growth)
                * sales_to_capital
            )
        reinvestment = incremental_revenue / sales_to_capital
        fcff = nopat - reinvestment
        cumulative_discount *= 1 / (1 + wacc)
        forecast.append({
            'year': year, 'growth': growth[year - 1],
            'revenue': revenues[year], 'margin': margin, 'ebit': ebit,
            'taxRate': tax_rate, 'nopat': nopat,
            'reinvestment': reinvestment, 'fcff': fcff,
            'wacc': wacc, 'discountFactor': cumulative_discount,
            'pvFcff': fcff * cumulative_discount, 'nol': nol,
            'salesToCapital': sales_to_capital,
            'capitalStart': capital, 'capitalEnd': capital + reinvestment,
            'economicProfit': nopat - wacc * capital,
        })
        capital += reinvestment

    terminal_roic = (values['terminalRoic']
                     if values['terminalExcessReturns'] else wacc)
    terminal_ebit = revenues[11] * forecast[-1]['margin']
    terminal_nopat = terminal_ebit * (1 - terminal_tax)
    terminal_reinvestment = (
        terminal_growth / terminal_roic * terminal_nopat
        if terminal_growth > 0 else 0.0
    )
    terminal_fcff = terminal_nopat - terminal_reinvestment
    terminal_value = terminal_fcff / (
        values['waccTerminal'] - terminal_growth
    )
    pv_terminal_value = terminal_value * cumulative_discount
    pv_forecast = sum(row['pvFcff'] for row in forecast)
    operating_value = pv_forecast + pv_terminal_value
    equity_value = (operating_value - values['debt']
                    - values['minorityInterests'] + values['cash']
                    + values['nonoperatingAssets'])
    # Economic-profit terminal PV is derived from the same capital recurrence:
    # NOPAT grows at g; each year's investment equals g / ROIC times NOPAT.
    # Opening year-11 capital need not equal NOPAT_11 / terminal ROIC.
    pv_terminal_economic_profit = (
        terminal_nopat * (1 - values['waccTerminal'] / terminal_roic)
        / (values['waccTerminal'] - terminal_growth)
        + terminal_nopat / terminal_roic - capital
        if terminal_growth > 0 else
        terminal_nopat / (values['waccTerminal'] - terminal_growth) - capital
    )
    eva_operating_value = values['openingCapital'] + sum(
        row['economicProfit'] * row['discountFactor'] for row in forecast
    ) + pv_terminal_economic_profit * cumulative_discount
    value = equity_value / values['shares']
    return {
        'value': value, 'operatingValue': operating_value,
        'equityValue': equity_value, 'terminalValue': terminal_value,
        'pvTerminalValue': pv_terminal_value,
        'pvForecast': pv_forecast,
        'terminalShare': pv_terminal_value / operating_value,
        'forecast': forecast,
        'terminal': {
            'year': 11, 'growth': terminal_growth,
            'revenue': revenues[11], 'margin': forecast[-1]['margin'],
            'ebit': terminal_ebit, 'taxRate': terminal_tax,
            'nopat': terminal_nopat, 'roic': terminal_roic,
            'reinvestment': terminal_reinvestment,
            'fcff': terminal_fcff, 'wacc': values['waccTerminal'],
            'capitalStart': capital,
            'pvEconomicProfitAtYear10': pv_terminal_economic_profit,
        },
        'evaOperatingValue': eva_operating_value,
        'evaMinusDcf': eva_operating_value - operating_value,
        'inputs': values,
        'overrides': deepcopy(values['overrides']),
    }


def build_scenarios(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    '''Build frozen analyst scenarios without replacing original proposals.'''
    original = resolve_inputs(inputs)
    definitions = [
        ('original', 'Original researched inputs', {},
         'Original 70-proposal snapshot; not changed by scenario research.'),
        ('bear', 'Bear', {
            'waccInitial': 0.09, 'waccTerminal': 0.08,
            'terminalGrowth': 0.025,
        }, 'Analyst downside: regional growth assumptions, original discount '
           'rates and margin; no terminal excess returns.'),
        ('base', 'Base', {
            'targetMargin': 0.20,
            'waccInitial': 0.075, 'waccTerminal': 0.07,
            'terminalGrowth': 0.025, 'terminalRoic': 0.20,
        }, 'Analyst assumptions: regional growth, 20% adjusted EBIT margin '
           'by year 5, 7.5% to 7% WACC and 20% terminal ROIC.'),
        ('bull', 'Bull', {
            'targetMargin': 0.22,
            'waccInitial': 0.065, 'waccTerminal': 0.065,
            'terminalGrowth': 0.03, 'terminalRoic': 0.25,
        }, 'Analyst upside: regional growth, 22% adjusted EBIT margin '
           'by year 5, 6.5% WACC and 25% terminal ROIC.'),
    ]
    scenarios = []
    for scenario_id, label, changes, note in definitions:
        changes = dict(changes)
        segment_build = None
        if scenario_id != 'original':
            segment_build = build_segments({
                'scenarioId': scenario_id,
                'terminalGrowth': changes['terminalGrowth'],
            })
            changes['growth1'] = segment_build['growth1']
            changes['growth2to5'] = segment_build['growth2to5Cagr']
            note += (
                ' Ginzu uses regional weighted growth in year 1 and the '
                'regional year-2-to-5 CAGR thereafter. This compression '
                'preserves year-1 and year-5 revenue, not every annual cash '
                'flow. Regional assumptions are not management guidance; '
                'the company pro forma/FX guidance uses a different basis.'
            )
        overrides = dict(original['overrides'])
        for key, value in changes.items():
            overrides[INPUT_CELLS[key]] = value
        if scenario_id in ('base', 'bull'):
            overrides['Input sheet!B48'] = 'Yes'
        result = evaluate_dcf({'overrides': overrides})
        result.update({
            'id': scenario_id, 'label': label,
            'kind': 'original_snapshot' if scenario_id == 'original'
            else 'analyst_assumption',
            'note': note,
            'sourceIds': segment_build['sourceIds'] if segment_build else [],
            'snapshotId': stable_hash(overrides),
            'overrides': overrides,
        })
        result['inputs'].update({key: original[key] for key in (
            'basis', 'priceAsOf', 'financialPeriod', 'sources',
        ) if key in original})
        if segment_build:
            segment_build['dcfLinked'] = True
            segment_build['linkType'] = 'growth1_and_year2to5_cagr'
            segment_build['compressionResiduals'] = [
                {
                    'year': regional['year'],
                    'regionalRevenue': regional['revenue'],
                    'ginzuRevenue': modeled['revenue'],
                    'difference': modeled['revenue'] - regional['revenue'],
                }
                for regional, modeled in zip(
                    segment_build['forecast'], result['forecast'],
                )
            ]
            result['segmentBuild'] = segment_build
        scenarios.append(result)
    return scenarios


__all__ = ['load_original_inputs', 'evaluate_dcf', 'build_scenarios',
           'validate_inputs']
