'''Auditable supplementary valuation methods for the historical WD-40 case.

Money is USD millions unless explicitly labelled per share.  Inputs remain
analyst assumptions when a primary source does not establish them.  A method
with missing market data is returned with an explicit status, never a made-up
valuation range.
'''

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median


DATA_DIR = Path(__file__).resolve().parent / 'data'
REFERENCE_DATE = '2025-08-29'


def _dataset(name: str) -> dict:
    path = DATA_DIR / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number.')
    if not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number.')
    return float(value)


def _inputs(inputs: dict) -> dict:
    aliases = {
        'revenue': ('Input sheet!B11', 619.985),
        'reportedEbit': ('Input sheet!B12', 103.793),
        'debt': ('Input sheet!B15', 86.995),
        'cash': ('Input sheet!B18', 58.13),
        'shares': ('Input sheet!B21', 13.633263),
        'taxRate': ('Input sheet!B23', 0.22200027552004406),
        'terminalTaxRate': ('Input sheet!B24', 0.25),
        'margin1': ('Input sheet!B27', 0.17106811723939558),
        'terminalGrowth': ('Input sheet!B68', 0.025),
    }
    raw = inputs.get('overrides', inputs)
    result = dict(inputs)
    for key, (cell, default) in aliases.items():
        result[key] = _number(inputs.get(key, raw.get(cell, default)), key)
    defaults = {
        'dandA': 8.191,
        'dividend0': 3.76,
        'normalizedEps': 5.82,
        'interestExpense': 3.441,
        'operatingExpenses': 237.550,
        'costOfEquity': 0.09,
        'lboDebtMultiple': 5.5,
        'lboDebtRate': 0.08,
        'lboExitMultiple': 14.0,
        'lboTransactionFeeRate': 0.02,
        'lboFinancingFeeRate': 0.02,
        'lboExitFeeRate': 0.02,
        'lboMinimumCash': 5.0,
        'lboAmortizationRate': 0.01,
        'lboSweepRate': 1.0,
    }
    for key, default in defaults.items():
        result[key] = _number(inputs.get(key, default), key)
    if result['shares'] <= 0 or result['revenue'] <= 0:
        raise ValueError('Shares and revenue must be positive.')
    if not 0 <= result['taxRate'] <= 1:
        raise ValueError('Tax rate must be between zero and one.')
    if not 0 <= result['terminalTaxRate'] <= 1:
        raise ValueError('Terminal tax rate must be between zero and one.')
    for key in ['debt', 'cash', 'dandA', 'dividend0', 'interestExpense',
                'lboTransactionFeeRate', 'lboFinancingFeeRate', 'lboExitFeeRate']:
        if result[key] < 0:
            raise ValueError(f'{key} cannot be negative.')
    return result


def percentile(values: list[float], probability: float) -> float:
    '''Linear interpolation between ordered observations (Excel INC basis).'''
    if not values or not 0 <= probability <= 1:
        raise ValueError('A percentile needs observations and a valid probability.')
    ordered = sorted(_number(value, 'observation') for value in values)
    position = (len(ordered) - 1) * probability
    left = math.floor(position)
    right = math.ceil(position)
    return ordered[left] + (ordered[right] - ordered[left]) * (position - left)


def _summary(method: dict) -> dict:
    values = [s['value'] for s in method['scenarios']
              if isinstance(s.get('value'), (int, float))]
    method['live'] = False
    method['basis'] = 'Retrospective FY2025; historical reference price.'
    method['currency'] = 'USD'
    method['unit'] = 'USD/share'
    method['value'] = median(values) if values else None
    method['low'] = min(values) if values else None
    method['base'] = method['value']
    method['high'] = max(values) if values else None
    return method


