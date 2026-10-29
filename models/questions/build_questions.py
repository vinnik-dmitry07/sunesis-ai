'''Build a curated WD-40 question tree from actual benchmark records.'''

import hashlib
import json
from pathlib import Path

from extract import DEFAULT_DATA, extract


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name('wd40_questions.json')

PARENTS = [
    ('revenue', 'What supports the revenue forecast?',
     'Separate the audited base, reported growth and forward expectations.'),
    ('margins', 'What supports the operating-margin forecast?',
     'Reconcile reported EBIT, R&D adjustments and the target margin.'),
    ('capital', 'How much investment does growth require?',
     'Distinguish observed capital spending from the sales-to-capital assumption.'),
    ('cash', 'How much accounting profit becomes distributable cash?',
     'Trace reinvestment and cash-flow conversion before inferring value.'),
    ('tax', 'Which tax effects will recur?',
     'Separate the reported tax benefit, normalization and terminal rate.'),
    ('discount', 'What supports the discount rates?',
     'Identify explicit rate assumptions and the historical evidence still needed.'),
    ('terminal', 'What must remain true beyond year ten?',
     'Expose terminal growth, excess returns and their contribution to value.'),
    ('financing', 'What can a financed buyer afford?',
     'Reconcile debt-like items, liquidity and the return requirement.'),
    ('payouts', 'How does operating value reach each shareholder?',
     'Review cash, dilution and the sustainability of shareholder distributions.'),
    ('risks', 'Which unresolved facts could change the investment decision?',
     'Prioritize missing evidence, business changes and testable outcomes.'),
]


