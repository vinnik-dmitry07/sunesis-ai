# Stage 6: diligence questions

`python -I models/questions/extract.py` merged 1,813 records from the pinned benchmark files: FinanceBench 150, FinLFQA 302, FinCausal 1,109, PE Bench 12, FinTextQA 240. `python -I models/questions/build_questions.py` adapts them to WD-40 in 57 questions under 11 topics and computes every answer from filings filed by 27 Oct 2025, the original case's proposals, the FY2025 8-K and 10-K passages, or the model. The adapted set is not a benchmark result.

Each topic starts from a judgement question. Following The Mom Test, the judgement is not asked directly: it is split into questions about specific past facts, then a question about which model input those facts test. Forecast questions state the object, period, threshold and resolution rule. Information from after the case date is shown apart and labelled; it is computed from the FY2026 10-K and the July 2026 guidance revision and never enters a valuation.

| Source | Records | Used as origin | Note |
|---|---:|---:|---|
| FinanceBench | 150 | 19 |  |
| FinLFQA | 302 | 6 | Records were chosen by their question text: the dataset's topic labels often do not match it, and no validation question asks about the cost of capital. |
| FinCausal | 1,109 | 2 | Cause-effect pairs from news about other companies; two shape the form of the disposal and oil-cost questions, and no figure from them enters an answer. |
| PE Bench | 12 | 8 |  |
| FinTextQA | 240 | 0 | The public part is 240 questions on banking regulation (Federal Reserve, HKMA, EU). None applies to a non-bank consumer products company; the textbook part was not released. |

## Merge of the two earlier question sets

Both earlier sets were merged by meaning, not by benchmark record: `main` (70b6ba8) had 30 questions, `valuation-range` (aa9dce5) had 47. main: 10 kept; main: 20 merged; valuation-range: 47 kept. Nothing was excluded.