def comparable_methods(inputs: dict, peer_data: dict | None = None) -> list[dict]:
    '''Apply only explicitly eligible historical, same-basis peer observations.'''
    facts = _inputs(inputs)
    data = peer_data if peer_data is not None else _dataset('peers.json')
    records = data.get('records', [])
    methods = []
    definitions = [
        ('ev-ebitda', 'Trading peers · EV/EBITDA', 'ebitda',
         facts['reportedEbit'] + facts['dandA'], True),
        ('pe', 'Trading peers · P/E', 'eps', facts['normalizedEps'], False),
        ('ev-sales', 'Trading peers · EV/sales', 'sales', facts['revenue'], True),
    ]
    for suffix, label, metric, target_metric, enterprise_basis in definitions:
        observations = []
        excluded = []
        for record in records:
            reason = None
            if record.get('ticker') == 'WDFC':
                reason = 'The valuation target cannot be its own peer.'
            elif record.get('priceAsOf') != REFERENCE_DATE:
                reason = 'Historical price at the reference date is unverified.'
            elif record.get('currency') != 'USD':
                reason = 'A consistent USD basis is required.'
            elif not record.get('eligibleForRange', False):
                reason = record.get('missingReason', 'Observation is not verified.')
            denominator = record.get(metric)
            numerator = record.get('enterpriseValue' if enterprise_basis else 'price')
            if reason is None and (not isinstance(denominator, (int, float))
                                   or denominator <= 0
                                   or not isinstance(numerator, (int, float))
                                   or numerator <= 0):
                reason = f'Missing positive {metric} or valuation numerator.'
            if reason:
                excluded.append({'id': record.get('id'), 'reason': reason})
            else:
                observations.append({
                    'id': record['id'], 'multiple': numerator / denominator,
                    'sourceIds': record.get('sourceIds', []),
                })
        scenarios = []
        if len(observations) >= 3:
            multiples = [row['multiple'] for row in observations]
            for case_id, probability, name in [
                    ('low', 0.25, '25th percentile'),
                    ('base', 0.50, 'Median'),
                    ('high', 0.75, '75th percentile')]:
                multiple = percentile(multiples, probability)
                numerator = multiple * target_metric
                equity_value = (numerator + facts['cash'] - facts['debt']
                                if enterprise_basis else numerator)
                value = equity_value / facts['shares'] if enterprise_basis else numerator
                scenarios.append({
                    'id': case_id, 'label': name, 'value': value,
                    'multiple': multiple, 'metric': metric,
                    'targetMetric': target_metric,
                    'status': 'calculated', 'schedule': observations,
                    'assumptions': {'netDebt': facts['debt'] - facts['cash'],
                                    'shares': facts['shares'],
                                    'ebitdaDefinition': 'Operating EBIT plus cash-flow D&A; not issuer adjusted EBITDA'},
                })
        methods.append(_summary({
            'id': f'comps-{suffix}', 'label': label, 'kind': 'comps',
            'rangeType': 'observed_multiple_percentiles',
            'status': 'calculated' if scenarios else 'missing_data',
            'scenarios': scenarios, 'observations': observations,
            'excludedRecords': excluded,
            'sourceIds': sorted({source for record in records
                                 for source in record.get('sourceIds', [])}),
            'limitations': [
                'At least three verified same-date observations are required.',
                'Percentiles are descriptive observations, not business scenarios.',
                'The WD-40 per-share denominator is a valuation dilution proxy.',
            ],
        }))
    return methods


def precedent_method(inputs: dict, deal_data: dict | None = None) -> dict:
    '''Keep announced consideration multiples distinct from clean EV multiples.'''
    facts = _inputs(inputs)
    data = deal_data if deal_data is not None else _dataset('deals.json')
    rows = []
    for record in data.get('records', []):
        value, ebitda = record.get('consideration'), record.get('ebitda')
        if record.get('eligibleForContext') and value and ebitda and ebitda > 0:
            rows.append({**record, 'multiple': value / ebitda})
    scenarios = []
    if len(rows) >= 3:
        multiples = [row['multiple'] for row in rows]
        target = facts['reportedEbit'] + facts['dandA']
        for case_id, probability, label in [
                ('low', 0, 'Observed minimum'),
                ('base', 0.5, 'Observed median'),
                ('high', 1, 'Observed maximum')]:
            multiple = percentile(multiples, probability)
            illustrative_ev = target * multiple
            scenarios.append({
                'id': case_id, 'label': label,
                'value': (illustrative_ev + facts['cash'] - facts['debt']) / facts['shares'],
                'multiple': multiple, 'targetEbitda': target,
                'status': 'indicative', 'schedule': rows,
                'assumptions': {'targetEbitda': 'Operating EBIT plus cash-flow D&A; not issuer adjusted EBITDA',
                                'netDebt': facts['debt'] - facts['cash'],
                                'shares': facts['shares']},
            })
    return _summary({
        'id': 'precedents', 'label': 'Acquisition context · consideration/EBITDA',
        'kind': 'precedents', 'rangeType': 'announced_consideration_context',
        'status': 'indicative' if scenarios else 'missing_data',
        'scenarios': scenarios, 'observations': rows,
        'sourceIds': sorted({source for row in rows for source in row['sourceIds']}),
        'limitations': [
            'Announced acquisition consideration is not a verified net-debt-adjusted EV.',
            'Adjacent oral-care and personal-care brands differ from maintenance products.',
            'Periods, growth and deal tax structures differ; no tax shield is subtracted.',
            'This contextual range does not establish a WD-40 control valuation.',
        ],
    })


