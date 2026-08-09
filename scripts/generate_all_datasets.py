"""Generate complex relational datasets: healthcare, finance, demographics x2.

Each dataset: multi-table with FKs, ~0.4-1M rows, schema.json + questions.json.
"""
import csv
import json
import random
from datetime import date, timedelta

random.seed(23)

BASE = "data/datasets"


def _date(start: date, days: int) -> str:
    return (start + timedelta(days=random.randint(0, days))).isoformat()


def _write(dataset: str, name: str, header: list[str], rows: list[list]) -> None:
    with open(f"{BASE}/{dataset}/{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {dataset}/{name}.csv: {len(rows):,} rows")


def _write_json(dataset: str, name: str, data: dict) -> None:
    with open(f"{BASE}/{dataset}/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Healthcare ────────────────────────────────────────────────────────────
def healthcare() -> None:
    ds = "healthcare"
    n_patients = 50_000
    n_encounters = 200_000

    patients = []
    for i in range(1, n_patients + 1):
        patients.append([
            f"PT{i:06d}", f"Patient {i}", random.randint(0, 95),
            random.choice(["M", "F"]), random.choice(["North", "South", "East", "West"]),
        ])
    _write(ds, "patients", ["patient_id", "name", "age", "gender", "region"], patients)

    departments = ["Cardiology", "Orthopedics", "Neurology", "Oncology", "Pediatrics", "Emergency", "Internal Medicine"]
    payers = ["Medicare", "Medicaid", "Private", "Self-Pay", "Employer"]
    encounters = []
    diagnoses = []
    procedures = []
    for i in range(1, n_encounters + 1):
        patient = random.choice(patients)[0]
        admit = _date(date(2023, 1, 1), 700)
        los = random.randint(1, 20)
        discharge = (date.fromisoformat(admit) + timedelta(days=los)).isoformat()
        dept = random.choice(departments)
        encounters.append([
            f"ENC{i:07d}", patient, admit, discharge, dept, random.choice(payers), los,
        ])
        # 1-3 diagnoses per encounter
        for d in range(random.randint(1, 3)):
            diagnoses.append([
                f"DX{len(diagnoses)+1:08d}", f"ENC{i:07d}",
                f"ICD{random.randint(100, 999)}", f"Diagnosis {random.randint(1, 50)}",
                random.choice(["mild", "moderate", "severe"]),
            ])
        # 0-2 procedures per encounter
        for p in range(random.randint(0, 2)):
            procedures.append([
                f"PR{len(procedures)+1:08d}", f"ENC{i:07d}",
                f"Procedure {random.randint(1, 40)}", round(random.uniform(500, 50000), 2),
            ])
    _write(ds, "encounters", ["encounter_id", "patient_id", "admission_date", "discharge_date", "department", "payer", "length_of_stay_days"], encounters)
    _write(ds, "diagnoses", ["diagnosis_id", "encounter_id", "icd_code", "diagnosis_name", "severity"], diagnoses)
    _write(ds, "procedures", ["procedure_id", "encounter_id", "procedure_name", "cost"], procedures)

    _write_json(ds, "schema", {
        "name": "Healthcare System",
        "domain": "healthcare",
        "description": "Complex relational healthcare database — patients, encounters, diagnoses, procedures (~1M rows)",
        "tables": [
            {"name": "patients", "columns": [
                {"name": "patient_id", "type": "TEXT", "pk": True},
                {"name": "name", "type": "TEXT"},
                {"name": "age", "type": "BIGINT"},
                {"name": "gender", "type": "TEXT"},
                {"name": "region", "type": "TEXT"}]},
            {"name": "encounters", "columns": [
                {"name": "encounter_id", "type": "TEXT", "pk": True},
                {"name": "patient_id", "type": "TEXT", "fk": "patients.patient_id"},
                {"name": "admission_date", "type": "DATE"},
                {"name": "discharge_date", "type": "DATE"},
                {"name": "department", "type": "TEXT"},
                {"name": "payer", "type": "TEXT"},
                {"name": "length_of_stay_days", "type": "BIGINT"}]},
            {"name": "diagnoses", "columns": [
                {"name": "diagnosis_id", "type": "TEXT", "pk": True},
                {"name": "encounter_id", "type": "TEXT", "fk": "encounters.encounter_id"},
                {"name": "icd_code", "type": "TEXT"},
                {"name": "diagnosis_name", "type": "TEXT"},
                {"name": "severity", "type": "TEXT"}]},
            {"name": "procedures", "columns": [
                {"name": "procedure_id", "type": "TEXT", "pk": True},
                {"name": "encounter_id", "type": "TEXT", "fk": "encounters.encounter_id"},
                {"name": "procedure_name", "type": "TEXT"},
                {"name": "cost", "type": "DOUBLE PRECISION"}]},
        ],
    })
    _write_json(ds, "questions", {
        "easy": [
            "How many encounters are there per department?",
            "What is the average length of stay by payer?",
            "What is the total procedure cost by department?"
        ],
        "medium": [
            "What is the readmission rate by department?",
            "What is the average cost per encounter by diagnosis severity?",
            "Which departments have the highest procedure costs per patient?"
        ],
        "hard": [
            "Show monthly admissions with a 3-month rolling average by department",
            "What is the average length of stay by age group, and how does it vary by gender?",
            "Which patients have the highest total healthcare cost, and what is their diagnosis profile?"
        ],
        "very_complex": [
            "Compare Q4 vs Q3 admissions by department, identify the departments with the largest growth, and explain the payer mix behind the change",
            "Build a report on readmissions: what percentage of patients are readmitted within 30 days, broken down by department and severity, and which department has the worst readmission profile?",
            "Analyze cost drivers: how do procedure costs vary by department and severity, and which combination drives the highest total cost per encounter?"
        ],
    })


# ── Finance ───────────────────────────────────────────────────────────────
def finance() -> None:
    ds = "finance"
    n_customers = 50_000
    n_accounts = 80_000
    n_transactions = 800_000
    n_loans = 30_000

    customers = []
    for i in range(1, n_customers + 1):
        customers.append([
            f"C{i:06d}", f"Customer {i}", random.choice(["Retail", "Premium", "Business", "Student"]),
            random.choice(["North", "South", "East", "West"]), _date(date(2019, 1, 1), 1500),
        ])
    _write(ds, "customers", ["customer_id", "name", "segment", "region", "signup_date"], customers)

    accounts = []
    for i in range(1, n_accounts + 1):
        accounts.append([
            f"A{i:07d}", random.choice(customers)[0],
            random.choice(["Checking", "Savings", "Credit", "Investment"]),
            round(random.uniform(0, 100000), 2), _date(date(2019, 1, 1), 1500),
        ])
    _write(ds, "accounts", ["account_id", "customer_id", "account_type", "balance", "opened_date"], accounts)

    categories = ["Retail", "Groceries", "Utilities", "Travel", "Dining", "Transfer", "Salary", "Investment"]
    transactions = []
    for i in range(1, n_transactions + 1):
        transactions.append([
            f"T{i:08d}", random.choice(accounts)[0], _date(date(2023, 1, 1), 700),
            round(random.uniform(-5000, 5000), 2), random.choice(categories),
            random.choice(["completed", "completed", "completed", "pending", "failed"]),
        ])
    _write(ds, "transactions", ["transaction_id", "account_id", "transaction_date", "amount", "category", "status"], transactions)

    loans = []
    for i in range(1, n_loans + 1):
        loans.append([
            f"L{i:06d}", random.choice(customers)[0], _date(date(2020, 1, 1), 1200),
            round(random.uniform(1000, 500000), 2), round(random.uniform(3, 15), 2),
            random.choice([12, 24, 36, 48, 60]),
            random.choice(["active", "active", "active", "paid", "defaulted"]),
        ])
    _write(ds, "loans", ["loan_id", "customer_id", "loan_date", "amount", "interest_rate", "term_months", "status"], loans)

    _write_json(ds, "schema", {
        "name": "Finance & Banking",
        "domain": "finance",
        "description": "Complex relational finance database — customers, accounts, transactions, loans (~960K rows)",
        "tables": [
            {"name": "customers", "columns": [
                {"name": "customer_id", "type": "TEXT", "pk": True},
                {"name": "name", "type": "TEXT"},
                {"name": "segment", "type": "TEXT"},
                {"name": "region", "type": "TEXT"},
                {"name": "signup_date", "type": "DATE"}]},
            {"name": "accounts", "columns": [
                {"name": "account_id", "type": "TEXT", "pk": True},
                {"name": "customer_id", "type": "TEXT", "fk": "customers.customer_id"},
                {"name": "account_type", "type": "TEXT"},
                {"name": "balance", "type": "DOUBLE PRECISION"},
                {"name": "opened_date", "type": "DATE"}]},
            {"name": "transactions", "columns": [
                {"name": "transaction_id", "type": "TEXT", "pk": True},
                {"name": "account_id", "type": "TEXT", "fk": "accounts.account_id"},
                {"name": "transaction_date", "type": "DATE"},
                {"name": "amount", "type": "DOUBLE PRECISION"},
                {"name": "category", "type": "TEXT"},
                {"name": "status", "type": "TEXT"}]},
            {"name": "loans", "columns": [
                {"name": "loan_id", "type": "TEXT", "pk": True},
                {"name": "customer_id", "type": "TEXT", "fk": "customers.customer_id"},
                {"name": "loan_date", "type": "DATE"},
                {"name": "amount", "type": "DOUBLE PRECISION"},
                {"name": "interest_rate", "type": "DOUBLE PRECISION"},
                {"name": "term_months", "type": "BIGINT"},
                {"name": "status", "type": "TEXT"}]},
        ],
    })
    _write_json(ds, "questions", {
        "easy": [
            "What is the total transaction volume by category?",
            "What is the average account balance by account type?",
            "How many loans are there per status?"
        ],
        "medium": [
            "What is the average transaction amount by category and status?",
            "What is the total loan amount by customer segment?",
            "Which account types have the highest transaction activity?"
        ],
        "hard": [
            "Show monthly net cash flow with a 3-month rolling average by category",
            "What is the loan default rate by segment, and how does it correlate with interest rate?",
            "Which customers have the highest total transaction volume, and what is their account profile?"
        ],
        "very_complex": [
            "Compare Q4 vs Q3 revenue by region, identify the top 3 growth categories, and explain the driver behind the growth",
            "Build a report on loan risk: what is the default rate by segment and term, and which combination poses the highest risk to the bank?",
            "Analyze customer profitability: which segments generate the most net revenue (deposits minus withdrawals), and how does it vary by region?"
        ],
    })


# ── Demographics: Census ──────────────────────────────────────────────────
def demographics_census() -> None:
    ds = "demographics_census"
    n_regions = 50
    n_households = 100_000
    n_individuals = 300_000

    regions = []
    for i in range(1, n_regions + 1):
        regions.append([f"R{i:03d}", f"Region {i}", random.choice(["CA", "NY", "TX", "FL", "IL", "WA", "GA", "CO"])])
    _write(ds, "regions", ["region_id", "name", "state"], regions)

    households = []
    for i in range(1, n_households + 1):
        households.append([
            f"H{i:07d}", random.choice(regions)[0],
            random.randint(1, 8), random.choice(["Own", "Rent"]),
            random.choice(["Urban", "Suburban", "Rural"]),
        ])
    _write(ds, "households", ["household_id", "region_id", "size", "home_type", "area_type"], households)

    educations = ["Less than HS", "HS Diploma", "Some College", "Bachelors", "Masters", "Doctorate"]
    employments = ["Employed", "Self-Employed", "Unemployed", "Retired", "Student"]
    individuals = []
    for i in range(1, n_individuals + 1):
        individuals.append([
            f"I{i:08d}", random.choice(households)[0], random.randint(0, 100),
            random.choice(["M", "F"]), random.choice(educations), random.choice(employments),
            random.randint(0, 500000),
        ])
    _write(ds, "individuals", ["individual_id", "household_id", "age", "gender", "education", "employment", "income"], individuals)

    _write_json(ds, "schema", {
        "name": "Census Demographics",
        "domain": "general",
        "description": "Census-style demographics — regions, households, individuals with income/education (~400K rows)",
        "tables": [
            {"name": "regions", "columns": [
                {"name": "region_id", "type": "TEXT", "pk": True},
                {"name": "name", "type": "TEXT"},
                {"name": "state", "type": "TEXT"}]},
            {"name": "households", "columns": [
                {"name": "household_id", "type": "TEXT", "pk": True},
                {"name": "region_id", "type": "TEXT", "fk": "regions.region_id"},
                {"name": "size", "type": "BIGINT"},
                {"name": "home_type", "type": "TEXT"},
                {"name": "area_type", "type": "TEXT"}]},
            {"name": "individuals", "columns": [
                {"name": "individual_id", "type": "TEXT", "pk": True},
                {"name": "household_id", "type": "TEXT", "fk": "households.household_id"},
                {"name": "age", "type": "BIGINT"},
                {"name": "gender", "type": "TEXT"},
                {"name": "education", "type": "TEXT"},
                {"name": "employment", "type": "TEXT"},
                {"name": "income", "type": "BIGINT"}]},
        ],
    })
    _write_json(ds, "questions", {
        "easy": [
            "What is the average income by state?",
            "How many individuals are there per education level?",
            "What is the average household size by area type?"
        ],
        "medium": [
            "What is the average income by education and gender?",
            "What is the employment rate by state?",
            "Which regions have the highest average household income?"
        ],
        "hard": [
            "Show the income distribution by age group and education level",
            "What is the income gap between urban and rural households, by state?",
            "Which education levels have the highest employment rates, and how does it vary by region?"
        ],
        "very_complex": [
            "Compare income by education across states, identify the states with the largest education premium, and explain the demographic drivers",
            "Build a report on the workforce: what is the employment profile (education, age, region) of the top-earning 10% of individuals, and how does it differ from the bottom 10%?",
            "Analyze household economics: how do household size, home type, and area type combine to predict income, and which regions show the strongest relationship?"
        ],
    })


# ── Demographics: Consumer ────────────────────────────────────────────────
def demographics_consumer() -> None:
    ds = "demographics_consumer"
    n_consumers = 100_000
    n_purchases = 500_000
    n_preferences = 200_000

    consumers = []
    for i in range(1, n_consumers + 1):
        consumers.append([
            f"CON{i:07d}", random.randint(18, 90), random.choice(["M", "F"]),
            random.choice(["<25K", "25-50K", "50-75K", "75-100K", "100K+"]),
            random.choice(["HS", "College", "Bachelors", "Graduate"]),
            random.choice(["North", "South", "East", "West"]),
        ])
    _write(ds, "consumers", ["consumer_id", "age", "gender", "income_bracket", "education", "region"], consumers)

    categories = ["Electronics", "Fashion", "Home", "Groceries", "Travel", "Entertainment", "Health", "Automotive"]
    purchases = []
    for i in range(1, n_purchases + 1):
        purchases.append([
            f"P{i:08d}", random.choice(consumers)[0], _date(date(2023, 1, 1), 700),
            random.choice(categories), round(random.uniform(5, 2000), 2),
        ])
    _write(ds, "purchases", ["purchase_id", "consumer_id", "purchase_date", "category", "amount"], purchases)

    preferences = []
    for i in range(1, n_preferences + 1):
        preferences.append([
            f"PF{i:08d}", random.choice(consumers)[0], random.choice(categories),
            random.randint(1, 10),
        ])
    _write(ds, "preferences", ["preference_id", "consumer_id", "category", "preference_score"], preferences)

    _write_json(ds, "schema", {
        "name": "Consumer Demographics",
        "domain": "general",
        "description": "Consumer demographics — consumers, purchases, preferences (~800K rows)",
        "tables": [
            {"name": "consumers", "columns": [
                {"name": "consumer_id", "type": "TEXT", "pk": True},
                {"name": "age", "type": "BIGINT"},
                {"name": "gender", "type": "TEXT"},
                {"name": "income_bracket", "type": "TEXT"},
                {"name": "education", "type": "TEXT"},
                {"name": "region", "type": "TEXT"}]},
            {"name": "purchases", "columns": [
                {"name": "purchase_id", "type": "TEXT", "pk": True},
                {"name": "consumer_id", "type": "TEXT", "fk": "consumers.consumer_id"},
                {"name": "purchase_date", "type": "DATE"},
                {"name": "category", "type": "TEXT"},
                {"name": "amount", "type": "DOUBLE PRECISION"}]},
            {"name": "preferences", "columns": [
                {"name": "preference_id", "type": "TEXT", "pk": True},
                {"name": "consumer_id", "type": "TEXT", "fk": "consumers.consumer_id"},
                {"name": "category", "type": "TEXT"},
                {"name": "preference_score", "type": "BIGINT"}]},
        ],
    })
    _write_json(ds, "questions", {
        "easy": [
            "What is the total purchase amount by category?",
            "What is the average purchase amount by income bracket?",
            "How many consumers are there per region?"
        ],
        "medium": [
            "What is the average purchase amount by category and income bracket?",
            "What is the average preference score by category?",
            "Which age groups spend the most per purchase?"
        ],
        "hard": [
            "Show monthly purchase volume with a 3-month rolling average by category",
            "What is the correlation between preference score and purchase amount by category?",
            "Which consumer segments (age + income) have the highest total spend?"
        ],
        "very_complex": [
            "Compare Q4 vs Q3 spending by category, identify the top 3 growth categories, and explain the demographic driver behind the growth",
            "Build a report on consumer segments: which age-income-education segments spend the most per category, and how do preferences predict spending?",
            "Analyze regional differences: how do purchase patterns and preferences vary by region, and which region shows the strongest preference-to-spend relationship?"
        ],
    })


if __name__ == "__main__":
    healthcare()
    finance()
    demographics_census()
    demographics_consumer()
    print("done")