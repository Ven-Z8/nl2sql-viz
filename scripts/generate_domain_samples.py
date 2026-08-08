"""Generate realistic sample CSVs for every domain (schema-agnostic demo data)."""
import csv
import random
from datetime import date, timedelta

random.seed(7)

OUT_DIR = "data/samples"
N = 1500  # rows per dataset


def _write(name: str, header: list[str], rows: list[list]) -> None:
    with open(f"{OUT_DIR}/{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {name}.csv: {len(rows)} rows")


def _date(start: date, days: int) -> str:
    return (start + timedelta(days=random.randint(0, days))).isoformat()


def healthcare() -> None:
    depts = ["Cardiology", "Orthopedics", "Neurology", "Oncology", "Pediatrics", "Emergency"]
    payers = ["Medicare", "Medicaid", "Private", "Self-Pay", "Employer"]
    diagnoses = ["Hypertension", "Diabetes", "Fracture", "Pneumonia", "Asthma", "Migraine"]
    rows = []
    for i in range(1, N + 1):
        admit = _date(date(2024, 1, 1), 365)
        los = random.randint(1, 14)
        discharge = (date.fromisoformat(admit) + timedelta(days=los)).isoformat()
        rows.append([
            f"P{i}", f"E{i}", admit, discharge, random.choice(depts),
            random.choice(diagnoses), random.choice(payers), los,
            round(random.uniform(2000, 60000), 2),
            "readmitted" if random.random() < 0.12 else "discharged",
        ])
    _write("healthcare_encounters", [
        "patient_id", "encounter_id", "admission_date", "discharge_date",
        "department", "diagnosis", "payer", "length_of_stay_days", "cost", "outcome",
    ], rows)


def finance() -> None:
    channels = ["Web", "Mobile", "Branch", "Partner", "API"]
    products = ["Checking", "Savings", "Credit Card", "Loan", "Mortgage", "Investment"]
    rows = []
    for i in range(1, N + 1):
        rows.append([
            f"T{i}", f"C{random.randint(1000, 1999)}", _date(date(2024, 1, 1), 365),
            random.choice(products), random.choice(channels),
            round(random.uniform(10, 5000), 2),
            random.choice(["completed", "completed", "completed", "refunded", "pending"]),
        ])
    _write("finance_transactions", [
        "transaction_id", "customer_id", "transaction_date", "product", "channel",
        "amount", "status",
    ], rows)


def marketing() -> None:
    channels = ["Google Ads", "Facebook", "Instagram", "Email", "LinkedIn", "TikTok"]
    campaigns = [f"Campaign {c}" for c in range(1, 13)]
    rows = []
    for i in range(1, N + 1):
        impressions = random.randint(10000, 500000)
        clicks = int(impressions * random.uniform(0.01, 0.05))
        leads = int(clicks * random.uniform(0.05, 0.2))
        spend = round(random.uniform(500, 20000), 2)
        revenue = round(spend * random.uniform(0.5, 4.0), 2)
        rows.append([
            f"M{i}", random.choice(campaigns), random.choice(channels), _date(date(2024, 1, 1), 365),
            impressions, clicks, leads, spend, revenue,
        ])
    _write("marketing_campaigns", [
        "campaign_id", "campaign_name", "channel", "date",
        "impressions", "clicks", "leads", "spend", "revenue",
    ], rows)


def saas_usage() -> None:
    plans = ["Free", "Pro", "Business", "Enterprise"]
    features = ["Dashboard", "Reports", "API", "Automation", "Integrations", "AI Insights"]
    rows = []
    for i in range(1, N + 1):
        rows.append([
            f"U{i}", _date(date(2023, 1, 1), 500), random.choice(plans), random.choice(features),
            random.randint(0, 200), random.randint(0, 30),
            round(random.uniform(0, 500), 2),
            random.choice(["active", "active", "active", "churned", "trial"]),
        ])
    _write("saas_usage", [
        "user_id", "signup_date", "plan", "top_feature",
        "sessions", "days_active", "mrr", "status",
    ], rows)


def operations() -> None:
    warehouses = ["East DC", "West DC", "Central DC", "South DC"]
    skus = [f"SKU{random.randint(1000, 9999)}" for _ in range(50)]
    rows = []
    for i in range(1, N + 1):
        order = _date(date(2024, 1, 1), 365)
        lead = random.randint(1, 14)
        ship = (date.fromisoformat(order) + timedelta(days=lead)).isoformat()
        rows.append([
            f"S{i}", random.choice(skus), random.choice(warehouses), order, ship,
            lead, random.randint(1, 500), round(random.uniform(5, 200), 2),
            random.choice(["delivered", "delivered", "delivered", "delayed", "in_transit"]),
        ])
    _write("supply_chain_shipments", [
        "shipment_id", "sku", "warehouse", "order_date", "ship_date",
        "lead_time_days", "quantity", "cost", "status",
    ], rows)


def hr_people() -> None:
    depts = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations"]
    roles = ["Manager", "Senior", "Junior", "Intern", "Director"]
    rows = []
    for i in range(1, N + 1):
        hire = _date(date(2019, 1, 1), 1)
        tenure = (date(2024, 12, 31) - date.fromisoformat(hire)).days // 30
        rows.append([
            f"E{i}", random.choice(depts), random.choice(roles), hire, tenure,
            random.randint(40000, 180000), round(random.uniform(1, 5), 1),
            random.choice(["active", "active", "active", "active", "left"]),
        ])
    _write("hr_employees", [
        "employee_id", "department", "role", "hire_date", "tenure_months",
        "salary", "performance_score", "status",
    ], rows)


if __name__ == "__main__":
    healthcare()
    finance()
    marketing()
    saas_usage()
    operations()
    hr_people()
    print("done")