def calculate_lbo(inputs: dict, forecast: list[dict], entry_price: float,
                  target_irr: float = 0.20, years: int = 5) -> dict:
    '''Fixed-exit-multiple LBO with opening-debt interest and a cash sweep.

    FCFF is the supplied unlevered operating-case proxy. EBITDA used for debt
    and exit removes a disclosed constant-margin R&D adjustment before adding
    D&A at its historical share of sales. No interim sponsor distributions or
    additional equity calls are assumed; funding shortfalls make a case infeasible.
    '''
    facts = _inputs(inputs)
    price = _number(entry_price, 'entry_price')
    if price <= 0 or years <= 0 or len(forecast) < years:
        raise ValueError('A positive entry price and a complete hold-period forecast are required.')
    debt_multiple = facts['lboDebtMultiple']
    debt_rate = facts['lboDebtRate']
    exit_multiple = facts['lboExitMultiple']
    sweep_rate = facts['lboSweepRate']
    if (debt_multiple < 0 or debt_rate < 0 or exit_multiple <= 0
            or not 0 <= sweep_rate <= 1 or facts['lboMinimumCash'] < 0
            or facts['lboAmortizationRate'] < 0):
        raise ValueError('Invalid debt, exit, cash or repayment assumptions.')
    ebitda0 = facts['reportedEbit'] + facts['dandA']
    new_debt = ebitda0 * debt_multiple
    entry_equity_value = price * facts['shares']
    entry_ev = entry_equity_value + facts['debt'] - facts['cash']
    minimum_cash = facts['lboMinimumCash']
    target_cash_used = max(0.0, facts['cash'] - minimum_cash)
    initial_cash = facts['cash'] - target_cash_used
    transaction_fees = max(0.0, entry_ev) * facts['lboTransactionFeeRate']
    financing_fees = new_debt * facts['lboFinancingFeeRate']
    cash_top_up = max(0.0, minimum_cash - initial_cash)
    total_uses = (entry_equity_value + facts['debt'] + transaction_fees
                  + financing_fees + cash_top_up)
    equity_in = total_uses - new_debt - target_cash_used
    sources_uses = {
        'equityPurchase': entry_equity_value, 'refinancedDebt': facts['debt'],
        'transactionFees': transaction_fees, 'financingFees': financing_fees,
        'cashTopUp': cash_top_up, 'totalUses': total_uses,
        'newDebt': new_debt, 'targetCashUsed': target_cash_used,
        'sponsorEquity': equity_in,
        'totalSources': new_debt + target_cash_used + equity_in,
    }
    assumptions = {
        'holdYears': years, 'targetIrr': target_irr, 'debtMultiple': debt_multiple,
        'debtRate': debt_rate, 'fixedExitMultiple': exit_multiple,
        'minimumCash': minimum_cash, 'cashSweepRate': sweep_rate,
        'annualMandatoryAmortization': new_debt * facts['lboAmortizationRate'],
        'exitFeeRate': facts['lboExitFeeRate'],
        'transactionFeeRate': facts['lboTransactionFeeRate'],
        'financingFeeRate': facts['lboFinancingFeeRate'],
        'ebitda0': ebitda0, 'dandA0': facts['dandA'],
        'ebitdaDefinition': 'Operating EBIT plus cash-flow D&A; not issuer adjusted EBITDA',
        'rAndDAdjustmentMargin': facts['margin1'] - facts['reportedEbit'] / facts['revenue'],
        'dandAMargin': facts['dandA'] / facts['revenue'],
        'cashFlowBasis': 'Valuation FCFF proxy; no independent lender underwriting',
        'ebitdaBridge': 'Remove constant-margin base R&D capitalization uplift; add historical D&A/sales',
        'interimSponsorDistributions': False,
    }
    result = {'entryPrice': price, 'sourcesAndUses': sources_uses,
              'assumptions': assumptions, 'schedule': [], 'irr': None,
              'moic': None, 'status': 'infeasible', 'meetsHurdle': False}
    if equity_in <= 0:
        result['reason'] = 'Sponsor equity must be positive.'
        return result
    debt, cash = new_debt, initial_cash + cash_top_up
    for year, row in enumerate(forecast[:years], 1):
        revenue = _number(row['revenue'], 'forecast revenue')
        ebit = _number(row['ebit'], 'forecast EBIT')
        fcff = _number(row['fcff'], 'forecast FCFF')
        tax_rate = float(row.get('taxRate', facts['taxRate']))
        reported_ebit_proxy = ebit - revenue * assumptions['rAndDAdjustmentMargin']
        ebitda = float(row.get('ebitda', reported_ebit_proxy
                              + revenue * assumptions['dandAMargin']))
        interest = debt * debt_rate
        tax_shield = min(interest, max(0.0, reported_ebit_proxy)) * tax_rate
        cash_before_principal = fcff - interest + tax_shield
        available = cash + cash_before_principal - minimum_cash
        mandatory = min(debt, new_debt * facts['lboAmortizationRate'])
        feasible = available + 1e-9 >= mandatory
        mandatory_paid = mandatory if feasible else max(0.0, available)
        additional = (min(debt - mandatory_paid,
                          max(0.0, available - mandatory_paid) * sweep_rate)
                      if feasible else 0.0)
        closing_debt = debt - mandatory_paid - additional
        closing_cash = cash + cash_before_principal - mandatory_paid - additional
        result['schedule'].append({
            'year': year, 'revenue': revenue, 'ebit': ebit,
            'reportedEbitProxy': reported_ebit_proxy, 'ebitda': ebitda,
            'fcff': fcff, 'taxRate': tax_rate,
            'openingDebt': debt, 'interest': interest,
            'interestTaxShield': tax_shield,
            'cashBeforePrincipal': cash_before_principal,
            'mandatoryRepayment': mandatory_paid, 'cashSweep': additional,
            'closingDebt': closing_debt, 'openingCash': cash,
            'closingCash': closing_cash, 'fundingShortfall': max(0.0, mandatory - available),
        })
        if not feasible:
            result['reason'] = f'Year {year} cannot fund minimum cash and mandatory repayment.'
            return result
        debt, cash = closing_debt, closing_cash
    exit_ebitda = result['schedule'][-1]['ebitda']
    exit_ev = exit_ebitda * exit_multiple
    exit_fees = exit_ev * facts['lboExitFeeRate']
    equity_out = max(0.0, exit_ev - exit_fees - debt + cash)
    moic = equity_out / equity_in
    irr = moic ** (1 / years) - 1
    result.update({'status': 'calculated', 'exitEbitda': exit_ebitda,
                   'exitEnterpriseValue': exit_ev, 'exitFees': exit_fees,
                   'exitEquity': equity_out, 'moic': moic, 'irr': irr,
                   'meetsHurdle': irr >= target_irr})
    return result


