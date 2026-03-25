"""Integration test: real BUN + real Postgres + real Claude.

Requirements:
  - BUN installed (brew install bun)
  - Postgres running at postgresql://testuser:testpass@localhost:5432/testdb
  - ANTHROPIC_API_KEY set in .env
"""
import os
import shutil
import pytest
from app.execution.bun_sandbox import BunSandbox
from app.agents.code_exec_agent import CodeExecAgent

bun_installed = shutil.which("bun") is not None
api_key_present = bool(os.getenv("ANTHROPIC_API_KEY"))
skip_no_bun = pytest.mark.skipif(not bun_installed, reason="BUN not installed")
skip_no_key = pytest.mark.skipif(not api_key_present, reason="ANTHROPIC_API_KEY not set")


@skip_no_bun
@pytest.mark.asyncio
async def test_bun_sandbox_real_execution():
    """Runs real BUN to transform a sample dataset."""
    sandbox = BunSandbox()
    rows = [
        {"region": "North", "amount": 600},
        {"region": "South", "amount": 400},
        {"region": "North", "amount": 200},
    ]
    code = """
const totals = {};
for (const r of rows) {
    totals[r.region] = (totals[r.region] || 0) + r.amount;
}
const result = Object.entries(totals).map(([region, total]) => ({region, total}));
"""
    result = await sandbox.run(code=code, input_data=rows)
    assert len(result) == 2
    regions = {r["region"] for r in result}
    assert "North" in regions and "South" in regions
    north = next(r for r in result if r["region"] == "North")
    assert north["total"] == 800


@skip_no_bun
@skip_no_key
@pytest.mark.asyncio
async def test_code_exec_agent_with_real_claude_and_bun(seed_test_db):
    """Claude generates JS code, BUN executes it on real data."""
    from app.connectors.postgres import PostgresConnector

    TEST_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"
    connector = PostgresConnector(dsn=TEST_DSN)
    await connector.connect()

    try:
        rows = await connector.execute_read("SELECT region, amount FROM sales")
    finally:
        await connector.disconnect()

    agent = CodeExecAgent()
    result = await agent.run(
        nl_query="Calculate the percentage each region contributes to total sales",
        rows=rows,
        schema_map="sales(region:text, amount:numeric, sale_date:date)",
    )

    assert result["status"] == "success", f"Expected success, got: {result}"
    assert len(result["rows"]) > 0
    # Each row should have a percentage-like field
    first_row = result["rows"][0]
    assert len(first_row) >= 2  # at least region + percentage field
