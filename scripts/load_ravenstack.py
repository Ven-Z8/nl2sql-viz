import argparse
import asyncio
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import asyncpg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "ravenstack"
DEFAULT_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


@dataclass(frozen=True)
class TableSpec:
    name: str
    csv_name: str
    columns: tuple[str, ...]
    create_sql: str
    date_columns: tuple[str, ...] = ()
    timestamp_columns: tuple[str, ...] = ()


TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        name="accounts",
        csv_name="ravenstack_accounts.csv",
        columns=(
            "account_id",
            "account_name",
            "industry",
            "country",
            "signup_date",
            "referral_source",
            "plan_tier",
            "seats",
            "is_trial",
            "churn_flag",
        ),
        create_sql="""
            CREATE TABLE accounts (
                account_id TEXT PRIMARY KEY,
                account_name TEXT NOT NULL,
                industry TEXT NOT NULL,
                country TEXT NOT NULL,
                signup_date DATE NOT NULL,
                referral_source TEXT NOT NULL,
                plan_tier TEXT NOT NULL,
                seats INTEGER NOT NULL,
                is_trial BOOLEAN NOT NULL,
                churn_flag BOOLEAN NOT NULL
            )
        """,
        date_columns=("signup_date",),
    ),
    TableSpec(
        name="subscriptions",
        csv_name="ravenstack_subscriptions.csv",
        columns=(
            "subscription_id",
            "account_id",
            "start_date",
            "end_date",
            "plan_tier",
            "seats",
            "mrr_amount",
            "arr_amount",
            "is_trial",
            "upgrade_flag",
            "downgrade_flag",
            "churn_flag",
            "billing_frequency",
            "auto_renew_flag",
        ),
        create_sql="""
            CREATE TABLE subscriptions (
                subscription_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                start_date DATE NOT NULL,
                end_date DATE,
                plan_tier TEXT NOT NULL,
                seats INTEGER NOT NULL,
                mrr_amount NUMERIC(12, 2) NOT NULL,
                arr_amount NUMERIC(12, 2) NOT NULL,
                is_trial BOOLEAN NOT NULL,
                upgrade_flag BOOLEAN NOT NULL,
                downgrade_flag BOOLEAN NOT NULL,
                churn_flag BOOLEAN NOT NULL,
                billing_frequency TEXT NOT NULL,
                auto_renew_flag BOOLEAN NOT NULL
            )
        """,
        date_columns=("start_date", "end_date"),
    ),
    TableSpec(
        name="feature_usage",
        csv_name="ravenstack_feature_usage.csv",
        columns=(
            "usage_id",
            "subscription_id",
            "usage_date",
            "feature_name",
            "usage_count",
            "usage_duration_secs",
            "error_count",
            "is_beta_feature",
        ),
        create_sql="""
            CREATE TABLE feature_usage (
                usage_event_id BIGSERIAL PRIMARY KEY,
                usage_id TEXT NOT NULL,
                subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
                usage_date DATE NOT NULL,
                feature_name TEXT NOT NULL,
                usage_count INTEGER NOT NULL,
                usage_duration_secs INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                is_beta_feature BOOLEAN NOT NULL
            )
        """,
        date_columns=("usage_date",),
    ),
    TableSpec(
        name="support_tickets",
        csv_name="ravenstack_support_tickets.csv",
        columns=(
            "ticket_id",
            "account_id",
            "submitted_at",
            "closed_at",
            "resolution_time_hours",
            "priority",
            "first_response_time_minutes",
            "satisfaction_score",
            "escalation_flag",
        ),
        create_sql="""
            CREATE TABLE support_tickets (
                ticket_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                submitted_at TIMESTAMP NOT NULL,
                closed_at TIMESTAMP,
                resolution_time_hours NUMERIC(10, 2),
                priority TEXT NOT NULL,
                first_response_time_minutes INTEGER NOT NULL,
                satisfaction_score INTEGER,
                escalation_flag BOOLEAN NOT NULL
            )
        """,
        timestamp_columns=("submitted_at", "closed_at"),
    ),
    TableSpec(
        name="churn_events",
        csv_name="ravenstack_churn_events.csv",
        columns=(
            "churn_event_id",
            "account_id",
            "churn_date",
            "reason_code",
            "refund_amount_usd",
            "preceding_upgrade_flag",
            "preceding_downgrade_flag",
            "is_reactivation",
            "feedback_text",
        ),
        create_sql="""
            CREATE TABLE churn_events (
                churn_event_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                churn_date DATE NOT NULL,
                reason_code TEXT NOT NULL,
                refund_amount_usd NUMERIC(10, 2) NOT NULL,
                preceding_upgrade_flag BOOLEAN NOT NULL,
                preceding_downgrade_flag BOOLEAN NOT NULL,
                is_reactivation BOOLEAN NOT NULL,
                feedback_text TEXT
            )
        """,
        date_columns=("churn_date",),
    ),
)


def cast_csv_value(value: str) -> Any:
    if value == "":
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return [
            {key: cast_csv_value(value) for key, value in row.items()}
            for row in csv.DictReader(csv_file)
        ]


def _parse_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raw = str(value)
    if len(raw) == 10:
        return datetime.fromisoformat(f"{raw} 00:00:00")
    return datetime.fromisoformat(raw)


def cast_row_for_table(table: TableSpec, row: dict[str, Any]) -> dict[str, Any]:
    casted = dict(row)
    for column in table.date_columns:
        casted[column] = _parse_date(casted[column])
    for column in table.timestamp_columns:
        casted[column] = _parse_timestamp(casted[column])
    return casted


async def load_ravenstack(dsn: str, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            for table in reversed(TABLES):
                await conn.execute(f"DROP TABLE IF EXISTS {table.name} CASCADE")

            for table in TABLES:
                await conn.execute(table.create_sql)
                rows = [
                    cast_row_for_table(table, row)
                    for row in read_csv_rows(data_dir / table.csv_name)
                ]
                values = [[row[column] for column in table.columns] for row in rows]
                placeholders = ", ".join(f"${index}" for index in range(1, len(table.columns) + 1))
                columns = ", ".join(table.columns)
                await conn.executemany(
                    f"INSERT INTO {table.name} ({columns}) VALUES ({placeholders})",
                    values,
                )

            await conn.execute(
                "CREATE INDEX idx_subscriptions_account_id ON subscriptions(account_id)"
            )
            await conn.execute(
                "CREATE INDEX idx_feature_usage_subscription_id ON feature_usage(subscription_id)"
            )
            await conn.execute(
                "CREATE INDEX idx_feature_usage_usage_date ON feature_usage(usage_date)"
            )
            await conn.execute(
                "CREATE INDEX idx_support_tickets_account_id ON support_tickets(account_id)"
            )
            await conn.execute(
                "CREATE INDEX idx_churn_events_account_id ON churn_events(account_id)"
            )
    finally:
        await conn.close()


async def _print_counts(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        for table in TABLES:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table.name}")
            print(f"{table.name}: {count}")
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load the RavenStack SaaS analytics CSVs into Postgres."
    )
    parser.add_argument(
        "--dsn",
        default=os.getenv("DATABASE_URL", DEFAULT_DSN),
        help="Postgres DSN. Defaults to DATABASE_URL or local docker-compose DSN.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the ravenstack_*.csv files.",
    )
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    args = parse_args()
    await load_ravenstack(dsn=args.dsn, data_dir=args.data_dir)
    await _print_counts(args.dsn)


if __name__ == "__main__":
    asyncio.run(main())