def lbo_method(inputs: dict, forecast: list[dict]) -> dict:
    scenarios = []
    if len(forecast) >= 5:
        for case_id, hurdle in [('low', 0.25), ('base', 0.20), ('high', 0.175)]:
            grid = [calculate_lbo(inputs, forecast, price, hurdle)
                    for price in range(50, 401, 5)]
            feasible = [case for case in grid if case['meetsHurdle']]
            if not feasible:
                scenarios.append({'id': case_id, 'label': f'{hurdle:.1%} return hurdle',
                                  'value': None, 'status': 'no_solution_in_grid',
                                  'note': 'No qualifying entry price from $50 to $400.',
                                  'grid': grid, 'schedule': []})
                continue
            best = max(feasible, key=lambda case: case['entryPrice'])
            boundary = best['entryPrice'] == 400
            if not boundary:
                low, high = best['entryPrice'], best['entryPrice'] + 5
                for _ in range(30):
                    midpoint = (low + high) / 2
                    candidate = calculate_lbo(inputs, forecast, midpoint, hurdle)
                    if candidate['meetsHurdle']:
                        low, best = midpoint, candidate
                    else:
                        high = midpoint
            scenarios.append({
                **best, 'id': case_id, 'label': f'{hurdle:.1%} return hurdle',
                'value': best['entryPrice'], 'status': 'grid_boundary' if boundary else 'illustrative',
                'note': 'At least the upper grid bound.' if boundary else 'Maximum tested fixed-exit entry price.',
                'sourceIds': ['wdfc25-is', 'wdfc25-cf'],
            })
    return _summary({
        'id': 'lbo', 'label': 'LBO · sponsor ability to pay', 'kind': 'lbo',
        'rangeType': 'buyer_return_hurdles',
        'status': 'illustrative' if any(s.get('value') is not None for s in scenarios) else 'missing_data',
        'scenarios': scenarios, 'sourceIds': ['wdfc25-is', 'wdfc25-cf'],
        'limitations': [
            'Leverage, debt pricing, fees and exit multiple are analyst assumptions.',
            'Forecast FCFF is a valuation proxy; no lender-approved financing is asserted.',
            'Forward reported EBITDA uses an explicit constant-margin R&D and D&A bridge.',
            'Entry EBITDA is operating EBIT plus cash-flow D&A, not the issuer adjusted EBITDA measure.',
            'No interim sponsor distributions or additional equity contributions are modeled.',
            'The per-share denominator is the case dilution proxy.',
        ],
    })


