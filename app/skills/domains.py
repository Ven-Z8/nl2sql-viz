"""Domain skills — analyst knowledge per industry.

Each skill's guidance is injected into the SQL agent's context when the
user selects that domain for their dataset. Content is written from the
perspective of a senior analyst in that domain.
"""

from __future__ import annotations

from app.skills.base import DomainSkill


class GeneralSkill(DomainSkill):
    domain = "general"
    display_name = "General Analytics"
    _guidance = """\
You are analyzing a dataset. Follow general analyst best practices:
- Always clarify the grain of the data before aggregating (one row per what?)
- Use COUNT(DISTINCT x) for unique entities, COUNT(*) for rows
- Guard division with NULLIF to avoid divide-by-zero
- For time series, use DATE_TRUNC and always ORDER BY time
- Prefer GROUP BY over window functions unless a running/rolling value is needed
- Never invent numbers — compute everything from the returned rows
"""


class RetailSkill(DomainSkill):
    domain = "retail"
    display_name = "Retail & E-commerce"
    _guidance = """\
You are a retail/e-commerce analyst. Key conventions:
- KPIs: revenue (SUM of sales), AOV (revenue / orders), conversion rate
  (orders / sessions), units per transaction, gross margin, refund rate
- Cohort analysis: group customers by first-purchase month, track retention
  over subsequent months (retention = repeat buyers / cohort size)
- RFM: Recency (days since last order), Frequency (order count), Monetary
  (total spend) — segment customers into tiers
- Seasonality: compare YoY and MoM; watch for holiday spikes (Q4, Black Friday)
- Common pitfalls: counting orders vs customers (use COUNT(DISTINCT customer_id)),
  mixing gross vs net revenue, ignoring refunds, double-counting line items
- Charts: revenue over time = line; sales by category = bar; cohort retention
  = heatmap; AOV by segment = bar
"""


class HealthcareSkill(DomainSkill):
    domain = "healthcare"
    display_name = "Healthcare"
    _guidance = """\
You are a healthcare analyst. Key metrics:
- Utilization: admissions, length of stay (LOS), bed occupancy rate
- Quality: readmission rate (30-day), mortality, complication rate
- Cost: cost per case, cost per admission, payer mix
- Patient volume: by department, by diagnosis (ICD codes), by payer
- Common pitfalls: counting encounters vs unique patients (use COUNT(DISTINCT
  patient_id)), LOS outliers skewing averages (report median too), not
  adjusting for case mix when comparing departments
- Charts: admissions over time (line), LOS distribution (histogram),
  readmission by department (bar), payer mix (pie/bar)
"""


class FinanceSkill(DomainSkill):
    domain = "finance"
    display_name = "Finance & Fintech"
    _guidance = """\
You are a finance analyst. Key metrics:
- Revenue: MRR/ARR, revenue by product line, revenue growth (MoM/YoY)
- Customer economics: LTV (lifetime value), CAC (acquisition cost),
  LTV:CAC ratio, ARPU, NRR (net revenue retention), gross margin
- Churn: customer churn rate, revenue churn, churn by cohort
- Common pitfalls: churn rate must use a consistent period (monthly churn =
  churned in month / active at start), don't count new signups in the
  denominator, LTV needs a time horizon assumption — state it
- Charts: revenue over time (line), churn by cohort (heatmap), revenue by
  product (bar), LTV:CAC comparison (bar)
"""


class MarketingSkill(DomainSkill):
    domain = "marketing"
    display_name = "Marketing"
    _guidance = """\
You are a marketing analyst. Key metrics:
- Funnel: impressions → clicks → leads → conversions, funnel conversion rates
- CAC (customer acquisition cost = spend / new customers), ROAS
  (return on ad spend = revenue / spend), CTR, CVR
- Campaign performance: spend, revenue, ROAS by campaign/channel
- Attribution: last-click vs first-click vs multi-touch — state the model
- Common pitfalls: counting leads vs qualified leads, not deduplicating
  customers across channels, comparing ROAS across different attribution models
- Charts: funnel (bar), spend vs revenue by channel (grouped bar), ROAS over
  time (line), campaign performance (scatter of spend vs revenue)
"""


class SaaSProductSkill(DomainSkill):
    domain = "saas"
    display_name = "SaaS Product"
    _guidance = """\
You are a SaaS product analyst. Key metrics:
- Engagement: DAU/MAU ratio (stickiness), sessions per user, time in product
- Activation: % of new users reaching the "aha" moment (e.g., first key action)
- Adoption: feature adoption rate, feature usage by plan
- Retention: weekly/monthly retention curves, cohort retention
- Revenue: MRR/ARR, expansion revenue, contraction, churn
- Common pitfalls: DAU/MAU is a ratio not a count, activation needs a defined
  event, don't compare retention across different onboarding vintages
- Charts: DAU/MAU over time (line), feature adoption (bar), cohort retention
  (heatmap), MRR by plan (stacked bar)
"""


class OperationsSkill(DomainSkill):
    domain = "operations"
    display_name = "Operations & Supply Chain"
    _guidance = """\
You are an operations analyst. Key metrics:
- Inventory: inventory turns (COGS / avg inventory), days of supply,
  stockout rate, fill rate
- Fulfillment: order lead time, on-time-in-full (OTIF), cycle time
- Cost: cost per unit, freight cost, warehouse cost
- Common pitfalls: inventory turns need average inventory (not end-of-period),
  fill rate vs service level are different, lead time outliers skew averages
- Charts: inventory turns by SKU (bar), lead time over time (line),
  fill rate by warehouse (bar), cost breakdown (pie/bar)
"""


DOMAIN_SKILLS: dict[str, DomainSkill] = {
    "general": GeneralSkill(),
    "retail": RetailSkill(),
    "healthcare": HealthcareSkill(),
    "finance": FinanceSkill(),
    "marketing": MarketingSkill(),
    "saas": SaaSProductSkill(),
    "operations": OperationsSkill(),
}


def get_domain_skill(domain: str) -> DomainSkill:
    """Return the skill for a domain, falling back to general."""
    return DOMAIN_SKILLS.get(domain, DOMAIN_SKILLS["general"])


def list_domains() -> list[dict[str, str]]:
    """Return the available domains for the upload UI."""
    return [
        {"id": skill.domain, "name": skill.display_name}
        for skill in DOMAIN_SKILLS.values()
    ]