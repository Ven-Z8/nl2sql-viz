# Test Questions Guide — What to Run on CSVs and Databases

> Companion to `2026-08-10-state-and-gaps.md`. This file tells the testing
> agent **exactly which questions to run** on both data-source types, **what
> "correct" looks like**, and **which questions are known to be fragile**.
>
> The user's bar: a question is only a pass if the answer is **correct** (the
> number matches the data), **tells a story** (key points, not a bare number
> dump), and **renders a sensible chart**. A query that "runs" but returns a
> wrong number is a FAIL.

---

## 1. The two data-source types

| | **CSV samples** | **Relational databases** |
| --- | --- | --- |
| UI tab | "CSV" | "Databases" |
| Structure | 1 flat table (`upload_*`) | 2–24 tables with FKs (`ds_*`) |
| Questions | Flat list of 6 per sample | Tiered ladder: easy/medium/hard/very_complex |
| Where defined | `data/samples/manifest.json` | `data/datasets/<id>/questions.json` |
| Loaded via | `POST /api/samples/<id>/load` | `POST /api/datasets/<id>/load` |
| Focus table | none (single table) | set to the dataset's primary table |

**Testing flow (UI):** start servers → load a sample (CSV tab) or a dataset
(Databases tab) → click each question → record the result.

---

## 2. Databases — the question ladders to run

Run **every question** in each dataset's ladder. The full lists are in
`data/datasets/<id>/questions.json`; the ladders are reproduced below so the
agent can log them without opening files.

### olist (retail) — 12 questions
- **easy:** Which payment methods are used most often across orders? · How does order volume vary by order status? · Which product categories appear most frequently in orders?
- **medium:** What does the average order value look like by customer state? · Compare total revenue across seller states · What is the distribution of review scores across all orders?
- **hard:** Show the monthly revenue trend with a 3-month rolling average · How has the share of each payment method changed month over month? · What is the relationship between review score and order value?
- **very_complex:** Compare 2017 vs 2018 growth by product category: which categories gained share, which lost it, and what drove the shift? · Analyze delivery performance: how does delivery time vary by state, which states are fastest, and does faster delivery correlate with higher review scores? · Which customers drive the most revenue, what do they have in common, and how does their purchasing behavior differ from the average customer?

### retail (retail, generated) — 12 questions
- **easy:** Which sales channels contribute the most orders? · How does revenue break down by region? · Which product categories sell the most units?
- **medium:** What does average order value look like by customer segment? · Compare payment method usage across sales channels · What is the distribution of order values across all orders?
- **hard:** Show the monthly revenue trend by channel · How has revenue per customer evolved month over month? · What is the relationship between product price and total units sold?
- **very_complex:** Compare Q4 vs Q3 performance by region: which regions grew, which categories drove the growth, and what was the channel mix impact? · Analyze customer retention: what share of customers return for a second purchase, how does retention vary by segment, and which segment retains best? · Which products are the most profitable per unit sold, and how does profitability vary across categories and regions?

### fdic (finance) — 11 questions
- **easy:** Which states host the most active banks? · How does the banking industry break down by bank class? · Which states hold the largest banking assets?
- **medium:** Compare average return on equity across bank classes · What does the distribution of bank asset sizes look like? · Which cities are home to the largest banks by assets?
- **hard:** Show the quarterly trend in total industry assets · How has aggregate bank net income evolved quarter over quarter? · What is the relationship between bank size and return on equity?
- **very_complex:** ⚠️ Compare 2020 vs 2024 profitability: how did return on equity and net income shift by bank class, which classes improved most, and what drove the change? · Analyze banking concentration: how much of industry assets do the top 10 banks hold, how has that share changed over time, and which regions are most concentrated?

### finance (finance, generated) — 11 questions
- **easy:** Which account types hold the most balance? · How does transaction volume break down by category? · Which loan statuses are most common?
- **medium:** Compare average loan amounts across customer segments · What does the distribution of account balances look like? · Which regions generate the most transaction activity?
- **hard:** Show the monthly transaction volume trend · How has the average loan size changed quarter over quarter? · What is the relationship between loan amount and interest rate?
- **very_complex:** Compare Q4 vs Q3 spending by category: which categories grew, which customer segments drove the growth, and what was the transaction mix impact? · Analyze loan risk: how does the default rate vary by segment and region, which segments are riskiest, and how do riskier loans compare on interest rate?

