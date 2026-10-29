# Stage 6: diligence questions

`python -I models/questions/extract.py` merged 1,813 records: FinanceBench 150, FinLFQA 302, FinCausal 1,109, PE Bench 12, FinTextQA 240. `python -I models/questions/build_questions.py` adapts them to WD-40 and computes every answer from filings filed by 27 Oct 2025, the FY2025 8-K and 10-K passages, or the model. The adapted set is not a benchmark result.

Each topic starts from a judgement question. Following The Mom Test, the judgement is not asked directly: it is split into questions about specific past facts, then a question about which model input those facts test. Forecast questions state the object, period, threshold and resolution rule. Where later filings already resolve them, the result is shown and labelled as information from after the case date.

| Source | Records | Used as origin | Note |
|---|---:|---:|---|
| FinanceBench | 150 | 16 |  |
| FinLFQA | 302 | 3 |  |
| FinCausal | 1,109 | 1 | 34 cause-effect pairs mention input costs, currencies, tariffs or freight; they are news texts about other companies, so they shape the form of the risk questions rather than supplying them. |
| PE Bench | 12 | 5 |  |
| FinTextQA | 240 | 0 | The public part is 240 questions on banking regulation (Federal Reserve, HKMA, EU). None applies to a non-bank consumer products company; the textbook part was not released. |

## Revenue growth

**Is WD-40's revenue growth in line with the growth the scenarios assume?**

FinanceBench asks whether a company's financials are those of a high-growth company and what drove revenue change. The WD-40 version asks the same about the years the scenarios extrapolate from, then tests the scenario inputs against them.