| Earlier question | Disposition | Now |
|---|---|---|
| `main:revenue-base` What FY2025 revenue anchors the WD-40 model? | merged | `growth-1` |
| `main:revenue-growth` What was reported FY2025 revenue growth, and is the forecast the same claim? | merged | `growth-2` |
| `main:revenue-resolution` Will WD-40 FY2026 reported net sales exceed the FY2025 reported base by at least 5%? | kept | `growth-6` |
| `main:margin-reported` What is WD-40 FY2025 reported operating margin? | merged | `margin-3` |
| `main:margin-rd-bridge` Why does the original model use a 17.1068% operating margin rather than the reported margin? | kept | `margin-rd` |
| `main:margin-target` What evidence would justify a 20% adjusted EBIT margin instead of the original flat margin? | merged | `margin-5` |
| `main:capital-capex` What was WD-40 FY2025 capital expenditure, and what percentage of revenue was it? | merged | `capital-1` |
| `main:capital-turnover` Is the model’s 2.0× sales-to-capital ratio observed or assumed? | merged | `capital-5` |
| `main:capital-rd` Which R&D amounts support the model’s capitalization schedule? | merged | `margin-rd` |
| `main:cash-fcff` What modeled free cash flow is generated in the first forecast year? | kept | `cash-4` |
| `main:cash-conversion` Did historical free-cash-flow conversion improve from FY2024 to FY2025? | merged | `cash-2` |
| `main:cash-working-capital` Does the forecast explicitly model WD-40’s working-capital funding need? | merged | `capital-5` |
| `main:tax-normalization` How is the model’s normalized starting tax rate calculated? | merged | `tax-2` |
| `main:tax-terminal` Is the 25% terminal tax rate a company fact? | merged | `tax-3` |
| `main:tax-nol` Why are disclosed state NOLs excluded from the simplified consolidated tax shield? | kept | `tax-4` |
| `main:discount-start` Which historical CAPM evidence supports the original 9% starting WACC? | merged | `coc-4` |
| `main:discount-terminal` Why is terminal WACC 8%, and which template tables are bypassed? | merged | `coc-4` |
| `main:discount-sensitivity` How does shifting the WACC path change modeled value per share? | kept | `coc-5` |
| `main:terminal-reinvestment` What terminal reinvestment does 2.5% growth require when ROIC equals 8% WACC? | kept | `returns-6` |
| `main:terminal-excess-returns` What supports terminal ROIC of 20% or 25% in an alternative scenario? | merged | `returns-5` |
| `main:terminal-value-share` How much of modeled operating value comes from the terminal value? | kept | `returns-7` |
| `main:financing-net-debt` Which debt and cash amounts enter the enterprise-to-equity bridge? | merged | `financing-1` |
| `main:financing-leases` Why are operating-lease liabilities excluded from this case’s debt? | kept | `financing-5` |
| `main:financing-affordability` What entry price can a buyer pay while meeting a 20% annualized equity return? | merged | `financing-3` |
| `main:payouts-dilution` What share count is used for DCF value per share, and is it the market-cap share count? | kept | `payouts-5` |
| `main:payouts-dividends` Were FY2025 dividends covered by recurring earnings and free cash flow? | merged | `payouts-2` |
| `main:payouts-ddm` Which dividend-growth and cost-of-equity assumptions support the DDM range? | merged | `payouts-4` |
| `main:risks-disposal` How would removing the homecare assets change the revenue and operating-income base? | kept | `growth-perimeter` |
| `main:risks-product-concentration` Which WD-40 product and geographic exposures could invalidate the growth scenario? | merged | `returns-2`, `returns-3` |
| `main:risks-falsification` Which published operating result would falsify the higher-margin scenario? | merged | `risks-4` |
| `valuation-range:growth-1` What were net sales in FY2021 and FY2025, and the compound annual growth rate between them? | kept | `growth-1` |
| `valuation-range:growth-2` How much of the FY2025 change in net sales came from volume, price and currency? | kept | `growth-2` |
| `valuation-range:growth-3` What growth did management guide for FY2026, from what base and at what exchange rates? | kept | `growth-3` |
| `valuation-range:growth-4` Which growth rates do the scenarios use after year 1, and how do they compare with the FY2021-FY2025 rate? | kept | `growth-4` |
| `valuation-range:growth-5` Will FY2026 net sales on the guidance basis (pro forma, FY2025 exchange rates) reach the $642.5m midpoint? | kept | `growth-5` |
| `valuation-range:margin-1` What was the gross margin in each fiscal year from 2021 to 2025? | kept | `margin-1` |
| `valuation-range:margin-2` What explained the change in gross margin from FY2024 to FY2025? | kept | `margin-2` |
| `valuation-range:margin-3` What was the operating margin in each fiscal year from 2021 to 2025? | kept | `margin-3` |
| `valuation-range:margin-4` How far was FY2025 cost of doing business from the company's own target? | kept | `margin-4` |
| `valuation-range:margin-5` Which margin paths do the scenarios use, and on what basis? | kept | `margin-5` |
| `valuation-range:capital-1` What were capital expenditures as a share of net sales in each year from FY2021 to FY2025? | kept | `capital-1` |
| `valuation-range:capital-2` How many times did inventory turn in FY2025 (cost of products sold over average inventory)? | kept | `capital-2` |
| `valuation-range:capital-3` What were receivables plus inventory minus payables at the end of FY2025, as a share of FY2025 net sales? | kept | `capital-3` |
| `valuation-range:capital-4` How much revenue did each dollar of added invested capital bring between FY2021 and FY2025? | kept | `capital-4` |
| `valuation-range:capital-5` Which sales-to-capital ratio does the model use, and does the history above support it? | kept | `capital-5` |
| `valuation-range:cash-1` What were operating cash flow and capital expenditures in each year from FY2021 to FY2025? | kept | `cash-1` |
| `valuation-range:cash-2` What was free cash flow (operating cash flow minus capex) as a share of net income in FY2023, FY2024 and FY2025? | kept | `cash-2` |
| `valuation-range:cash-3` Among operating, investing and financing activities, which brought in the most cash in FY2025? | kept | `cash-3` |
| `valuation-range:tax-1` How much did the effective tax rate change between FY2024 and FY2025? | kept | `tax-1` |
| `valuation-range:tax-2` What one-time item explains the FY2025 rate? | kept | `tax-2` |
| `valuation-range:tax-3` Which starting tax rate do the scenarios use? | kept | `tax-3` |
| `valuation-range:coc-1` What was the 10-year Treasury yield on 29 Aug 2025, and Damodaran's implied equity risk premium at the start of September 2025? | kept | `coc-1` |
| `valuation-range:coc-2` What betas do regressions of WD-40 on the S&P 500 give, and how much of the variation do they explain? | kept | `coc-2` |
| `valuation-range:coc-3` What were Damodaran's January 2025 unlevered betas for Chemical (Specialty) and Household Products? | kept | `coc-3` |
| `valuation-range:coc-4` Which WACC do the scenarios use, and what did the original case use? | kept | `coc-4` |
| `valuation-range:returns-1` What was FY2025 return on invested capital in the workbook (after-tax operating income over invested capital)? | kept | `returns-1` |
| `valuation-range:returns-2` What share of FY2025 net sales came from WD-40 Multi-Use Product? | kept | `returns-2` |
| `valuation-range:returns-3` What share of FY2025 net sales came from outside the United States, and did any customer reach 10%? | kept | `returns-3` |
| `valuation-range:returns-4` Does restating the DCF as invested capital plus economic profit give the same operating value? | kept | `returns-4` |
| `valuation-range:returns-5` What return on new capital after year 10 do the scenarios assume? | kept | `returns-5` |
| `valuation-range:payouts-1` What dividend per share did WD-40 pay in each year from FY2021 to FY2025? | kept | `payouts-1` |
| `valuation-range:payouts-2` What share of FY2025 earnings per share went to dividends? | kept | `payouts-2` |
| `valuation-range:payouts-3` How did FY2025 share repurchases compare with dividends? | kept | `payouts-3` |
| `valuation-range:payouts-4` What does a dividend discount model give with the scenarios' cost of equity? | kept | `payouts-4` |
| `valuation-range:financing-1` How did borrowings change between the end of FY2024 and FY2025? | kept | `financing-1` |
| `valuation-range:financing-2` What was FY2025 operating income over interest expense? | kept | `financing-2` |
| `valuation-range:financing-3` At 5.0 times FY2025 EBITDA of debt, SOFR on 29 Aug 2025 plus 3.5%, a 20% target return and an exit at the peer median multiple, what is the highest price per share that works? | kept | `financing-3` |
| `valuation-range:financing-4` Which operating case does the buyout model use? | kept | `financing-4` |
| `valuation-range:market-1` What EV to EBITDA did five listed peers trade at on 29 Aug 2025, after adding back tagged one-off charges? | kept | `market-1` |
| `valuation-range:market-2` What EV to EBITDA did WD-40 trade at on 29 Aug 2025, and at its previous four fiscal year-ends? | kept | `market-2` |
| `valuation-range:market-3` Starting from Base, what single change reaches $216.04? | kept | `market-3` |
| `valuation-range:market-4` What price targets had analysts published by 29 Aug 2025? | kept | `market-4` |
| `valuation-range:market-5` Can the company-defined adjusted EBITDA of $114.4m be reconciled to EBIT plus depreciation and amortization of $112.0m? | kept | `market-5` |
| `valuation-range:risks-1` Which inputs does WD-40 name as its main costs, and how does the price of oil reach them? | kept | `risks-1` |
| `valuation-range:risks-2` How did currency translation affect FY2025 net sales by segment? | kept | `risks-2` |
| `valuation-range:risks-3` Are restructuring costs shown separately in the FY2025 income statement? | kept | `risks-3` |
| `valuation-range:risks-4` Will the FY2026 gross margin stay within the guided 55.5-56.5% range? | kept | `risks-4` |