### healthcare (healthcare, generated) — 11 questions
- **easy:** Which departments handle the most encounters? · How does patient volume break down by payer? · Which diagnoses are the most common?
- **medium:** Compare average length of stay across departments · What does the distribution of patient ages look like? · Which regions carry the highest total procedure costs?
- **hard:** Show the monthly admission trend · How has the average length of stay changed quarter over quarter? · What is the relationship between length of stay and procedure cost?
- **very_complex:** Analyze readmission patterns: which departments have the highest return rates, how does severity affect readmission, and what is the cost impact? · Analyze the payer mix: how has the share of each payer changed over time, which payers carry the highest costs, and how does that vary by department?

### census (demographics) — 11 questions
- **easy:** Which states have the largest populations? · How does median income vary across states? · Which states have the highest poverty rates?
- **medium:** Compare commute mode usage (driving vs transit vs walking) across the largest states · What does the distribution of median income look like across counties? · Which counties have the largest populations?
- **hard:** Show the relationship between median income and poverty rate by county · How does the racial composition vary across the largest states? · What is the relationship between commute time and transit usage?
- **very_complex:** Compare the wealthiest vs poorest counties: how do employment, education, and commute patterns differ between them, and which states host both? · Analyze the aging population: which states have the highest share of elderly residents, how does that correlate with income and labor force participation, and what does it imply for the workforce?

### worldbank (demographics) — 11 questions
- **easy:** How does life expectancy vary across world regions? · Which countries have the largest populations? · How does GDP per capita compare across income groups?
- **medium:** ⚠️ Compare internet adoption between high-income and low-income countries · What does the distribution of GDP growth look like across countries? · Which world regions show the highest unemployment?
- **hard:** Show the population trend for the world's largest economies since 2000 · ⚠️ How has global life expectancy evolved over the past 30 years? · ⚠️ What is the relationship between GDP per capita and internet usage?
- **very_complex:** ⚠️ Compare the development gap: how do life expectancy, internet usage, and fossil fuel consumption differ between income groups, and which gap has widened over time? · Analyze economic growth: which countries grew fastest from 2000 to 2020, what do they have in common, and how did their inflation and trade patterns compare?

### demographics_census (demographics, generated) — 11 questions
- **easy:** Which states have the most households? · How does the housing mix break down by home type? · Which area types (urban vs rural) hold more households?
- **medium:** Compare average household size between urban and rural areas · What does the distribution of individual income look like? · How does employment status vary across education levels?
- **hard:** Show the income distribution by education level · What is the relationship between age and individual income? · How does the employment mix vary across states?
- **very_complex:** Compare urban vs rural households: how do income, education, and employment differ, and which areas show the biggest opportunity gaps? · Analyze the workforce: what does the employment profile look like by education and region, which groups face the highest unemployment, and how does that correlate with income?

### demographics_consumer (demographics, generated) — 11 questions
- **easy:** Which product categories drive the most purchases? · How does spending break down by income bracket? · Which regions have the most consumers?
- **medium:** Compare average purchase amounts across income brackets · What does the distribution of purchase amounts look like? · How does category preference vary by gender?
- **hard:** Show the monthly spending trend · How has spending changed quarter over quarter by category? · What is the relationship between age and purchase amount?
- **very_complex:** Compare Q4 vs Q3 spending by category: which categories grew, which income brackets drove the growth, and what were the preference shifts? · Analyze consumer segments: which age and income groups spend the most per purchase, how do their category preferences differ, and what drives the difference?

### tpcds (operations) — 11 questions
- **easy:** Which sales channels (store, catalog, web) generate the most revenue? · Which item categories sell the most units? · How does revenue break down across sales channels?
- **medium:** Compare average item prices across categories · What is the distribution of item list prices? · Which channels have the highest return rates?
- **hard:** Show the monthly store sales trend · How has web sales revenue evolved quarter over quarter? · What is the relationship between item price and quantity sold?
- **very_complex:** Compare store vs web sales: how do the revenue trends differ over time, which categories drive the difference, and what is the return impact? · Analyze inventory risk: which items have the highest stockout risk relative to sales, how does it vary by warehouse, and which items need restocking?

