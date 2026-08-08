# Data Analyst Work Across Domains — Research Report

> Research for **DataLens AI** (NL2SQL copilot): what analysts actually compute in each
> domain, the patterns they run, the charts they use, the mistakes they avoid — and
> which public datasets showcase it best. Drives the domain-skill SKILL.md bundles and
> the demo dataset selection.

---

## 1. Retail & E-commerce

### Core KPIs (with definitions)
| KPI | Definition |
|---|---|
| Revenue / GMV | SUM of order amounts (gross vs net — net excludes refunds) |
| AOV (Average Order Value) | Revenue ÷ number of orders |
| Conversion rate | Orders ÷ sessions (or visitors) |
| Units per transaction | Total units ÷ orders |
| Gross margin | (Revenue − COGS) ÷ Revenue |
| Refund / return rate | Refunded orders ÷ total orders |
| Repeat purchase rate | Customers with ≥2 orders ÷ total customers |
| Cohort retention | Repeat buyers in month N ÷ cohort size (first-purchase month) |

**Analysis patterns:** cohort retention (first-purchase month → retention curve), RFM segmentation (Recency/Frequency/Monetary tiers), period-over-period (MoM/YoY), seasonality (Q4/holiday spikes), category mix, channel performance.

**Charts:** revenue over time → line; sales by category/region → bar; cohort retention → heatmap; AOV by segment → bar; funnel (browse→cart→checkout) → funnel bar.

**Pitfalls:** counting orders vs customers (`COUNT(DISTINCT customer_id)`), mixing gross/net, ignoring refunds, double-counting line items, comparing periods with different day counts.

**Showcase datasets:** Brazilian E-Commerce (Olist) — 100K orders, 9 tables (orders, customers, order_items, payments, sellers, geolocation); UCI Online Retail — ~540K rows single table; Superstore Sales — ~10K rows.

---

## 2. Healthcare

**Core KPIs:** admissions/encounters, length of stay (LOS), bed occupancy, 30-day readmission rate, mortality, cost per case, payer mix, patient volume by department/diagnosis.

**Analysis patterns:** utilization trends, LOS distribution (median over mean — outliers), readmission by department/diagnosis, payer mix, seasonal admission patterns.

**Charts:** admissions over time → line; LOS distribution → histogram; readmission by department → bar; payer mix → pie/bar.

**Pitfalls:** encounters vs unique patients (`COUNT(DISTINCT patient_id)`), LOS outliers skewing means, comparing departments without case-mix adjustment, date-of-discharge vs date-of-admission confusion.

**Demo datasets:** Medical Cost Personal (~1.3K rows), Hospital Inpatient Discharges (NY state, ~2.5M rows), MIMIC-IV (ICU, large, requires credentialing).

---

## 3. Finance / Fintech

**Core KPIs:** MRR/ARR, revenue growth (MoM/YoY), LTV, CAC, LTV:CAC ratio, ARPU, NRR (net revenue retention), gross margin, churn rate (customer + revenue).

**Analysis patterns:** cohort revenue retention, churn by cohort, revenue by product line, LTV:CAC comparison, period-over-period growth, expansion vs contraction revenue.

**Charts:** revenue over time → line; churn by cohort → heatmap; revenue by product → bar; LTV:CAC → grouped bar; growth rate → line.

**Pitfalls:** churn denominator (active at period start, not new signups), inconsistent churn periods, LTV time-horizon assumptions, mixing gross/net revenue.

**Demo datasets:** Telco Customer Churn (~7K rows), Credit Card Fraud (~285K rows), Lending Club loans (~2.2M rows).

---

## 4. Marketing

**Core KPIs:** funnel conversion (impressions→clicks→leads→customers), CAC (spend ÷ new customers), ROAS (revenue ÷ spend), CTR, CVR, campaign/channel performance.

**Analysis patterns:** funnel analysis, channel comparison, campaign ROAS, attribution (last-click vs first-click vs multi-touch — state the model), A/B test lift.

**Charts:** funnel → bar; spend vs revenue by channel → grouped bar; ROAS over time → line; campaign scatter (spend vs revenue).

**Pitfalls:** leads vs qualified leads, no dedup across channels, comparing ROAS across attribution models, not accounting for organic vs paid.