def calculate_ddm(dividend: float, growth: float, terminal_growth: float,
                  cost_of_equity: float, years: int = 10) -> dict:
    for value, label in [(dividend, 'dividend'), (growth, 'growth'),
                         (terminal_growth, 'terminal growth'),
                         (cost_of_equity, 'cost of equity')]:
        _number(value, label)
    if dividend < 0 or growth <= -1 or terminal_growth <= -1 or years < 1:
        raise ValueError('Invalid dividend, growth or forecast horizon.')
    if cost_of_equity <= terminal_growth or cost_of_equity <= 0:
        raise ValueError('Cost of equity must exceed terminal growth and zero.')
    schedule = []
    for year in range(1, years + 1):
        payment = dividend * (1 + growth) ** year
        discount_factor = (1 + cost_of_equity) ** -year
        schedule.append({'year': year, 'dividend': payment,
                         'discountFactor': discount_factor,
                         'pvDividend': payment * discount_factor})
    terminal_dividend = schedule[-1]['dividend'] * (1 + terminal_growth)
    terminal_value = terminal_dividend / (cost_of_equity - terminal_growth)
    pv_terminal = terminal_value * schedule[-1]['discountFactor']
    return {'value': sum(row['pvDividend'] for row in schedule) + pv_terminal,
            'schedule': schedule, 'terminalDividend': terminal_dividend,
            'terminalValue': terminal_value, 'pvTerminalValue': pv_terminal,
            'assumptions': {'dividend0': dividend, 'growth': growth,
                            'terminalGrowth': terminal_growth,
                            'costOfEquity': cost_of_equity, 'years': years}}


def ddm_method(inputs: dict, forecast: list[dict]) -> dict:
    facts = _inputs(inputs)
    scenarios = []
    for case_id, growth, spread in [('low', 0.05, 0.005), ('base', 0.07, 0),
                                  ('high', 0.09, -0.005)]:
        result = calculate_ddm(facts['dividend0'], growth, facts['terminalGrowth'],
                               facts['costOfEquity'] + spread)
        coverage = []
        for row, operating in zip(result['schedule'], forecast):
            interest = facts['interestExpense']
            tax_rate = float(operating.get('taxRate', facts['taxRate']))
            fcfe_proxy = float(operating['fcff']) - interest * (1 - tax_rate)
            distribution = row['dividend'] * facts['shares']
            coverage.append({'year': row['year'], 'dividendsTotal': distribution,
                             'fcfeProxy': fcfe_proxy,
                             'covered': distribution <= fcfe_proxy})
        uncovered = [row['year'] for row in coverage if not row['covered']]
        scenarios.append({
            **result, 'id': case_id, 'label': f'{growth:.0%} dividend growth',
            'status': 'payout_shortfall' if uncovered else 'illustrative',
            'coverage': coverage, 'uncoveredYears': uncovered,
            'sourceIds': ['wdfc25-release'],
        })
    return _summary({
        'id': 'ddm', 'label': 'DDM · assumed dividend policy', 'kind': 'ddm',
        'rangeType': 'analyst_dividend_scenarios', 'status': 'illustrative',
        'scenarios': scenarios, 'sourceIds': ['wdfc25-release'],
        'limitations': [
            'Dividend growth and cost of equity are explicit analyst assumptions, not a CAPM estimate.',
            'The $3.76 dividend is an annualized quarterly run rate, not total shareholder distributions.',
            'Payout coverage uses a constant-debt FCFE proxy; buybacks are not separately valued.',
            'Terminal dividend growth uses the operating case terminal growth.',
        ],
    })