Origins: FinanceBench `financebench_id_00956` (Are JnJ's FY2022 financials that of a high growth company?); FinanceBench `financebench_id_01198` (What drove revenue change as of the FY22 for AMD?)

- *fact*: What were net sales in FY2021 and FY2025, and the compound annual growth rate between them?  
  $488.1m in FY2021 and $620.0m in FY2025: 6.2% a year.
- *fact*: How much of the FY2025 change in net sales came from volume, price and currency?  
  Volume added about $25.2m, price about $5.6m and currency translation took off $1.4m, on a $29.4m increase.
- *fact*: What growth did management guide for FY2026, from what base and at what exchange rates?  
  5-9% from FY2025 pro forma results, which exclude the Americas homecare and cleaning brands held for sale, at FY2025 average exchange rates: $630-655m.
- *assumption*: Which growth rates do the scenarios use after year 1, and how do they compare with the FY2021-FY2025 rate?  
  Bear 4%, Base 6%, Bull 7% a year in years 2-5, against 6.2% actual. Year 1 is set at the guidance range on the reported base: 1.6%, 3.6%, 5.6%.
- *forecast*: Will FY2026 net sales on the guidance basis (pro forma, FY2025 exchange rates) reach the $642.5m midpoint?  
  Open at the case date. Status: open at case date.
  Resolution: Compare the constant-currency pro forma net sales in the FY2026 results release with $642.5m. Threshold $642.5m; linked to Input sheet!B26 (Base 3.63%).
  Later information (after the case date): The FY2026 10-K reports net sales of $688.0m. That figure is on the reported basis: it includes the Americas homecare brands the company decided to keep and currency translation, so it does not resolve the question on the guidance basis.

## Margins

**Does WD-40's margin history support the Base path from 16.9% to 18%?**

FinanceBench asks whether margins are improving and what drove the change. Here the facts are the filed margins and the drivers named in the FY2025 10-K, and the last question checks the Base path against them.

Origins: FinanceBench `financebench_id_00684` (Does AMCOR have an improving gross margin profile as of FY2023? If gross margin is not a useful metric for a c…); FinanceBench `financebench_id_01226` (What drove operating margin change as of FY2022 for 3M? If operating margin is not a useful metric for a compa…); FinanceBench `financebench_id_00685` (Are Best Buy's gross margins historically consistent (not fluctuating more than roughly 2% each year)? If gros…)

- *fact*: What was the gross margin in each fiscal year from 2021 to 2025?  
  FY2021 54.0%, FY2022 49.1%, FY2023 51.0%, FY2024 53.4%, FY2025 55.1%. It moved by more than 2 points in FY2022 and FY2023.
- *fact*: What explained the change in gross margin from FY2024 to FY2025?  
  Lower specialty chemical costs (+80 bp), lower aerosol can costs (+60 bp) and higher average selling prices (+50 bp), less higher warehousing, distribution and freight costs (-50 bp); 30 bp of the 170 bp rise is not attributed in the filing.
- *fact*: What was the operating margin in each fiscal year from 2021 to 2025?  
  FY2021 18.2%, FY2022 16.8%, FY2023 16.7%, FY2024 16.3%, FY2025 16.7%.
- *fact*: How far was FY2025 cost of doing business from the company's own target?  
  37% of net sales against a long-term target of 30%; gross margin was at its 55% target and adjusted EBITDA was 18% against 25%.
- *assumption*: Which margin paths do the scenarios use, and on what basis?  
  Year-1 margins come from operating-income guidance plus the workbook's R&D adjustment: 16.7%, 16.9%, 17.1%. Targets by year 5: Bear stays flat, Base 18%, Bull 20%. FY2017-FY2020 averaged 19.4% reported.

## Capital intensity and reinvestment

**Does WD-40 need as much capital to grow as the sales-to-capital ratio of 2.0 implies?**

FinanceBench asks whether a company is capital-intensive and how fast it turns inventory; PE Bench asks for a working-capital peg. Here those facts test the single reinvestment input of the DCF.

Origins: FinanceBench `financebench_id_00499` (Is 3M a capital-intensive business based on FY2022 data?); FinanceBench `financebench_id_00540` (Roughly how many times has AES Corporation sold its inventory in FY2022? Calculate inventory turnover ratio fo…); PE Bench `voltaic-05-nwc-peg` (We're putting together a first-round bid for Project Voltaic. Work out the net working capital we'd assume, ho…)

- *fact*: What were capital expenditures as a share of net sales in each year from FY2021 to FY2025?  
  FY2021 3.1%, FY2022 1.6%, FY2023 1.3%, FY2024 0.7%, FY2025 0.7%. FY2025 capex was $4.5m against depreciation and amortization of $8.2m.
- *calculation*: How many times did inventory turn in FY2025 (cost of products sold over average inventory)?  
  3.51 times: $278.6m over average inventory of $79.5m.
- *calculation*: What were receivables plus inventory minus payables at the end of FY2025, as a share of FY2025 net sales?  
  $162.5m, or 26.2% of net sales.
- *calculation*: How much revenue did each dollar of added invested capital bring between FY2021 and FY2025?  
  Net sales rose $131.9m. Book equity plus borrowings minus cash rose from $230.2m to $297.0m, so each added dollar brought about $1.97 of revenue. This book measure excludes the capitalized R&D the workbook adds.
- *assumption*: Which sales-to-capital ratio does the model use, and does the history above support it?  
  2.0 in years 1-10 in every case. The FY2021-FY2025 book measure is close to 2, so the ratio is not changed in the scenarios.

## Cash conversion

**How much of WD-40's profit turns into cash?**

FinanceBench asks which cash-flow category brought in the most cash; FinLFQA asks for free-cash-flow comparisons with evidence. Both are answered here from the filed cash-flow statements.

Origins: FinanceBench `financebench_id_01279` (Among operations, investing, and financing activities, which brought in the most (or lost the least) cash flow…); FinLFQA `validation-14` (How does the net cash flow from operating activities differ between CWT and WEC for the first three months of …)

- *fact*: What were operating cash flow and capital expenditures in each year from FY2021 to FY2025?  
  FY2021 $84.7m and $15.1m; FY2022 $2.6m and $8.3m; FY2023 $98.4m and $6.9m; FY2024 $92.0m and $4.2m; FY2025 $87.9m and $4.5m. FY2022 operating cash flow was low because inventory rose by $52.7m.
- *calculation*: What was free cash flow (operating cash flow minus capex) as a share of net income in FY2023, FY2024 and FY2025?  
  FY2023 139%, FY2024 126%, FY2025 92%. FY2025 net income includes an $11.9m one-time tax benefit.
- *fact*: Among operating, investing and financing activities, which brought in the most cash in FY2025?  
  Operating activities: $87.9m. Investing used $2.4m and financing used $74.1m.

## Taxes

**Which tax rate should the forecast start from?**

FinanceBench asks how much the effective tax rate changed between two years. The WD-40 version adds the cause of the change and the rate the model starts from.

Origins: FinanceBench `financebench_id_01351` (How much has the effective tax rate of American Express changed between FY2021 and FY2022?)

- *calculation*: How much did the effective tax rate change between FY2024 and FY2025?  
  From 23.9% to 10.5%: -13.4 points.
- *fact*: What one-time item explains the FY2025 rate?  
  An $11.9m release of a reserve for an uncertain tax position. Without it the FY2025 rate is 22.2%.
- *assumption*: Which starting tax rate do the scenarios use?  
  Bear 23.5%, Base 23.0%, Bull 22.5%, from the FY2026 guidance range of 22.5-23.5%; the original case uses the normalized 22.2%. All fade to 25% by year 10.

## Cost of capital

**What discount rate do market data support for WD-40 at 29 Aug 2025?**

FinLFQA's WACC questions ask for the inputs behind a cost of capital with evidence; PE Bench requires a declared pricing date. Each input here carries its date and source.

Origins: FinLFQA `validation-179` (How does the gross profit margin of CSL compare to SHW for the first quarter of 2024?); PE Bench `voltaic-02-comparables` (Build a trading comparables analysis and a precedent transactions analysis for Project Voltaic from the data r…)

- *fact*: What was the 10-year Treasury yield on 29 Aug 2025, and Damodaran's implied equity risk premium at the start of September 2025?  
  4.23% and 3.94%.
- *calculation*: What betas do regressions of WD-40 on the S&P 500 give, and how much of the variation do they explain?  
  2-year weekly: 0.13 (R² 0.006); 5-year weekly: 0.49 (R² 0.073); 3-year monthly: 0.62 (R² 0.105); 5-year monthly: 0.10 (R² 0.003). None explains more than 11% of WD-40's returns.
- *fact*: What were Damodaran's January 2025 unlevered betas for Chemical (Specialty) and Household Products?  
  0.79 and 0.83, corrected for cash.
- *assumption*: Which WACC do the scenarios use, and what did the original case use?  
  Bear 7.70% drifting to 8.32%, Base 7.40%, Bull 6.58%. The original case used 9% fading to 8%, labelled as an illustrative placeholder.

## Return on capital

**How long can WD-40 keep earning more than its cost of capital?**

FinLFQA's EVA questions ask how economic profit and capital efficiency compare across periods; FinanceBench asks whether any product exceeds 20% of revenue. Together they ask how durable WD-40's excess return is.

Origins: FinLFQA `validation-2` (How do changes in depreciation and amortization mean for CWT and AWK's investment strategies in Q1 2024?); FinanceBench `financebench_id_00517` (Are there any product categories / service categories that represent more than 20% of Boeing's revenue for FY2…)

- *calculation*: What was FY2025 return on invested capital in the workbook (after-tax operating income over invested capital)?  
  26.3%, on invested capital of $313.4m including capitalized R&D.
- *fact*: What share of FY2025 net sales came from WD-40 Multi-Use Product?  
  $478.0m of $620.0m, or 77.1%. WD-40 Specialist added $82.0m.
- *fact*: What share of FY2025 net sales came from outside the United States, and did any customer reach 10%?  
  About 66% came from outside the US. No customer reached 10% of consolidated net sales.
- *calculation*: Does restating the DCF as invested capital plus economic profit give the same operating value?  
  Yes. original $1,230.6m against $1,230.6m; bear $1,127.6m against $1,127.6m; base $1,737.6m against $1,737.6m; bull $2,950.2m against $2,950.2m. The two are the same calculation arranged differently, so this checks consistency, not value.
- *assumption*: What return on new capital after year 10 do the scenarios assume?  
  Bear: equal to the cost of capital (no excess return). Base: 15%. Bull: 20%. In years 1-10 the model earns 25% to 32% on capital across the four cases.

## Shareholder payouts

**Is the dividend sustainable at the scenarios' growth rates?**

FinanceBench asks whether a company paid dividends and whether it keeps a stable dividend trend. The WD-40 version adds payout and a dividend-based value.

Origins: FinanceBench `financebench_id_01244` (Has CVS Health paid dividends to common shareholders in Q2 of FY2022?); FinanceBench `financebench_id_01858` (Does 3M maintain a stable trend of dividend distribution?)

- *fact*: What dividend per share did WD-40 pay in each year from FY2021 to FY2025?  
  FY2021 $2.78, FY2022 $3.06, FY2023 $3.27, FY2024 $3.47, FY2025 $3.70. It rose every year.
- *calculation*: What share of FY2025 earnings per share went to dividends?  
  $3.70 paid against $5.82 non-GAAP diluted EPS (64%) or $6.69 GAAP EPS, which includes the one-time tax benefit (55%).
- *fact*: How did FY2025 share repurchases compare with dividends?  
  $12.3m of repurchases against $50.3m of dividends.
- *calculation*: What does a dividend discount model give with the scenarios' cost of equity?  
  Bear $84.16 (cost of equity 7.80%, terminal payout 74%); Base $121.42 (cost of equity 7.49%, terminal payout 83%); Bull $198.76 (cost of equity 6.65%, terminal payout 85%).

## Financing a buyout

**What could a financial buyer pay for WD-40?**

PE Bench asks for a debt schedule, sources and uses, and returns; FinanceBench asks whether debt rose. Together they test what a sponsor could pay for WD-40.

Origins: PE Bench `voltaic-08-debt-schedule` (Build free cash flow and the debt schedule for Project Voltaic onto the attached transaction model, from the 3…); PE Bench `voltaic-09-sources-uses` (We are acquiring 100% of Ironvale Digital Infrastructure (Project Voltaic). Build the transaction onto the att…); PE Bench `voltaic-11-returns-waterfall` (Build the exit, the distribution waterfall and the returns for Project Voltaic in the attached model, on the t…); FinanceBench `financebench_id_00552` (Has Microsoft increased its debt on balance sheet between FY2023 and the FY2022 period?)

- *fact*: How did borrowings change between the end of FY2024 and FY2025?  
  From $94.6m to $87.0m.
- *calculation*: What was FY2025 operating income over interest expense?  
  30 times: $103.8m over $3.44m.
- *calculation*: At 5.0 times FY2025 EBITDA of debt, SOFR on 29 Aug 2025 plus 3.5%, a 20% target return and an exit at the peer median multiple, what is the highest price per share that works?  
  $75.86, an entry multiple of 9.5 times EBITDA. Bear (4.5x debt, 25% target, 25th percentile exit) gives $65.89; Bull (5.5x, 17.5%, 75th percentile) $107.90.
- *assumption*: Which operating case does the buyout model use?  
  The Base DCF case: its revenue, EBIT, tax rate and free cash flow before financing in years 1-5. EBITDA is put on a reported basis by removing the R&D adjustment and adding depreciation and amortization at the FY2025 share of sales.

## Market pricing

**What does the $216.04 price assume that the cases do not?**

PE Bench requires peers and the target on one EBITDA definition; FinanceBench asks whether operating margin is improving. Here the facts measure how far the price sits from each method.

Origins: PE Bench `voltaic-02-comparables` (Build a trading comparables analysis and a precedent transactions analysis for Project Voltaic from the data r…); FinanceBench `financebench_id_00438` (Does Adobe have an improving operating margin profile as of FY2022? If operating margin is not a useful metric…)

- *calculation*: What EV to EBITDA did five listed peers trade at on 29 Aug 2025, after adding back tagged one-off charges?  
  25th percentile 11.1x, median 11.2x, 75th percentile 16.5x.
- *calculation*: What EV to EBITDA did WD-40 trade at on 29 Aug 2025, and at its previous four fiscal year-ends?  
  FY2021 34.6x, FY2022 28.0x, FY2023 30.5x, FY2024 34.1x, FY2025 26.4x.
- *calculation*: Starting from Base, what single change reaches $216.04?  
  A WACC of 5.40% in every year, or a 31.1% operating margin by year 5, or 19.0% revenue growth in years 2-5. No terminal return on capital reaches it alone: at 500% the value is $141.26.
- *fact*: What price targets had analysts published by 29 Aug 2025?  
  DA Davidson $300 (Buy, 11 Jul 2025) and Jefferies $280 (Hold, 18 Oct 2024). Other firms' targets were not found.
- *fact*: Can the company-defined adjusted EBITDA of $114.4m be reconciled to EBIT plus depreciation and amortization of $112.0m?  
  Not from the material collected. The $2.4m difference sits in the company's non-GAAP reconciliation, which was not extracted. Status: insufficient data.

## Threats to the business

**What could break the margin and growth assumptions?**

FinCausal extracts cause and effect from financial text; FinanceBench asks for restructuring costs and material legal matters. The WD-40 version asks which costs move margins and through what channel.

Origins: FinCausal `0037.00003`; FinanceBench `financebench_id_01319` (What is the quantity of restructuring costs directly outlined in AES Corporation's income statements for FY202…); FinanceBench `financebench_id_01091` (Has Boeing reported any materially important ongoing legal battles from FY2022?)

- *fact*: Which inputs does WD-40 name as its main costs, and how does the price of oil reach them?  
  Specialty chemicals and aerosol cans. The 10-K says oil price volatility indirectly affects specialty chemical costs, many of which are indexed to refined oil products.
- *fact*: How did currency translation affect FY2025 net sales by segment?  
  Americas -$4.7m, EIMEA +$3.5m, Asia-Pacific -$0.2m: -$1.4m in total.
- *fact*: Are restructuring costs shown separately in the FY2025 income statement?  
  No restructuring line or restructuring fact appears in the FY2025 XBRL data, so the FinanceBench rule gives 0.
- *forecast*: Will the FY2026 gross margin stay within the guided 55.5-56.5% range?  
  Open at the case date. Status: open at case date.
  Resolution: Read gross margin from the FY2026 10-K income statement. Threshold 55.5% to 56.5%; linked to Input sheet!B27 and B29 (Base 16.9% and 18% operating margin).
  Later information (after the case date): The FY2026 10-K reports a gross margin of 55.3%, below the original range; the company lowered its guidance to 54.5-55.5% in July 2026.