**Demo datasets:** Marketing Campaign (Maven, ~2.2K rows), Facebook Ad Campaign (~1.1K rows), Google Analytics sample.

---

## 5. SaaS Product Analytics

**Core KPIs:** DAU/MAU (stickiness), sessions per user, activation rate (% reaching "aha" event), feature adoption, weekly/monthly retention, MRR/ARR, expansion/contraction revenue, churn.

**Analysis patterns:** cohort retention curves, activation funnel, feature adoption by plan, MRR by plan over time, DAU/MAU trend.

**Charts:** DAU/MAU → line; feature adoption → bar; cohort retention → heatmap; MRR by plan → stacked bar.

**Pitfalls:** DAU/MAU is a ratio not a count, activation needs a defined event, comparing retention across different onboarding vintages, counting active users wrong.

**Demo datasets:** SaaS subscription datasets (synthetic), Amplitude/Heap public samples, app usage logs.

---

## 6. Operations / Supply Chain

**Core KPIs:** inventory turns (COGS ÷ avg inventory), days of supply, stockout rate, fill rate, OTIF (on-time-in-full), order lead time, cost per unit.

**Analysis patterns:** inventory turns by SKU, lead time trends, fill rate by warehouse, cost breakdown, stockout analysis.

**Charts:** inventory turns → bar; lead time → line; fill rate by warehouse → bar; cost breakdown → pie/bar.

**Pitfalls:** inventory turns need average inventory (not end-of-period), fill rate vs service level, lead time outliers.

**Demo datasets:** Supply Chain Shipment (~1.5K rows), Inventory datasets.

---

## 7. HR / People Analytics

**Core KPIs:** attrition rate, time-to-hire, headcount, engagement score, promotion rate, cost per hire.

**Analysis patterns:** attrition by department/tenure, headcount trends, time-to-hire by role, engagement drivers.

**Charts:** attrition by department → bar; headcount over time → line; tenure distribution → histogram.

**Demo datasets:** IBM HR Analytics (~1.5K rows), HR Employee Attrition.

---

## 8. What makes a good domain skill for an AI analytics tool

1. **Metric definitions with formulas** — the LLM must compute the right thing (e.g., churn = churned/active-at-start).
2. **Grain awareness** — one row per what? (orders vs customers vs line items).
3. **Pitfall guardrails** — the mistakes analysts make are the mistakes LLMs make (COUNT(DISTINCT), NULLIF, refunds).
4. **Chart conventions** — which chart for which pattern, so the viz layer picks well.
5. **Domain vocabulary** — AOV, ROAS, LTV, OTIF — so the LLM understands the question.

This is exactly what the SKILL.md bundles encode (frontmatter name/description + guidance body), injected into SQL generation.

---

## 9. Recommended demo datasets (for the CSV upload showcase)

| Domain | Dataset | Rows | Why it showcases well |
|---|---|---|---|
| Retail | Olist Brazilian E-commerce | ~100K orders (9 tables) | Cohorts, AOV, revenue by time/region/category |
| Retail | UCI Online Retail | ~540K rows | Big single-table, time series + RFM |
| Finance | Telco Customer Churn | ~7K rows | Churn cohorts, LTV-style analysis |
| Finance | Lending Club | ~2.2M rows | Large-scale, risk analytics |
| Healthcare | Hospital Inpatient Discharges | ~2.5M rows | Volume, LOS, cost |
| Marketing | Marketing Campaign | ~2.2K rows | Funnel, channel ROAS |
| SaaS | (synthetic) | — | Activation, retention, MRR |

**Best first pick for the demo:** the **Olist Brazilian E-Commerce** dataset (retail domain) — it exercises cohorts, AOV, time series, and category breakdowns, which are exactly the adaptive layouts (KPI strip, trend line, breakdown bar, heatmap) the UI supports. For a single-CSV upload, the **Online Retail (UCI)** file is the easiest big single-table test.

---

*Sources: Kaggle dataset pages (Olist, UCI Online Retail, Telco Churn, Lending Club, IBM HR), established analytics practice (RFM, cohort retention, funnel, LTV/CAC, DAU/MAU, inventory turns).*