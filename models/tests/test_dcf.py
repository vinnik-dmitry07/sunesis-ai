'''Regression checks against the actual browser engine, including scenarios.'''

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import unittest

from models.common import load_original_inputs
from models.dcf import build_scenarios, evaluate_dcf


ROOT = Path(__file__).resolve().parents[2]


class DcfParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = load_original_inputs(ROOT / 'index.html')
        cls.scenarios = build_scenarios(cls.original)
        overrides = cls.original['overrides']
        cls.probes = [
            ('original', {}),
            ('roic20', {'Input sheet!B48': 'Yes', 'Input sheet!B49': 0.20}),
            ('margin20', {'Input sheet!B29': 0.20}),
            ('growth7', {'Input sheet!B28': 0.07}),
            ('losses', {'Input sheet!B27': -0.08,
                        'Input sheet!B29': 0.18}),
            ('nol', {'Input sheet!B61': 'Yes', 'Input sheet!B62': 300}),
            ('no_rd', {'Input sheet!B16': 'No'}),
            ('tax_hold', {'Input sheet!B59': 'Yes'}),
            ('lag0', {'Input sheet!B56': 'Yes', 'Input sheet!B57': 0}),
            ('lag2', {'Input sheet!B56': 'Yes', 'Input sheet!B57': 2}),
            ('lag3', {'Input sheet!B56': 'Yes', 'Input sheet!B57': 3}),
            ('negative_g', {'Input sheet!B68': -0.01}),
            ('year1_margin', {'Input sheet!B27': 0.15,
                             'Input sheet!B29': 0.22,
                             'Input sheet!B30': 1}),
        ]
        cls.case_maps = [
            (label, {**overrides, **changes})
            for label, changes in cls.probes
        ] + [(scenario['id'], scenario['overrides'])
             for scenario in cls.scenarios[1:]]
        program = '''
import {loadOriginal,evaluate} from './models/engine.mjs';
let input=''; for await(const chunk of process.stdin) input+=chunk;
const original=loadOriginal();
const engine=new original.WorkbookEngine(original.book);
console.log(JSON.stringify(JSON.parse(input).map(([id,overrides])=>
  ({id,...evaluate(engine,overrides)}))));
'''
        result = subprocess.run(
            ['node', '--input-type=module', '-e', program],
            input=json.dumps(cls.case_maps), text=True, capture_output=True,
            check=True, cwd=ROOT,
        )
        cls.browser = json.loads(result.stdout)

    def assert_near(self, actual, expected):
        self.assertTrue(math.isclose(
            actual, expected, rel_tol=1e-10, abs_tol=1e-9,
        ), f'{actual} != {expected}')

    def test_original_result_is_reproduced_without_tuning(self):
        result = evaluate_dcf(self.original)
        self.assert_near(result['value'], 88.15029580134913)
        self.assert_near(result['operatingValue'], 1230.6411661875882)
        self.assertEqual(self.original['originalProposalCount'], 70)

    def test_actual_engine_parity_for_every_forecast_row(self):
        mappings = {
            'growth': 2, 'revenue': 3, 'margin': 4, 'ebit': 5,
            'taxRate': 6, 'nopat': 7, 'reinvestment': 8, 'fcff': 9,
            'nol': 10, 'wacc': 12, 'discountFactor': 13, 'pvFcff': 14,
        }
        for (label, overrides), browser in zip(self.case_maps, self.browser):
            with self.subTest(case=label):
                result = evaluate_dcf({'overrides': overrides})
                for key in ('value', 'operatingValue', 'equityValue',
                            'pvTerminalValue', 'terminalShare'):
                    self.assert_near(result[key], browser[key])
                for index, row in enumerate(result['forecast']):
                    col = chr(67 + index)
                    cells = browser['rows'][index]['cells']
                    for key, row_number in mappings.items():
                        cell = cells[f'{col}{row_number}']
                        self.assertIsNone(cell['error'])
                        self.assert_near(row[key], cell['value'])

    def test_eva_uses_the_same_capital_recurrence(self):
        for label, overrides in self.case_maps:
            with self.subTest(case=label):
                result = evaluate_dcf({'overrides': overrides})
                self.assert_near(result['evaMinusDcf'], 0.0)

    def test_original_margin_is_explained_by_rd_capitalization(self):
        result = evaluate_dcf(self.original)
        expected = (103.793 + 8.7 - (8 + 6.2 + 5.1) / 3) / 619.985
        self.assert_near(result['inputs']['margin1'], expected)
        self.assert_near(result['inputs']['rdAsset'], 16.1)

    def test_inactive_terminal_roic_does_not_block_the_case(self):
        overrides = {**self.original['overrides'], 'Input sheet!B49': -1}
        self.assert_near(evaluate_dcf({'overrides': overrides})['value'],
                         self.browser[0]['value'])
        overrides['Input sheet!B48'] = 'Yes'
        with self.assertRaisesRegex(ValueError, 'ROIC'):
            evaluate_dcf({'overrides': overrides})

    def test_terminal_singularity_is_rejected(self):
        overrides = {**self.original['overrides'], 'Input sheet!B46': 0.025}
        with self.assertRaisesRegex(ValueError, 'WACC'):
            evaluate_dcf({'overrides': overrides})

    def test_scenario_override_maps_preserve_original(self):
        original = dict(self.original['overrides'])
        self.assertEqual(self.scenarios[0]['overrides'], original)
        self.assertEqual(self.original['overrides'], original)
        for scenario in self.scenarios:
            self.assert_near(
                evaluate_dcf({'overrides': scenario['overrides']})['value'],
                scenario['value'],
            )
            self.assertTrue(scenario['snapshotId'])

    def test_regional_growth_compression_preserves_reported_endpoints(self):
        self.assertNotIn('segmentBuild', self.scenarios[0])
        for scenario in self.scenarios[1:]:
            with self.subTest(case=scenario['id']):
                regional = scenario['segmentBuild']
                self.assert_near(regional['baseRevenue'], 619.985)
                for index in (0, 4):
                    self.assert_near(
                        scenario['forecast'][index]['revenue'],
                        regional['forecast'][index]['revenue'],
                    )
                self.assertEqual(regional['linkType'],
                                 'growth1_and_year2to5_cagr')
                self.assertEqual(
                    scenario['overrides']['Input sheet!B26'],
                    regional['growth1'],
                )
                self.assertEqual(
                    scenario['overrides']['Input sheet!B28'],
                    regional['growth2to5Cagr'],
                )
                self.assertGreater(
                    max(abs(row['difference'])
                        for row in regional['compressionResiduals']), 0,
                )


if __name__ == '__main__':
    unittest.main()
