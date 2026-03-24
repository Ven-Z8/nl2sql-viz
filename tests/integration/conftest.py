import pytest
import asyncpg
import pytest_asyncio

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


@pytest_asyncio.fixture
async def seed_test_db():
    conn = await asyncpg.connect("postgresql://testuser:testpass@localhost:5432/testdb")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            region TEXT NOT NULL,
            amount NUMERIC(10,2) NOT NULL,
            sale_date DATE NOT NULL
        )
    """)
    await conn.execute("DELETE FROM sales")
    await conn.execute("""
        INSERT INTO sales (region, amount, sale_date) VALUES
        ('North', 1000.00, '2024-01-15'),
        ('South', 2000.00, '2024-01-20'),
        ('North', 1500.00, '2024-02-10'),
        ('East',  800.00,  '2024-02-15')
    """)
    await conn.close()
    yield
    # Teardown
    conn = await asyncpg.connect("postgresql://testuser:testpass@localhost:5432/testdb")
    await conn.execute("DROP TABLE IF EXISTS sales")
    await conn.close()