## Revenue growth

**Is WD-40's revenue growth in line with the growth the scenarios assume?**

FinanceBench asks whether a company's financials are those of a high-growth company and what drove revenue change; PE Bench asks for historicals and an operating model. The WD-40 version asks the same about the years the scenarios extrapolate from, then tests the scenario inputs against them.

Origins: FinanceBench `financebench_id_00956` (Are JnJ's FY2022 financials that of a high growth company?); FinanceBench `financebench_id_01198` (What drove revenue change as of the FY22 for AMD?); PE Bench `voltaic-01-historicals` (Project Voltaic is a data centre platform we're looking at buying; the data room is attached. Build me a clean…); PE Bench `voltaic-07-operating-model` (Build me an operating model for Ironvale off the data room: drivers to EBITDA and EBIT, historicals through FY…); FinCausal `0209.00019` (cause: disposals.; effect: Its operating income was $1.8 billion, while net income decr)

- *fact* `growth-1`: What were net sales in FY2021, FY2024 and FY2025, and the compound annual growth rate from FY2021 to FY2025?  
  $488.1m in FY2021, $590.6m in FY2024 and $620.0m in FY2025: 6.2% a year from FY2021. FY2025 and FY2024 are the model's starting revenue.
- *fact* `growth-2`: How much did net sales grow in FY2025, and how much of the change came from volume, price and currency?  
  4.98%, or $29.4m. Volume added about $25.2m, price about $5.6m and currency translation took off $1.4m.
- *fact* `growth-3`: What growth did management guide for FY2026, from what base and at what exchange rates?  
  5%-9% from FY2025 pro forma results, which exclude the Americas homecare and cleaning brands held for sale, at FY2025 average exchange rates: $630-655m.
- *calculation* `growth-perimeter`: How much FY2025 revenue does the guidance base leave out, and does the release say what the excluded brands sell?  
  The guidance starts from currency-adjusted pro forma FY2025 net sales of about $603m, against $620.0m reported, so about $17.0m sits outside the base. The release does not split that amount, so it only bounds the excluded brands' FY2025 sales from above. The release's $12.5m is a different figure: how much higher FY2026 net sales guidance would be if the sale did not happen. The scenarios grow reported revenue and assume no sale proceeds. Taking the whole $17.0m out of the Americas would change Base growth in years 2-5 by 0.05 points.
  Later information (after the case date): In July 2026 the company moved the brands from held for sale back to held for use and put their contribution at about $12m of net sales and $2.9m of operating income.
- *assumption* `growth-4`: Which growth rates do the scenarios use, and how do they compare with the FY2021-FY2025 rate?  
  Year 1 is set at the guidance range on the reported base: Bear 1.62%, Base 3.63%, Bull 5.65%. Years 2-5 come from a regional build (Americas/EIMEA/Asia-Pacific: Bear 2/4/5%, Base 4/7/8%, Bull 6/9/11%; analyst assumptions), compressed to one rate: Bear 3.25%, Base 5.81%, Bull 7.98% a year, against 6.2% in FY2021-FY2025.