### cms (healthcare) — 11 questions
- **easy:** Which DRG codes appear most often in inpatient claims? · How does claim volume break down by year? · Which providers handle the most claims?
- **medium:** Compare average payment amounts across the top DRG codes · What does the distribution of claim payment amounts look like? · Which admission diagnoses are the most common?
- **hard:** Show the monthly claim volume trend · How has the average length of stay changed quarter over quarter? · What is the relationship between length of stay and payment amount?
- **very_complex:** Compare 2008 vs 2010 inpatient costs: how did average payment and length of stay change, which DRGs drove the increase, and what was the deductible impact? · Analyze high-cost patients: which beneficiaries accumulate the most Medicare spend, what are their common diagnoses, and how does their length of stay compare to the average?

### ga (marketing) — 11 questions
- **easy:** How does trip volume compare between members and casual riders? · Which rideable types are used the most? · Which start stations see the most trips?
- **medium:** Compare average trip duration between members and casual riders · How does trip volume vary by day of week? · What is the distribution of trip durations?
- **hard:** Show the monthly trip volume trend by member type · How does trip duration vary by hour of day for members vs casual riders? · Which station pairs (start to end) are the most common routes?
- **very_complex:** Compare member vs casual rider behavior: how do trip duration and peak usage hours differ, and which station areas show the biggest seasonal swings? · Analyze usage patterns: how did trip volume and average duration change from Q1 to Q4 2021 by rideable type, and which type drove the growth?

---

## 3. CSV samples — the questions to run

Load each sample from the **CSV tab** and run its 6 questions (from
`data/samples/manifest.json`). All are single-table.

### finance_lending — Lending Club Loans (real, 2.2M rows, 151 cols)
1. What is the average loan amount by grade?
2. What is the total loan amount by year?
3. What is the average interest rate by loan status?
4. How many loans are fully paid vs defaulted?
5. What is the average annual income by home ownership?
6. What is the average installment by term?

### retail_online — Online Retail (real, 542K rows)
1. What is the total revenue by country?
2. What is the average order value by country?
3. Show monthly revenue over time
4. Which products are the top 10 best sellers by quantity?
5. What is the refund rate by month?
6. How many orders are there per country?

### finance_bankruptcy — Bankruptcy Risk (real, 6.8K rows, 96 cols)
1. How many companies are bankrupt?
2. What is the average debt ratio by bankruptcy status?
3. What is the average return on assets by bankruptcy status?
4. What is the average current ratio?
5. What is the average net income to total assets?
6. How many companies have a debt ratio above 50%?

### marketing_shoppers — Online Shoppers (real, 12.3K rows)
1. What is the conversion rate by visitor type?
2. What is the average page value by month?
3. Which months have the highest revenue?
4. What is the average bounce rate by region?
5. How many sessions are there per month?
6. What is the conversion rate by traffic type?

### retail_orders — Retail Orders (2K rows)
1. What is the total revenue by region?
2. What is the average order value by category?
3. Show monthly revenue over time
4. Which products are the top 5 best sellers by quantity?
5. What is the refund rate by category?
6. How many orders are there per region?

### healthcare_encounters — Healthcare Encounters (1.5K rows)
1. What is the average length of stay by department?
2. What is the total cost by payer?
3. How many encounters are there per department?
4. What is the readmission rate by diagnosis?
5. Show monthly admissions over time
6. What is the average cost per encounter by department?

### finance_transactions — Finance Transactions (1.5K rows)
1. What is the total transaction amount by product?
2. What is the average transaction amount by channel?
3. How many transactions are there per product?
4. What is the refund rate by channel?
5. Show monthly transaction volume over time
6. What is the total revenue by channel?

### marketing_campaigns — Marketing Campaigns (1.5K rows)
1. What is the return on ad spend (ROAS) by channel?
2. What is the total spend by campaign?
3. What is the click-through rate by channel?
4. Which campaigns have the highest revenue?
5. Show monthly spend over time
6. What is the cost per lead by channel?