def synergy_method(inputs: dict, scenario: dict) -> dict:
    facts = _inputs(inputs)
    rows = scenario.get('forecast', [])[:10]
    scenarios = []
    if rows and not inputs.get('synergiesAlreadyIncluded', False):
        for case_id, fraction in [('low', 0.10), ('base', 0.20), ('high', 0.30)]:
            savings0 = facts['operatingExpenses'] * fraction
            upfront_cost = savings0
            schedule = []
            for year, row in enumerate(rows, 1):
                run_rate = savings0 * float(row['revenue']) / facts['revenue']
                ramp = min(1.0, year / 3)
                savings = run_rate * ramp
                tax_rate = float(row.get('taxRate', facts['taxRate']))
                after_tax = savings * (1 - tax_rate)
                discount_factor = float(row['discountFactor'])
                schedule.append({'year': year, 'revenue': row['revenue'],
                                 'preTaxSavings': savings, 'ramp': ramp,
                                 'afterTaxSavings': after_tax,
                                 'discountFactor': discount_factor,
                                 'pvSavings': after_tax * discount_factor})
            discount = float(rows[-1].get('wacc', inputs.get('waccTerminal', 0.08)))
            growth = facts['terminalGrowth']
            if discount <= growth:
                continue
            terminal_savings = (savings0 * float(rows[-1]['revenue']) / facts['revenue']
                                * (1 + growth) * (1 - facts['terminalTaxRate']))
            terminal_value = terminal_savings / (discount - growth)
            pv_terminal = terminal_value * float(rows[-1]['discountFactor'])
            pv_synergy = sum(row['pvSavings'] for row in schedule) + pv_terminal - upfront_cost
            scenarios.append({
                'id': case_id, 'label': f'{fraction:.0%} incremental cost savings',
                'value': float(scenario['value']) + pv_synergy / facts['shares'],
                'status': 'illustrative', 'pvSynergies': pv_synergy,
                'standaloneValue': scenario['value'], 'schedule': schedule,
                'terminalValue': terminal_value, 'pvTerminalValue': pv_terminal,
                'assumptions': {'costSavingsFraction': fraction,
                                'costBase': facts['operatingExpenses'],
                                'rampYears': 3, 'upfrontImplementationCost': upfront_cost,
                                'terminalGrowth': growth, 'terminalWacc': discount,
                                'taxTreatment': 'Savings after tax; implementation cost has no assumed tax shield',
                                'scope': 'Incremental to the selected standalone case'},
                'sourceIds': ['wdfc25-release'],
            })
    return _summary({
        'id': 'synergy', 'label': 'Strategic buyer · incremental synergies',
        'kind': 'synergy', 'rangeType': 'buyer_cost_savings_scenarios',
        'status': 'illustrative' if scenarios else 'blocked',
        'scenarios': scenarios, 'sourceIds': ['wdfc25-release'],
        'limitations': [
            'No identified buyer or verified synergy plan is asserted.',
            'Savings are incremental to standalone margins; no acquired growth is added.',
            'A one-year run-rate implementation cost is paid up front without an assumed tax shield.',
            'No acquisition premium allocation or negotiated seller share is assumed.',
        ],
    })


def get_methods(inputs: dict, dcf_scenarios: list[dict]) -> list[dict]:
    '''Return comparable ranges and buyer/payout views without hiding data gaps.'''
    chosen = next((case for case in dcf_scenarios if case.get('id') == 'base'),
                  next((case for case in dcf_scenarios if case.get('id') == 'original'),
                       dcf_scenarios[0] if dcf_scenarios else {}))
    selected_inputs = {**inputs, **chosen.get('inputs', {})}
    forecast = chosen.get('forecast', [])
    return (comparable_methods(inputs) + [precedent_method(inputs),
            lbo_method(selected_inputs, forecast),
            ddm_method(selected_inputs, forecast),
            synergy_method(selected_inputs, chosen)])