- *forecast* `growth-5`: Will FY2026 net sales on the guidance basis (pro forma, FY2025 exchange rates) reach the $642.5m midpoint?  
  Open at the case date. Status: open at case date.
  Resolution: Compare FY2026 net sales on the original guidance basis (without the brands then held for sale, at FY2025 exchange rates) with the midpoint. Threshold $642.5m; linked to Input sheet!B26 (Base 3.63%).
  Later information (after the case date): The FY2026 10-K reports net sales of $688.0m. That is reported revenue: it includes the Americas homecare and cleaning brands, which the company moved back from held for sale to held for use in July 2026, and currency translation. It is not on the guidance basis, so it does not resolve the question; the constant-currency figure on the original perimeter was not collected.
- *forecast* `growth-6`: Will FY2026 reported net sales exceed FY2025 reported net sales by at least 5%?  
  Open at the case date. The case recorded no probability for it. Status: open at case date.
  Resolution: Compare reported net sales in the FY2026 10-K with FY2025 reported net sales. Threshold $651.0m (5% above $620.0m); linked to Input sheet!B26 (the original case's 5% year-1 growth).
  Later information (after the case date): The FY2026 10-K reports net sales of $688.0m, 11.0% above FY2025. Both years are reported figures that include the homecare brands and currency translation. With no probability recorded at the case date, this is an outcome, not a forecasting record.

## Margins

**Does WD-40's margin history support the Base path from 16.9% to 18%?**

FinanceBench asks whether margins are improving and what drove the change; PE Bench asks for the bridge from reported to adjusted earnings. Here the facts are the filed margins, the drivers named in the FY2025 10-K and the workbook's one adjustment, and the last question checks the scenario paths against them.

Origins: FinanceBench `financebench_id_00684` (Does AMCOR have an improving gross margin profile as of FY2023? If gross margin is not a useful metric for a c…); FinanceBench `financebench_id_01226` (What drove operating margin change as of FY2022 for 3M? If operating margin is not a useful metric for a compa…); FinanceBench `financebench_id_00685` (Are Best Buy's gross margins historically consistent (not fluctuating more than roughly 2% each year)? If gros…); PE Bench `voltaic-04-ebitda-bridge` (Bridge Project Voltaic's FY25 reported result to adjusted EBITDA for pricing from a buyer's perspective, using…); PE Bench `voltaic-07-operating-model` (Build me an operating model for Ironvale off the data room: drivers to EBITDA and EBIT, historicals through FY…)

- *fact* `margin-1`: What was the gross margin in each fiscal year from 2021 to 2025?  
  FY2021 54.0%, FY2022 49.1%, FY2023 51.0%, FY2024 53.4%, FY2025 55.1%.
- *fact* `margin-2`: What explained the change in gross margin from FY2024 to FY2025?  
  The filing names lower specialty chemical costs (+80 bp), lower aerosol can costs (+60 bp) and higher average selling prices (+50 bp), less higher warehousing, distribution and freight costs (-50 bp). Gross margin rose 168 bp; the named drivers add up to 140 bp, leaving about 28 bp that the filing does not attribute.
- *fact* `margin-3`: What was the reported operating margin in each fiscal year from 2021 to 2025?  
  FY2021 18.2%, FY2022 16.8%, FY2023 16.7%, FY2024 16.3%, FY2025 16.7%. FY2025 is $103.793m over $619.985m, before the workbook's R&D adjustment.
- *calculation* `margin-rd`: How does the workbook's R&D capitalization change FY2025 operating income?  
  It adds back FY2025 R&D of $8.7m and subtracts a third of each of the three prior years' R&D ($8.0m, $6.2m and $5.1m), $6.43m in total. Operating income rises by $2.27m to $106.06m, a 17.11% margin against 16.74% reported. The three-year life is an analyst assumption; the company expenses R&D.
- *fact* `margin-4`: How far was FY2025 cost of doing business from the company's own target?  
  37% of net sales against a long-term target of 30%; gross margin was at its 55% target and adjusted EBITDA was 18% against 25%.
- *assumption* `margin-5`: Which margin paths do the scenarios use, and on what basis?  
  Year-1 margins come from operating-income guidance plus the workbook's R&D adjustment: Bear 16.7%, Base 16.9%, Bull 17.1%. By year 5: Bear stays at its year-1 margin, Base 18%, Bull 20%. FY2017-FY2020 averaged 19.4% reported. The company's long-term model targets adjusted EBITDA of 25%, not an operating margin, so no filing gives the 18% or 20% directly: both are analyst assumptions.

## Capital intensity and reinvestment

**Does WD-40 need as much capital to grow as the sales-to-capital ratio of 2.0 implies?**

FinanceBench asks whether a company is capital-intensive, what it spends on capex and how fast it turns inventory; PE Bench asks for a working-capital peg. Here those facts test the single reinvestment input of the DCF.

Origins: FinanceBench `financebench_id_00499` (Is 3M a capital-intensive business based on FY2022 data?); FinanceBench `financebench_id_00540` (Roughly how many times has AES Corporation sold its inventory in FY2022? Calculate inventory turnover ratio fo…); FinanceBench `financebench_id_03029` (What is the FY2018 capital expenditure amount (in USD millions) for 3M? Give a response to the question by rel…); PE Bench `voltaic-05-nwc-peg` (We're putting together a first-round bid for Project Voltaic. Work out the net working capital we'd assume, ho…)

- *fact* `capital-1`: What were capital expenditures as a share of net sales in each year from FY2021 to FY2025?  
  FY2021 3.1%, FY2022 1.6%, FY2023 1.3%, FY2024 0.7%, FY2025 0.7%. FY2025 capex (purchases of property, plant and equipment in the cash-flow statement) was $4.5m against depreciation and amortization of $8.2m.
- *calculation* `capital-2`: How many times did inventory turn in FY2025 (cost of products sold over average inventory)?  
  3.51 times: $278.6m over average inventory of $79.5m.
- *calculation* `capital-3`: What were receivables plus inventory minus payables at the end of FY2025, as a share of FY2025 net sales?  
  $162.5m, or 26.2% of net sales.
- *calculation* `capital-4`: How much revenue did each dollar of added invested capital bring between FY2021 and FY2025?  
  Net sales rose $131.9m. Book equity plus borrowings minus cash rose from $230.2m to $297.0m, so each added dollar brought about $1.97 of revenue. This book measure excludes the capitalized R&D the workbook adds.
- *assumption* `capital-5`: Which sales-to-capital ratio does the model use, and is it observed or assumed?  
  2.0 in years 1-10 in every case, an assumption. The FY2021-FY2025 book measure above is 1.97, so the scenarios keep 2.0. The one ratio covers capital spending and working capital together: the model has no separate receivables, inventory and payables schedule.

## Cash conversion

**How much of WD-40's profit turns into cash?**

FinanceBench asks which cash-flow category brought in the most cash and whether free-cash-flow conversion improved; FinLFQA compares free cash flow with evidence. Both are answered here from the filed cash-flow statements, and the last question sets the model's first-year cash flow beside them.

Origins: FinanceBench `financebench_id_01279` (Among operations, investing, and financing activities, which brought in the most (or lost the least) cash flow…); FinanceBench `financebench_id_00591` (Does Adobe have an improving Free cashflow conversion as of FY2022?); FinanceBench `financebench_id_04854` (According to the information provided in the statement of cash flows, what is the FY2020 free cash flow (FCF) …); FinLFQA `validation-34` (How do EOG's and NOG's free cash flow figures differ, and what does this imply for potential shareholder retur…)

- *fact* `cash-1`: What were operating cash flow and capital expenditures in each year from FY2021 to FY2025?  
  FY2021 $84.7m and $15.1m; FY2022 $2.6m and $8.3m; FY2023 $98.4m and $6.9m; FY2024 $92.0m and $4.2m; FY2025 $87.9m and $4.5m. FY2022 operating cash flow was low because inventory rose by $53.3m.
- *calculation* `cash-2`: What was free cash flow (operating cash flow minus capex) as a share of net income in FY2023, FY2024 and FY2025?  
  FY2023 139%, FY2024 126%, FY2025 92%. FY2025 net income includes an $11.9m one-time tax benefit; without it FY2025 is 105%.
- *fact* `cash-3`: Among operating, investing and financing activities, which brought in the most cash in FY2025?  
  Operating activities: $87.9m. Investing used $2.4m and financing used $74.1m.
- *calculation* `cash-4`: What free cash flow does Base produce in year 1, and how does it compare with FY2025 operating cash flow minus capex?  
  $65.1m: after-tax operating income of $83.8m less reinvestment of $18.7m. FY2025 operating cash flow minus capex was $83.4m. The model figure is a forecast before interest; the FY2025 figure is reported and after interest.

## Taxes

**Which tax rate should the forecast start from, and which tax effects recur?**

FinanceBench asks how much the effective tax rate changed between two years; FinLFQA asks how tax adjustments change effective rates. The WD-40 version adds the cause of the change, the rate the model starts from, and the tax item it leaves out.

Origins: FinanceBench `financebench_id_01351` (How much has the effective tax rate of American Express changed between FY2021 and FY2022?); FinLFQA `validation-82` (How does the adjusted effective tax rate due to non-GAAP measures differ between MDT and SYK?); FinLFQA `validation-97` (How do the tax-related adjustments for MDT and ISRG affect their effective tax rates, and what are the implica…)

- *calculation* `tax-1`: How much did the effective tax rate change between FY2024 and FY2025?  
  From 23.9% to 10.5%: -13.4 points.
- *fact* `tax-2`: What one-time item explains the FY2025 rate, and how does the workbook remove it?  
  An $11.929m release of a reserve for an uncertain tax position. The workbook's starting rate adds it back: ($10.632m + $11.929m) / $101.626m = 22.20%.
- *assumption* `tax-3`: Which starting and long-run tax rates do the scenarios use?  
  Bear 23.5%, Base 23.0%, Bull 22.5% to start, from the FY2026 guidance range of 22.5%-23.5%; the original case uses the normalized 22.2%. All move to 25% by year 10, an analyst assumption for the long-run marginal rate, not a company figure.
- *assumption* `tax-4`: Why does the model leave WD-40's state net operating losses out?  
  The 10-K reports $7.8m of state NOLs with a $0.5m deferred tax asset. The workbook's NOL input would shelter all consolidated operating income at one rate, which overstates a state-only loss, so it stays off. The Python port refuses any case with that input on.

## Cost of capital

**What discount rate do market data support for WD-40 at 29 Aug 2025?**

PE Bench requires a declared pricing date and asks what return a price implies. Each input here carries its date and source, and the last question shows how much the value depends on the rate. FinLFQA's validation questions include none on the cost of capital.

Origins: PE Bench `voltaic-02-comparables` (Build a trading comparables analysis and a precedent transactions analysis for Project Voltaic from the data r…); PE Bench `voltaic-07-operating-model` (Build me an operating model for Ironvale off the data room: drivers to EBITDA and EBIT, historicals through FY…); PE Bench `voltaic-11-returns-waterfall` (Build the exit, the distribution waterfall and the returns for Project Voltaic in the attached model, on the t…)

- *fact* `coc-1`: What was the 10-year Treasury yield on 29 Aug 2025, and Damodaran's implied equity risk premiums at the start of September 2025?  
  4.23%. Premiums: 3.94% (trailing 12-month cash yield), 5.37% (smoothed), 3.68% (sustainable payout). Each scenario pairs one premium with the same 4.23% rate: Bear smoothed, Base trailing 12-month cash yield, Bull sustainable payout.
- *calculation* `coc-2`: What betas do regressions of WD-40 on the S&P 500 give, and how much of the variation do they explain?  
  2-year weekly: 0.13 (R² 0.006); 5-year weekly: 0.49 (R² 0.073); 3-year monthly: 0.62 (R² 0.105); 5-year monthly: 0.10 (R² 0.003). None explains more than 11% of WD-40's returns.
- *fact* `coc-3`: What were Damodaran's January 2025 unlevered betas for Chemical (Specialty) and Household Products?  
  0.79 and 0.83, corrected for cash.
- *assumption* `coc-4`: Which WACC do the scenarios use, and what did the original case use?  
  Bear 8.66% moving to 9.45%, Base 7.40% and Bull 6.58% in every year. The original case used 9% moving to 8%: the starting rate is an illustrative placeholder with no CAPM behind it, and the terminal rate is typed into the workbook's override instead of coming from its risk-free rate plus mature-market premium.
- *calculation* `coc-5`: How much does Base value per share move when the WACC changes?  
  With a flat WACC and every other Base input fixed, value per share is $137.01 at 7.0% and $122.75 at 7.5%: about $14 per half point around Base's 7.40%. A flat rate and a shifted path that fades are different changes; the live reverse DCF on the page shifts the whole path.

## Return on capital

**How long can WD-40 keep earning more than its cost of capital?**

FinLFQA compares returns on equity; FinanceBench asks whether any product exceeds 20% of revenue. Together they ask how durable WD-40's excess return is, and how much of the value rests on it lasting.

Origins: FinLFQA `validation-170` (Comparing the Return on Equity (ROE), which company demonstrated better shareholder value in Q1 2024?); FinanceBench `financebench_id_00517` (Are there any product categories / service categories that represent more than 20% of Boeing's revenue for FY2…); PE Bench `voltaic-07-operating-model` (Build me an operating model for Ironvale off the data room: drivers to EBITDA and EBIT, historicals through FY…)

- *calculation* `returns-1`: What was FY2025 return on invested capital in the workbook (after-tax operating income over invested capital)?  
  26.3%, on invested capital of $313.4m including capitalized R&D.
- *fact* `returns-2`: What share of FY2025 net sales came from WD-40 Multi-Use Product?  
  $478.0m of $620.0m, or 77.1%. WD-40 Specialist added $82.0m.
- *fact* `returns-3`: How were FY2025 net sales split by region, and did any customer reach 10%?  
  Americas 47%, EIMEA 38%, Asia-Pacific 15%. About 66% came from outside the US. No customer reached 10% of consolidated net sales.
- *calculation* `returns-4`: Does restating the DCF as invested capital plus economic profit give the same operating value?  
  Yes. Original $1,230.6m against $1,230.6m; Bear $988.2m against $988.2m; Base $1,737.6m against $1,737.6m; Bull $2,950.2m against $2,950.2m. The two are the same calculation arranged differently, so this checks consistency, not value. The reconciliation is in the DCF details.
- *assumption* `returns-5`: What return on new capital after year 10 do the scenarios assume, and what supports it?  
  Bear: equal to the cost of capital (no excess return), Base: 15%, Bull: 20%. In years 1-10 the model earns 25% to 32% on capital across the four cases. No filing establishes a permanent excess return; the Base and Bull figures rest on the brand and the low capital needs above, and are analyst assumptions.
- *calculation* `returns-6`: What reinvestment does each case's terminal growth and return on new capital imply?  
  Reinvestment is growth over the return on new capital: Original 2.5% / 8.00% = 31.2%; Bear 2.0% / 9.45% = 21.2%; Base 2.5% / 15.00% = 16.7%; Bull 3.0% / 20.00% = 15.0% of after-tax operating income. A higher assumed return lets the same growth come with less reinvestment, so the two have to be read together.
- *calculation* `returns-7`: What share of operating value comes from after year 10 in each case?  
  Original 55%; Bear 47%; Base 64%; Bull 75%. The cases with higher growth and returns lean more on the years after the forecast.

## Shareholder payouts

**Is the dividend sustainable at the scenarios' growth rates, and how does value reach each share?**

FinanceBench asks whether a company pays dividends, keeps a stable trend and what its payout ratio is; FinLFQA compares dividends with buybacks; PE Bench needs a diluted share count. The WD-40 version adds coverage, a dividend-based value and the share count every value is divided by.

Origins: FinanceBench `financebench_id_01244` (Has CVS Health paid dividends to common shareholders in Q2 of FY2022?); FinanceBench `financebench_id_01858` (Does 3M maintain a stable trend of dividend distribution?); FinanceBench `financebench_id_06272` (What is Coca Cola's FY2022 dividend payout ratio (using total cash dividends paid and net income attributable …); FinLFQA `validation-221` (How did OLED's dividend payments in Q1 2024 compare to CGNX's share repurchases in financial magnitude?); FinLFQA `validation-41` (How do the dividends paid by EOG and PXD compare during the first quarter of 2024, including percentage differ…); PE Bench `voltaic-09-sources-uses` (We are acquiring 100% of Ironvale Digital Infrastructure (Project Voltaic). Build the transaction onto the att…)

- *fact* `payouts-1`: What dividend per share did WD-40 pay in each year from FY2021 to FY2025?  
  FY2021 $2.78, FY2022 $3.06, FY2023 $3.27, FY2024 $3.47, FY2025 $3.70. It rose every year.
- *calculation* `payouts-2`: How well did FY2025 earnings and free cash flow cover the dividend?  
  $3.70 a share paid against $5.82 non-GAAP diluted EPS (64%) or $6.69 GAAP EPS, which includes the one-time tax benefit (55%). In cash, dividends of $50.3m were 60% of operating cash flow minus capex.
- *fact* `payouts-3`: How did FY2025 share repurchases compare with dividends?  
  $12.3m of repurchases against $50.3m of dividends.
- *calculation* `payouts-4`: What does a dividend discount model give with the scenarios' cost of equity?  
  Bear $72.68 (cost of equity 8.79%, terminal payout 77%); Base $121.42 (cost of equity 7.49%, terminal payout 83%); Bull $198.76 (cost of equity 6.65%, terminal payout 85%). The discount rate is each scenario's CAPM cost of equity, not its WACC; earnings growth and payout are analyst assumptions.
- *fact* `payouts-5`: Which share count divides equity value, and how is it built?  
  13.633263m: 13.527614m common shares plus 0.063189m restricted stock units, 0.040839m market-based units at target and 0.001621m vested deferred units. Performance units granted in FY2025 are left out because they were later forfeited. Every case uses this count.

## Financing a buyout

**What could a financial buyer pay for WD-40?**

PE Bench asks for a debt schedule, sources and uses, debt-like items and returns; FinanceBench asks whether debt rose. Together they test what a sponsor could pay for WD-40.

Origins: PE Bench `voltaic-08-debt-schedule` (Build free cash flow and the debt schedule for Project Voltaic onto the attached transaction model, from the 3…); PE Bench `voltaic-09-sources-uses` (We are acquiring 100% of Ironvale Digital Infrastructure (Project Voltaic). Build the transaction onto the att…); PE Bench `voltaic-11-returns-waterfall` (Build the exit, the distribution waterfall and the returns for Project Voltaic in the attached model, on the t…); PE Bench `voltaic-05-nwc-peg` (We're putting together a first-round bid for Project Voltaic. Work out the net working capital we'd assume, ho…); FinanceBench `financebench_id_00552` (Has Microsoft increased its debt on balance sheet between FY2023 and the FY2022 period?)

- *fact* `financing-1`: How did borrowings change between the end of FY2024 and FY2025, and what reaches the equity bridge?  
  From $94.636m to $86.995m. With cash of $58.130m, borrowings net of cash were $28.865m at FY2025 year-end; the DCF subtracts the debt and adds the cash.
- *calculation* `financing-2`: What was FY2025 operating income over interest expense?  
  30 times: $103.8m over $3.44m.
- *calculation* `financing-3`: With the Base financing terms, what is the highest price per share a buyer can pay and still earn its target return?  
  $74.87 (boundary found), an entry multiple of 9.4 times EBITDA. Terms: 5.0 times FY2025 EBITDA of debt at SOFR on 29 Aug 2025 plus 3.5% (7.84%), a 20% target return, and an exit after five years at 11.2 times EBITDA, the peer median. Debt is repaid 1% a year, then from cash above a $30m minimum; fees are 2% on the transaction, 2.5% on the financing and 2% on exit. Bear (4.5x debt, 25% target, exit at the 25th percentile) gives $65.10; Bull (5.5x, 17.5%, 75th percentile) $106.28.
- *assumption* `financing-4`: Which operating case does the buyout model use?  
  The Base DCF case: its revenue, EBIT, tax rate and free cash flow before financing in years 1-5. EBITDA is put on a reported basis by removing the R&D adjustment and adding depreciation and amortization at the FY2025 share of sales.
- *assumption* `financing-5`: Why are operating leases left out of debt?  
  The case keeps operating rent in operating income, so it leaves the $10.705m operating-lease liability out of debt and takes it and the $10.385m right-of-use asset out of book equity: $268.152m reported becomes $268.472m. Counting the liability as debt would also require moving rent out of operating income.

## Market pricing

**What does the $216.04 price assume that the cases do not?**

PE Bench requires peers and the target on one EBITDA definition; FinanceBench asks whether operating margin is improving. Here the facts measure how far the price sits from each method.

Origins: PE Bench `voltaic-02-comparables` (Build a trading comparables analysis and a precedent transactions analysis for Project Voltaic from the data r…); FinanceBench `financebench_id_00438` (Does Adobe have an improving operating margin profile as of FY2022? If operating margin is not a useful metric…)

- *calculation* `market-1`: What EV to EBITDA did five listed peers trade at on 29 Aug 2025, after adding back tagged one-off charges?  
  25th percentile 11.1x, median 11.2x, 75th percentile 16.5x.
- *calculation* `market-2`: What EV to EBITDA did WD-40 trade at on 29 Aug 2025, and at its previous four fiscal year-ends?  
  FY2021 34.6x, FY2022 28.0x, FY2023 30.5x, FY2024 34.1x, FY2025 26.4x.
- *calculation* `market-3`: Starting from Base, what single change reaches $216.04?  
  A WACC of 5.40% in every year, or a 31.1% operating margin by year 5, or 19.0% revenue growth in years 2-5. No terminal return on capital reaches it alone: at 500% the value is $141.26.
- *fact* `market-4`: What price targets had analysts published by 29 Aug 2025?  
  DA Davidson $300 (Buy, 11 Jul 2025) and Jefferies $280 (Hold, 18 Oct 2024). Other firms' targets were not found.
- *fact* `market-5`: Can the company-defined adjusted EBITDA of $114.4m be reconciled to EBIT plus depreciation and amortization of $112.0m?  
  Not from the material collected. The $2.4m difference sits in the company's non-GAAP reconciliation, which was not extracted. Status: insufficient data.

## Threats to the business

**What could break the margin and growth assumptions?**

FinCausal extracts cause and effect from financial text; FinanceBench asks for restructuring costs. The WD-40 version asks which costs move margins, through what channel, and which published figure would test the margin paths.

Origins: FinCausal `0100.00018` (cause: Mr. Thummel projected that oil prices in the United States w; effect: a roughly 25 cent increase in the retail price of gasoline.); FinanceBench `financebench_id_01319` (What is the quantity of restructuring costs directly outlined in AES Corporation's income statements for FY202…); PE Bench `voltaic-07-operating-model` (Build me an operating model for Ironvale off the data room: drivers to EBITDA and EBIT, historicals through FY…)

- *fact* `risks-1`: Which inputs does WD-40 name as its main costs, and how does the price of oil reach them?  
  Specialty chemicals and aerosol cans. The 10-K says oil price volatility indirectly affects specialty chemical costs, many of which are indexed to refined oil products.
- *fact* `risks-2`: How did currency translation affect FY2025 net sales by segment?  
  Americas -$4.7m, EIMEA +$3.5m, Asia-Pacific -$0.2m: -$1.4m in total.
- *fact* `risks-3`: Are restructuring costs shown separately in the FY2025 income statement?  
  No restructuring line or restructuring fact appears in the FY2025 XBRL data, so the FinanceBench rule gives 0.
- *forecast* `risks-4`: Will the FY2026 gross margin stay within the guided 55.5%-56.5% range?  
  Open at the case date. Status: open at case date.
  Resolution: Compare FY2026 gross margin on the original guidance perimeter (without the brands then held for sale) with the range. A margin below it would contradict the Base and Bull paths, which raise operating margin to 18% and 20%. Threshold 55.5% to 56.5%; linked to Input sheet!B27 and B29 (Base 16.9% and 18% operating margin).
  Later information (after the case date): The FY2026 10-K reports a gross margin of 55.3% ($380.5m over $688.0m), below the range but on a changed perimeter. In July 2026 the company moved the homecare brands back into the business and lowered its gross margin guidance to 54.5%-55.5%, putting 40 bp of the cut on that move and 60 bp on higher costs. The reported figure therefore does not resolve the question on the original basis.
