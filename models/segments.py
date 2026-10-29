'''Aggregate disclosed WD-40 regions under explicit analyst growth assumptions.'''

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REGIONAL_GROWTH = {
    'bear': {'americas': 0.01, 'eimea': 0.04, 'asiaPacific': 0.06},
    'base': {'americas': 0.04, 'eimea': 0.07, 'asiaPacific': 0.10},
    'bull': {'americas': 0.06, 'eimea': 0.09, 'asiaPacific': 0.13},
}


def load_research() -> dict[str, Any]:
    '''Read the pinned evidence and definitions beside the model sources.'''
    path = Path(__file__).parent / 'data' / 'research.json'
    return json.loads(path.read_text(encoding='utf-8'))


def build_segments(inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    '''Build a regional illustration without altering the active Ginzu case.

    ``regionGrowth`` and ``divestmentRevenueByRegion`` are analyst inputs.
    Amounts are USD millions, with FX held constant as a modeling assumption.
    An explicitly provided revenue removal occurs before first-year growth.
    No sale proceeds or profit effects are inferred from that revenue removal.
    '''
    inputs = inputs or {}
    research = load_research()
    scenario = inputs.get('scenarioId', inputs.get('scenario', 'base'))
    if scenario not in REGIONAL_GROWTH:
        raise ValueError(f'Unknown regional scenario: {scenario}.')
    regions = research['operatingFacts']['regions']
    revenues = {region['id']: region['revenue'] for region in regions}
    original_total = sum(revenues.values())
    rates = dict(REGIONAL_GROWTH[scenario])
    rates.update(inputs.get('regionGrowth', {}))
    if set(rates) != set(revenues):
        raise ValueError('Regional growth keys must match disclosed regions.')
    for region, rate in rates.items():
        if not math.isfinite(rate) or rate <= -1:
            raise ValueError(f'{region} growth must be finite and above -100%.')
    removed = inputs.get('divestmentRevenueByRegion', {})
    if set(removed) - set(revenues):
        raise ValueError('Unknown region in divestment revenue adjustment.')
    for region, amount in removed.items():
        if not math.isfinite(amount) or not 0 <= amount < revenues[region]:
            raise ValueError(f'{region} revenue removal is outside its base.')
        revenues[region] -= amount
    terminal_growth = inputs.get('terminalGrowth', 0.025)
    if not math.isfinite(terminal_growth) or terminal_growth <= -1:
        raise ValueError('Terminal growth must be finite and above -100%.')
    horizon = inputs.get('horizon', 10)
    if not isinstance(horizon, int) or not 5 <= horizon <= 10:
        raise ValueError('Forecast horizon must be an integer from 5 to 10.')
    rows = []
    prior_total = original_total
    for year in range(1, horizon + 1):
        active_rates = {
            region: rate if year <= 5 else
            rate - (rate - terminal_growth) * (year - 5) / 5
            for region, rate in rates.items()
        }
        revenues = {
            region: value * (1 + active_rates[region])
            for region, value in revenues.items()
        }
        total = sum(revenues.values())
        rows.append({
            'year': year, 'regions': dict(revenues),
            'regionGrowth': active_rates, 'revenue': total,
            'growth': total / prior_total - 1,
        })
        prior_total = total
    year_one = rows[0]['revenue']
    year_five = rows[4]['revenue']
    return {
        'scenarioId': scenario,
        'kind': 'regional_analyst_illustration',
        'units': 'USD millions',
        'basePeriod': 'FY2025',
        'baseRevenue': original_total,
        'baseRegions': {region['id']: region['revenue'] for region in regions},
        'regionGrowthAssumptions': rates,
        'divestmentRevenueByRegion': removed,
        'forecast': rows,
        'growth1': year_one / original_total - 1,
        'growth2to5Cagr': (year_five / year_one) ** 0.25 - 1,
        'sourceIds': ['wd40-fy25-operating-research'],
        'dcfLinked': False,
        'basis': ('Reported regional FY2025 base, constant FX assumption. '
                  'Regional growth is analyst-selected; this is not company '
                  'guidance or an automatic replacement for Ginzu inputs.'),
        'guidanceComparison': (
            'Original FY2026 guidance uses a different pro forma perimeter. '
            'A direct comparison requires divestment and FX reconciliation.'
        ),
        'limitations': [
            'No inferred regional-product forecast matrix.',
            'No divestment revenue removal unless explicitly supplied.',
            'No sale proceeds, tax or profit effect inferred from revenue.',
            'A single exported CAGR preserves endpoints, not annual cash flows.',
        ],
    }