def main():
    html = (ROOT / 'index.html').read_text()
    case = json.JSONDecoder().raw_decode(html.split('const BUNDLED_CASE=', 1)[1])[0]
    book = json.JSONDecoder().raw_decode(html.split('const BUNDLED_BOOK=', 1)[1])[0]
    inputs = {p['cell']: p['value'] for p in case['proposals']}
    records, counts = extract(DEFAULT_DATA)
    lookup = {(row['source'], row['recordId']): row for row in records}
    manifest = json.loads((DEFAULT_DATA / 'manifest.json').read_text())
    source_lookup = {source['id']: source for source in manifest['sources']}
    revenue = inputs['Input sheet!B11']
    prior_revenue = inputs['Input sheet!C11']
    ebit = inputs['Input sheet!B12']
    margin = ebit / revenue
    normalized_tax = inputs['Input sheet!B23']
    questions = []

    def add(identifier, parent, question, category, source, record_id, cells,
            source_ids, answer, status='answered', note='', resolution=None):
        record = lookup[(source, str(record_id))]
        benchmark = {
            'name': source,
            'recordId': str(record_id),
            'originalQuestion': record['originalQuestion'],
            'adapted': True,
            'version': 'sha256:' + record['sourceHash'],
            'revision': source_lookup[source]['revision'],
            'url': record['sourceUrl'],
            'adaptation': (
                'Analyst-authored WD-40 adaptation of the cited question or '
                'task; not an original benchmark item.'
            ),
        }
        if record.get('originalText'):
            benchmark.update({
                'originalText': record['originalText'],
                'cause': record.get('cause'),
                'effect': record.get('effect'),
                'adaptation': (
                    'Analyst-authored question inspired by a cause-effect '
                    'annotation; the source contains spans, not a question.'
                ),
            })
        item = {
            'id': identifier,
            'parentId': parent,
            'question': question,
            'category': category,
            'benchmark': benchmark,
            'cellIds': cells,
            'sourceIds': source_ids,
            'answer': answer,
            'status': status,
            'note': note,
            'answerBasis': (
                'Original FY2025 proposal snapshot; linked cells expose the '
                'current model separately.'
            ),
        }
        if resolution:
            item['resolution'] = resolution
        questions.append(item)

    fb = 'financebench'
    pe = 'pe-bench'
    fl = 'finlfqa'
    add('revenue-base', 'revenue', 'What FY2025 revenue anchors the WD-40 model?',
        'fact', pe, 'voltaic-01-historicals',
        ['Input sheet!B11', 'Input sheet!C11'], ['wdfc25-is'],
        (f'The original audited-input proposals record FY2025 revenue of '
         f'${revenue:.3f}m and FY2024 revenue of ${prior_revenue:.3f}m. '
         'Both are USD millions.'))
    add('revenue-growth', 'revenue', (
        'What was reported FY2025 revenue growth, and is the forecast the same '
        'claim?'
    ),
        'fact', fb, 'financebench_id_01198',
        ['Input sheet!B11', 'Input sheet!C11', 'Input sheet!B26', 'Input sheet!B28'],
        ['wdfc25-is'],
        (f'Reported growth from the original revenue proposals is '
         f'{(revenue / prior_revenue - 1) * 100:.4f}%. '
         'The 5% next-year and years-2–5 inputs are explicit forward '
         'assumptions, not observed FY2026 growth.'))
    add('revenue-resolution', 'revenue', (
        'Will WD-40 FY2026 reported net sales exceed the FY2025 reported base '
        'by at least 5%?'
    ),
        'forecast', pe, 'voltaic-07-operating-model',
        ['Input sheet!B11', 'Input sheet!B26'], ['wdfc25-is'],
        (
            'No contemporaneous probability or FY2026 outcome is supplied in '
            'this historical case. This is a retrospective resolution template,'
            ' not an advance forecast record.'
        ),
        'unresolved_forecast',
        resolution={'metric': 'Reported consolidated net sales, USD',
                    'period': 'FY2026 versus FY2025',
                    'threshold': 'FY2026 / FY2025 - 1 >= 0.05',
                    'source': 'WD-40 FY2026 annual report',
                    'resolveAfter': 'FY2026 annual report publication',
                    'retrospectiveTemplate': True})

    add('margin-reported', 'margins', 'What is WD-40 FY2025 reported operating margin?',
        'fact', fb, 'financebench_id_01226',
        ['Input sheet!B11', 'Input sheet!B12'], ['wdfc25-is'],
        (f'${ebit:.3f}m reported EBIT / ${revenue:.3f}m revenue = '
         f'{margin * 100:.4f}%. This is the reported EBIT margin before '
         'the model’s R&D adjustment.'))
    add('margin-rd-bridge', 'margins', (
        'Why does the original model use a 17.1068% operating margin rather '
        'than the reported margin?'
    ),
        'assumption', pe, 'voltaic-04-ebitda-bridge',
        ['Input sheet!B12', 'Input sheet!B27', 'Input sheet!B29',
         'R& D converter!F6', 'R& D converter!B6'],
        ['wdfc25-is', 'wdfc25-rd', 'wdfc23-rd'],
        (
            'The original case capitalizes R&D over a three-year assumed life. '
            'Its adjusted EBIT adds current R&D and subtracts modeled '
            'amortization. The retained 17.1068% next-year and target margins '
            'use that adjusted base. R&D capitalization and flat future margins'
            ' are modeling choices.'
        ),
        'assumption')
    add('margin-target', 'margins', (
        'What evidence would justify a 20% adjusted EBIT margin instead of the '
        'original flat margin?'
    ),
        'assumption', pe, 'voltaic-07-operating-model',
        ['Input sheet!B27', 'Input sheet!B29', 'Input sheet!B30'],
        ['wdfc25-is', 'wdfc25-rd'],
        (
            'A higher target requires a bridge from sales and gross profit '
            'through operating expenses and R&D treatment. The original case '
            'provides no sourced 20% EBIT target. An EBITDA target alone does '
            'not establish an EBIT margin.'
        ),
        'needs_evidence')

    add('capital-capex', 'capital', (
        'What was WD-40 FY2025 capital expenditure, and what percentage of '
        'revenue was it?'
    ),
        'fact', fb, 'financebench_id_03029',
        ['Input sheet!B11'], ['wdfc25-cf'],
        (
            'The original proposal set does not include a separate verified '
            'capex input. Extract purchases of property, plant and equipment '
            'from the FY2025 cash-flow statement, document the sign convention,'
            ' then divide by revenue. Do not substitute the model’s forecast '
            'reinvestment.'
        ),
        'needs_evidence')
    add('capital-turnover', 'capital', (
        'Is the model’s 2.0× sales-to-capital ratio '
        'observed or assumed?'
    ),
        'assumption', fb, 'financebench_id_00499',
        ['Input sheet!B31', 'Input sheet!B32', 'Input sheet!B14',
         'Input sheet!B15', 'Input sheet!B18'],
        ['wdfc25-bs', 'wdfc25-leases'],
        (
            'Both forecast sales-to-capital ratios are explicit 2.0× '
            'assumptions. Historical revenue divided by book capital is a scale'
            ' comparison, not a direct observation of the incremental '
            'reinvestment needed for future growth.'
        ),
        'assumption')
    add('capital-rd', 'capital', (
        'Which R&D amounts support the model’s '
        'capitalization schedule?'
    ),
        'fact', pe, 'voltaic-01-historicals',
        ['R& D converter!B6', 'R& D converter!B7', 'R& D converter!B8',
         'R& D converter!B9', 'R& D converter!F6'],
        ['wdfc25-rd', 'wdfc23-rd'],
        (
            'The recorded disclosures are $8.7m, $8.0m and $6.2m for '
            'FY2025–FY2023, and $5.1m for FY2022. The assumed three-year useful'
            ' life determines which history enters amortization; it is not a '
            'disclosed accounting useful life for an R&D asset.'
        ))

    add('cash-fcff', 'cash', (
        'What modeled free cash flow is generated in '
        'the first forecast year?'
    ),
        'assumption', fb, 'financebench_id_04854',
        ['Valuation output!C7', 'Valuation output!C8', 'Valuation output!C9'],
        ['wdfc25-is'],
        (
            'Inspect modeled NOPAT less modeled reinvestment in the linked '
            'forecast cells. These are forecast FCFF values, distinct from '
            'historical cash from operations less capex.'
        ),
        'assumption')
    add('cash-conversion', 'cash', (
        'Did historical free-cash-flow conversion improve from FY2024 to '
        'FY2025?'
    ),
        'fact', fb, 'financebench_id_00591',
        ['Input sheet!B11', 'Input sheet!C11', 'Input sheet!B12'],
        ['wdfc25-cf', 'wdfc25-is'],
        (
            'This requires cash from operations and capex for both years under '
            'one definition. The original proposal set does not supply that '
            'complete comparison. A DCF output cannot resolve this historical '
            'question.'
        ),
        'needs_evidence')
    add('cash-working-capital', 'cash', (
        'Does the forecast explicitly model WD-40’s working-capital funding '
        'need?'
    ),
        'assumption', pe, 'voltaic-05-nwc-peg',
        ['Input sheet!B31', 'Input sheet!B32', 'Valuation output!C8'],
        ['wdfc25-bs', 'wdfc25-cf'],
        (
            'Ginzu’s sales-to-capital reinvestment approach aggregates net '
            'capital spending and working-capital investment. It does not '
            'provide a standalone receivables, inventory and payables schedule '
            'or an acquisition working-capital peg.'
        ),
        'assumption')

    add('tax-normalization', 'tax', (
        'How is the model’s normalized starting tax '
        'rate calculated?'
    ),
        'fact', fb, 'financebench_id_01351',
        ['Input sheet!B23'], ['wdfc25-tax', 'wdfc25-is', 'wdfc25-cf'],
        ('The original case uses (reported tax $10.632m + nonrecurring '
         'benefit $11.929m) / pretax income $101.626m = '
         f'{normalized_tax * 100:.6f}%. '
         'The result is an explicit normalization convention, '
         'not the reported effective rate.'))
    add('tax-terminal', 'tax', 'Is the 25% terminal tax rate a company fact?',
        'assumption', fl, '82',
        ['Input sheet!B23', 'Input sheet!B24', 'Input sheet!B59'],
        ['wdfc25-tax'],
        (
            'The 25% long-run combined marginal rate is an analyst assumption. '
            'The original case fades the normalized starting rate toward it '
            'because the permanent-effective-rate override is off.'
        ),
        'assumption', (
            'The FinLFQA comparison was changed into a single-company '
            'normalization question; it is not scored as the original '
            'two-company item.'
        ))
    add('tax-nol', 'tax', (
        'Why are disclosed state NOLs excluded from the simplified consolidated'
        ' tax shield?'
    ),
        'assumption', fl, '97',
        ['Input sheet!B61', 'Input sheet!B62'], ['wdfc25-nol'],
        (
            'The original source records $7.8m of state NOLs with a $0.5m '
            'deferred-tax asset. Their treatment is not equivalent to deducting'
            ' $7.8m against all consolidated operating income at one modeled '
            'tax rate, so this case leaves the simplified NOL shield inactive.'
        ),
        'assumption')

    add('discount-start', 'discount', (
        'Which historical CAPM evidence supports the '
        'original 9% starting WACC?'
    ),
        'assumption', pe, 'voltaic-07-operating-model',
        ['Cost of capital worksheet!B11', 'Cost of capital worksheet!B12',
         'Input sheet!B34', 'Input sheet!B35'],
        [],
        (
            'The original 9% WACC and 4% risk-free rate are explicit '
            'illustrative parameters. No date-matched CAPM calculation is '
            'supplied. A sourced replacement needs the risk-free rate, equity '
            'risk premium, beta, borrowing cost and capital weights.'
        ),
        'needs_evidence')
    add('discount-terminal', 'discount', (
        'Why is terminal WACC 8%, and which template '
        'tables are bypassed?'
    ),
        'assumption', pe, 'voltaic-07-operating-model',
        ['Input sheet!B45', 'Input sheet!B46', 'Valuation output!M12'],
        [],
        (
            'The case explicitly overrides terminal WACC to 8%. This avoids '
            'inheriting the template’s later reference premium. The selected 8%'
            ' remains an analyst assumption; it is not verified August 2025 '
            'market data.'
        ),
        'assumption')
    add('discount-sensitivity', 'discount', (
        'How does shifting the WACC path change '
        'modeled value per share?'
    ),
        'assumption', pe, 'voltaic-11-returns-waterfall',
        ['Cost of capital worksheet!B12', 'Input sheet!B46', 'Valuation output!B33'],
        [],
        (
            'Use the sensitivity and reverse-DCF calculations with all other '
            'inputs fixed. State whether the whole path shifts or becomes flat;'
            ' those are different counterfactuals. The implied rate does not '
            'establish market participants’ beliefs.'
        ),
        'assumption', (
            'The PE Bench maximum-price task is adapted into a required-return '
            'sensitivity; its transaction terms and original answer are not '
            'transferred.'
        ))

    add('terminal-reinvestment', 'terminal', (
        'What terminal reinvestment does 2.5% growth require when ROIC equals '
        '8% WACC?'
    ),
        'assumption', fb, 'financebench_id_00499',
        ['Input sheet!B48', 'Input sheet!B49', 'Input sheet!B68',
         'Valuation output!M40', 'Valuation output!M8'],
        [],
        (
            'Under the original default, terminal ROIC equals terminal WACC. '
            'The steady-state reinvestment rate is g / ROIC = 2.5% / 8% = '
            '31.25% of terminal NOPAT. Growth, ROIC and reinvestment must be '
            'considered together.'
        ),
        'assumption')
    add('terminal-excess-returns', 'terminal', (
        'What supports terminal ROIC of 20% or 25% in '
        'an alternative scenario?'
    ),
        'assumption', pe, 'voltaic-07-operating-model',
        ['Input sheet!B48', 'Input sheet!B49', 'Valuation output!M40'],
        ['wdfc25-company'],
        (
            'A durable excess-return scenario needs evidence on competition, '
            'brand economics, capital requirements and the duration of '
            'advantages. A high historical return alone does not establish a '
            'perpetual terminal return.'
        ),
        'needs_evidence')
    add('terminal-value-share', 'terminal', (
        'How much of modeled operating value comes '
        'from the terminal value?'
    ),
        'assumption', pe, 'voltaic-07-operating-model',
        ['Valuation output!B19', 'Valuation output!B21', 'Valuation output!B24'],
        [],
        (
            'Calculate present value of terminal value divided by the '
            'corresponding operating-value cash-flow sum. Read this alongside '
            'terminal growth, margin, WACC and reinvestment; it is a '
            'model-dependence measure.'
        ),
        'assumption')

    add('financing-net-debt', 'financing', (
        'Which debt and cash amounts enter the '
        'enterprise-to-equity bridge?'
    ),
        'fact', pe, 'voltaic-09-sources-uses',
        ['Input sheet!B15', 'Input sheet!B18', 'Valuation output!B26',
         'Valuation output!B31'],
        ['wdfc25-bs'],
        (
            'The original proposals record gross interest-bearing borrowings of'
            ' $86.995m and cash of $58.130m. This implies $28.865m of net '
            'borrowings under the stated lease convention, before any '
            'separately justified transaction adjustments.'
        ))
    add('financing-leases', 'financing', (
        'Why are operating-lease liabilities excluded '
        'from this case’s debt?'
    ),
        'assumption', pe, 'voltaic-05-nwc-peg',
        ['Input sheet!B15', 'Input sheet!B17', 'Input sheet!B14'],
        ['wdfc25-leases', 'wdfc25-lease-expense'],
        (
            'The case leaves operating rent in EBIT and excludes the $10.705m '
            'recognized operating-lease liability from debt. It also adjusts '
            'book equity for the net lease-capitalization difference. This is a'
            ' consistent chosen convention, not absence of lease obligations.'
        ),
        'assumption')
    add('financing-affordability', 'financing', (
        'What entry price can a buyer pay while meeting a 20% annualized equity'
        ' return?'
    ),
        'assumption', pe, 'voltaic-11-returns-waterfall',
        ['Input sheet!B12', 'Input sheet!B15', 'Input sheet!B18', 'Input sheet!B21'],
        ['wdfc25-is', 'wdfc25-bs'],
        (
            'Use the LBO ability-to-pay schedule with explicit debt, interest, '
            'fees, reinvestment, liquidity and exit assumptions. Without those '
            'terms the original DCF does not answer the buyer’s maximum-price '
            'question.'
        ),
        'needs_evidence')

    add('payouts-dilution', 'payouts', (
        'What share count is used for DCF value per share, and is it the '
        'market-cap share count?'
    ),
        'fact', pe, 'voltaic-09-sources-uses',
        ['Input sheet!B21', 'Valuation output!B32', 'Valuation output!B33'],
        ['wdfc25-bs', 'wdfc25-rsu', 'wdfc25-msu', 'wdfc25-plan-footnote', 'wdfc25-psu'],
        (
            'The original DCF denominator is 13.633263m: 13.527614m common '
            'shares plus 0.063189m RSUs, 0.040839m target MSUs and 0.001621m '
            'vested DPUs. It is an explicit stock-unit dilution proxy; '
            'point-in-time common shares should be identified separately for '
            'market capitalization.'
        ))
    add('payouts-dividends', 'payouts', (
        'Were FY2025 dividends covered by recurring earnings and free cash '
        'flow?'
    ),
        'fact', fb, 'financebench_id_06272',
        ['Input sheet!B12', 'Input sheet!B23'],
        ['wdfc25-is', 'wdfc25-cf', 'wdfc25-tax'],
        (
            'Verify total cash dividends, normalized net income and cash from '
            'operations less capex under consistent definitions. The original '
            'proposals do not include the complete payout-coverage calculation;'
            ' the tax-release benefit must not be treated as recurring '
            'earnings.'
        ),
        'needs_evidence')
    add('payouts-ddm', 'payouts', (
        'Which dividend-growth and cost-of-equity assumptions support the DDM '
        'range?'
    ),
        'assumption', fl, '41',
        ['Input sheet!B21', 'Input sheet!B34'], ['wdfc25-is', 'wdfc25-cf'],
        (
            'A dividend valuation requires a dated dividend base, sustainable '
            'per-share payout growth and cost of equity. WACC is not the '
            'discount rate for dividends. The original DCF input set alone does'
            ' not establish these inputs.'
        ),
        'needs_evidence', (
            'The source’s two-company dividend comparison is adapted into a '
            'single-company payout-underwriting question.'
        ))

    add('risks-disposal', 'risks', (
        'How would removing the homecare assets change the revenue and '
        'operating-income base?'
    ),
        'assumption', 'fincausal', '0209.00019',
        ['Input sheet!B11', 'Input sheet!B12', 'Input sheet!B26'],
        ['wdfc25-is', 'wdfc25-bs'],
        (
            'Reconcile reported results to the pro forma scope, then account '
            'separately for the value, tax and costs of any disposal. The '
            'original case has no complete divestiture bridge. An announced '
            'intention to sell does not establish a completed transaction.'
        ),
        'needs_evidence', (
            'The source cause-effect spans concern a different company. Only '
            'the disposal-to-results reasoning pattern is reused; no '
            'source-company figures become WD-40 facts.'
        ))
    add('risks-product-concentration', 'risks', (
        'Which WD-40 product and geographic exposures could invalidate the '
        'growth scenario?'
    ),
        'fact', fb, 'financebench_id_00517',
        ['Input sheet!B11', 'Input sheet!B26', 'Input sheet!B28'],
        ['wdfc25-company', 'wdfc25-is'],
        (
            'Inspect product and regional disclosures in the annual report '
            'before assigning exposures or probabilities. The original proposal'
            ' set contains consolidated revenue and business identity, not a '
            'fully verified concentration analysis.'
        ),
        'needs_evidence')
    add('risks-falsification', 'risks', (
        'Which published operating result would falsify the higher-margin '
        'scenario?'
    ),
        'forecast', pe, 'voltaic-07-operating-model',
        ['Input sheet!B29', 'Input sheet!B30', 'Input sheet!B27'],
        ['wdfc25-is', 'wdfc25-rd'],
        (
            'No advance probability is recorded. The margin scenario needs an '
            'explicit adjustment policy and a dated observable test. This '
            'retrospective template is not a historical forecasting track '
            'record.'
        ),
        'unresolved_forecast',
        resolution={'metric': (
            'Reported EBIT margin with a separately '
            'documented R&D adjustment'
        ),
                    'period': 'FY2030',
                    'threshold': 'Adjusted EBIT / revenue >= 0.20',
                    'source': (
                        'WD-40 FY2030 annual report and the fixed R&D '
                        'adjustment policy'
                    ),
                    'resolveAfter': 'FY2030 annual report publication',
                    'retrospectiveTemplate': True})

    known_cells = set(book['cells'])
    known_case_sources = {source['id'] for source in case['sources']}
    for question in questions:
        unknown_cells = set(question['cellIds']) - known_cells
        unknown_sources = set(question['sourceIds']) - known_case_sources
        if unknown_cells or unknown_sources:
            identifier = question['id']
            raise ValueError(
                f'Unresolved links for {identifier}: '
                f'{unknown_cells}, {unknown_sources}'
            )

    sources = [{
        'id': source['id'],
        'title': source['title'],
        'url': source['page'],
        'downloadUrl': source['url'],
        'version': 'sha256:' + source['sha256'],
        'revision': source['revision'],
        'licenseKnown': source['licenseKnown'],
        'recordCount': counts[source['id']],
        'usage': ((
            'Inspected but not selected: banking and regulatory QA does not '
            'support WD-40 valuation assumptions; textbook portion is not '
            'released.'
        )
                  if source['id'] == 'fintextqa' else (
                      'Actual records inspected; selected patterns are '
                      'explicitly adapted.'
                  )),
    } for source in source_lookup.values() if source['status'] == 'available']
    proposal_payload = json.dumps(case['proposals'], sort_keys=True).encode()
    result = {
        'schemaVersion': '1.0',
        'company': 'WD-40 Company',
        'caseBasis': 'FY2025 retrospective illustrative DCF',
        'caseProposalHash': hashlib.sha256(proposal_payload).hexdigest(),
        'sources': sources,
        'parents': [{'id': identifier, 'question': question, 'description': description}
                    for identifier, question, description in PARENTS],
        'questions': questions,
        'initialQuestionIds': [
            'revenue-base', 'margin-reported', 'margin-rd-bridge',
            'capital-turnover', 'cash-fcff', 'tax-normalization',
            'discount-start', 'discount-terminal',
            'terminal-reinvestment', 'terminal-value-share',
            'financing-net-debt', 'payouts-dilution',
        ],
        'counts': {'sourceRecords': counts, 'curatedQuestions': len(questions)},
        'limitations': [
            (
                'These are analyst-authored company adaptations, not published '
                'WD-40 benchmark questions or a benchmark score.'
            ),
            (
                'Static answers describe the original proposal snapshot; '
                'current user edits can differ.'
            ),
            (
                'Source snapshots were parsed as inert data; code fields were '
                'not executed.'
            ),
            (
                'Source-specific reuse rights remain to be independently '
                'confirmed before redistributing full raw datasets.'
            ),
            'FinCausal contains cause-effect spans, not prewritten questions.',
            (
                'No suitable WD-40 valuation question was selected from the '
                'released FinTextQA banking-policy subset.'
            ),
        ],
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    OUTPUT.write_text(payload + '\n')
    categories = {
        category: sum(q['category'] == category for q in questions)
        for category in ('fact', 'assumption', 'forecast')
    }
    print(json.dumps({
        'output': str(OUTPUT), 'parents': len(PARENTS),
        'questions': len(questions), 'categories': categories,
    }, indent=2))


if __name__ == '__main__':
    main()
