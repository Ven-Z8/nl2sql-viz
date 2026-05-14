import pytest

from app.connectors.postgres import PostgresConnector
from scripts.load_ravenstack import load_ravenstack


@pytest.fixture
async def ravenstack_db(postgres_dsn: str):
    await load_ravenstack(postgres_dsn)
    yield


@pytest.mark.asyncio
async def test_ravenstack_tables_load_expected_counts(
    postgres_dsn: str, ravenstack_db
) -> None:
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    try:
        rows = await connector.execute_read("""
            SELECT 'accounts' AS table_name, COUNT(*) AS row_count FROM accounts
            UNION ALL
            SELECT 'subscriptions', COUNT(*) FROM subscriptions
            UNION ALL
            SELECT 'feature_usage', COUNT(*) FROM feature_usage
            UNION ALL
            SELECT 'support_tickets', COUNT(*) FROM support_tickets
            UNION ALL
            SELECT 'churn_events', COUNT(*) FROM churn_events
            ORDER BY table_name
        """)
    finally:
        await connector.disconnect()

    counts = {row["table_name"]: row["row_count"] for row in rows}
    assert counts == {
        "accounts": 500,
        "churn_events": 600,
        "feature_usage": 25000,
        "subscriptions": 5000,
        "support_tickets": 2000,
    }


@pytest.mark.asyncio
async def test_ravenstack_support_churn_query_returns_real_segments(
    postgres_dsn: str, ravenstack_db
) -> None:
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    try:
        rows = await connector.execute_read("""
            SELECT
                a.industry,
                COUNT(DISTINCT a.account_id) AS accounts,
                COUNT(DISTINCT ce.churn_event_id) AS churn_events,
                ROUND(AVG(st.resolution_time_hours), 2) AS avg_resolution_hours
            FROM accounts a
            LEFT JOIN churn_events ce ON ce.account_id = a.account_id
            LEFT JOIN support_tickets st ON st.account_id = a.account_id
            GROUP BY a.industry
            HAVING COUNT(DISTINCT a.account_id) >= 10
            ORDER BY churn_events DESC, avg_resolution_hours DESC NULLS LAST
            LIMIT 5
        """)
    finally:
        await connector.disconnect()

    assert len(rows) == 5
    assert all(row["industry"] for row in rows)
    assert all(row["accounts"] >= 10 for row in rows)


@pytest.mark.asyncio
async def test_ravenstack_mrr_trend_query_returns_monthly_series(
    postgres_dsn: str, ravenstack_db
) -> None:
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    try:
        rows = await connector.execute_read("""
            SELECT
                DATE_TRUNC('month', start_date)::date AS month,
                plan_tier,
                SUM(mrr_amount) AS mrr
            FROM subscriptions
            GROUP BY month, plan_tier
            ORDER BY month, plan_tier
            LIMIT 24
        """)
    finally:
        await connector.disconnect()

    assert len(rows) == 24
    assert {"month", "plan_tier", "mrr"} <= set(rows[0])
