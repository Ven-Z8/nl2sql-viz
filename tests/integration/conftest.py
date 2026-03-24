import pytest

TEST_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


@pytest.fixture
def postgres_dsn():
    return TEST_DSN
