"""Decision-relevant tests for supplementary valuation calculations."""

import unittest

from models.methods import (
    calculate_ddm,
    calculate_lbo,
    comparable_methods,
    get_methods,
    percentile,
    synergy_method,
)


def operating_forecast():
    rows = []
    for year in range(1, 11):
        revenue = 619.985 * 1.05 ** year
        rows.append({'year': year, 'revenue': revenue,
                     'ebit': revenue * 0.20, 'taxRate': 0.25,
                     'fcff': revenue * 0.12, 'wacc': 0.08,
                     'discountFactor': 1.08 ** -year})
    return rows


class MethodsTest(unittest.TestCase):
    def test_ddm_zero_growth_equals_perpetuity(self):
        result = calculate_ddm(4.0, 0.0, 0.0, 0.10)
        self.assertAlmostEqual(result['value'], 40.0)

    def test_ddm_invalid_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_ddm(4.0, 0.05, 0.03, 0.03)

    def test_lbo_sources_and_uses_and_cash_sweep_reconcile(self):
        result = calculate_lbo({}, operating_forecast(), 100)
        self.assertEqual(result['status'], 'calculated')
        funding = result['sourcesAndUses']
        self.assertAlmostEqual(funding['totalSources'], funding['totalUses'])
        for row in result['schedule']:
            self.assertAlmostEqual(
                row['openingDebt'] - row['mandatoryRepayment'] - row['cashSweep'],
                row['closingDebt'],
            )
            self.assertAlmostEqual(
                row['openingCash'] + row['cashBeforePrincipal']
                - row['mandatoryRepayment'] - row['cashSweep'],
                row['closingCash'],
            )
            self.assertGreaterEqual(row['closingCash'] + 1e-9, 5.0)
            self.assertGreaterEqual(row['closingDebt'] + 1e-9, 0.0)

    def test_fixed_exit_price_reduces_return(self):
        low = calculate_lbo({}, operating_forecast(), 100)
        high = calculate_lbo({}, operating_forecast(), 150)
        self.assertAlmostEqual(low['exitEnterpriseValue'], high['exitEnterpriseValue'])
        self.assertGreater(low['irr'], high['irr'])

    def test_financing_shortfall_is_infeasible(self):
        forecast = operating_forecast()
        forecast[0]['fcff'] = -100
        result = calculate_lbo({}, forecast, 100)
        self.assertEqual(result['status'], 'infeasible')
        self.assertIsNone(result['irr'])
        self.assertGreater(result['schedule'][0]['fundingShortfall'], 0)

    def test_fee_cannot_be_negative(self):
        with self.assertRaises(ValueError):
            calculate_lbo({'lboTransactionFeeRate': -0.1}, operating_forecast(), 100)

    def test_historical_peer_gaps_are_not_filled(self):
        results = comparable_methods({}, {'records': [
            {'id': 'target', 'ticker': 'WDFC', 'currency': 'USD',
             'priceAsOf': '2025-08-29', 'eligibleForRange': True,
             'enterpriseValue': 1000, 'ebitda': 100, 'sales': 500,
             'price': 100, 'eps': 5},
        ]})
        self.assertTrue(all(method['status'] == 'missing_data' for method in results))
        self.assertTrue(all(method['value'] is None for method in results))
        self.assertTrue(all('own peer' in method['excludedRecords'][0]['reason']
                            for method in results))

    def test_inc_percentile(self):
        self.assertEqual(percentile([10, 20, 30], 0.25), 15)
        self.assertEqual(percentile([10, 20, 30], 0.5), 20)

    def test_synergy_cannot_be_added_twice(self):
        method = synergy_method({'synergiesAlreadyIncluded': True},
                                {'value': 100, 'forecast': operating_forecast()})
        self.assertEqual(method['status'], 'blocked')
        self.assertIsNone(method['value'])

    def test_get_methods_retains_distinct_types(self):
        methods = get_methods({}, [{'id': 'base', 'value': 150,
                                    'forecast': operating_forecast()}])
        by_id = {method['id']: method for method in methods}
        self.assertEqual(by_id['precedents']['rangeType'],
                         'announced_consideration_context')
        self.assertEqual(by_id['lbo']['rangeType'], 'buyer_return_hurdles')
        self.assertEqual(by_id['ddm']['rangeType'], 'analyst_dividend_scenarios')
        self.assertEqual(by_id['synergy']['rangeType'],
                         'buyer_cost_savings_scenarios')


if __name__ == '__main__':
    unittest.main()
