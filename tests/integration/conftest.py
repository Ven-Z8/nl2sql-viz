import pytest
import asyncpg

TEST_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


@pytest.fixture
def postgres_dsn():
    return TEST_DSN


@pytest.fixture(autouse=True, scope="session")
def event_loop_policy():
    """Use default event loop policy — required by pytest-asyncio in auto mode."""
    return None


@pytest.fixture(autouse=True, scope="session")
async def seed_test_schema():
    """Create a minimal test table so schema introspection returns non-empty results."""
    conn = await asyncpg.connect(TEST_DSN)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS test_users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT
        )
    """)
    await conn.close()
    yield
    conn = await asyncpg.connect(TEST_DSN)
    await conn.execute("DROP TABLE IF EXISTS test_users")
    await conn.close()