### saas_usage — SaaS Product Usage (1.5K rows)
1. What is the total MRR by plan?
2. What is the churn rate by plan?
3. What is the average sessions per user by plan?
4. Which features have the highest adoption?
5. Show signups over time
6. What is the average MRR per active user?

### supply_chain_shipments — Supply Chain Shipments (1.5K rows)
1. What is the average lead time by warehouse?
2. What is the total cost by warehouse?
3. What is the on-time delivery rate by warehouse?
4. How many shipments are delayed?
5. Show shipment volume over time
6. What is the average cost per shipment by SKU?

### hr_employees — HR Employees (1.5K rows)
1. What is the attrition rate by department?
2. What is the average salary by department?
3. What is the average tenure by role?
4. What is the average performance score by department?
5. How many employees are per department?
6. What is the salary distribution by role?

---

## 4. What "correct" looks like (verification criteria)

For **every** question, check all four:

1. **Result produced** — a `result` event, not an `error` event.
2. **SQL is right** — inspect the SQL: does it query the right tables/columns?
   Does it filter the right thing (e.g. World Bank questions MUST filter
   `indicator_code`)? A query that runs but reads the wrong table/column is a
   FAIL.
3. **Answer is correct** — spot-check the numbers against the data (run the
   SQL manually in psql, or sanity-check: revenue ≈ known figure, averages in
   plausible ranges). A wrong number is a FAIL even if the query ran.
4. **Answer tells a story** — the user's #2 complaint: the answer should give
   key points / an insight ("Revenue grew 18% YoY, driven by X in region Y"),
   not just `"Total Revenue: 16,008,872.12"` or a pipe-joined metric list.
   **Bare-number answers are a FAIL against the current product bar.**
5. **Chart renders** — a sensible chart for the question type (line for
   trends, bar for breakdowns, scatter for correlations). No chart for a
   chartable question is a FAIL.

**Per question type:**
| Type | Expected answer shape | Expected chart |
| --- | --- | --- |
| KPI | single grounded number + context | stat strip (no chart) |
| BREAKDOWN | per-group values + top/bottom insight | bar |
| TREND | time series + direction/change insight | line |
| COMPARISON | both sides + which is bigger and why | grouped bar |
| DISTRIBUTION | bucket/spread + shape insight | bar/histogram |
| very_complex | multi-section report, each section with a takeaway | chart of primary result |

---

## 5. Known-fragile questions (probe these first)

Marked ⚠️ in the ladders above. These are the most likely to fail:

1. **worldbank — any question naming an indicator** (life expectancy, GDP,
   internet usage, fossil fuel). Known failure: the model averages ALL
   indicators instead of filtering `indicator_code = 'SP.DYN.LE00.IN'` etc.
   The `indicators` table has the names — the model must join/filter on it.
2. **fdic — "Compare 2020 vs 2024 profitability…"** — previously returned
   "All planned queries returned zero rows."
3. **tpcds — very_complex questions** — 24-table schema, the linker and
   planner have the most work; joins can pick wrong tables.
4. **Any question with no focus table** (connect-your-own DSN path) — the
   linker sees all ~40 tables and can pick a plausible-but-wrong one.
5. **cms — date questions** — `CLM_FROM_DT` is TEXT `YYYYMMDD`; the model must
   parse it (e.g. `LEFT(CLM_FROM_DT, 4)` or `to_date`) for year/month grouping.
6. **ga — "Which station pairs are the most common routes?"** — needs a
   self-join or group-by-two-columns; check the SQL is sensible.

---

## 6. Report format

Return a table/list of every question run with:

```
Dataset/Sample | Tier | Question | Result (PASS/FAIL) | SQL correct? | Answer correct? | Story? | Chart? | Time | Notes
```

For each FAIL, include: the exact question, what happened (error message or
wrong behavior), and what the correct behavior should be. The user will use
this list to drive the next fix round.

---

## 7. How to run the questions programmatically (optional)

Instead of clicking the UI, the benchmark runner can execute a ladder and save
results:

```bash
uv run python -m scripts.benchmark <dataset_id> 10        # databases
```

For CSV samples there is no ladder runner — use the UI (load sample → click
questions) or drive the WebSocket directly. The UI is the source of truth for
what the user experiences.