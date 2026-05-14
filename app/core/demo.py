import os
import uuid
from typing import Any

from app.core.auth import generate_api_key

DEFAULT_DEMO_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"
DEMO_DATASET_NAME = "RavenStack SaaS Analytics"

_DEMO_QUESTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "mrr-by-plan",
        "question": "Show monthly recurring revenue by plan tier over time.",
        "category": "Revenue",
    },
    {
        "id": "churn-support",
        "question": "Which industries have the most churn events and longest support resolution time?",
        "category": "Retention",
    },
    {
        "id": "feature-errors",
        "question": "Which features have the highest usage but also the highest error counts?",
        "category": "Product",
    },
    {
        "id": "support-priority",
        "question": "Show support ticket volume and average satisfaction score by priority.",
        "category": "Support",
    },
    {
        "id": "referral-arr",
        "question": "Which referral sources produce the highest average ARR?",
        "category": "Growth",
    },
    {
        "id": "high-risk-accounts",
        "question": "Find accounts with high seat counts, high support load, and churn events.",
        "category": "Risk",
    },
)


def get_demo_dsn() -> str:
    """Return the configured sample Postgres DSN.

    The bundled RavenStack dataset is only the default sample. Operators can point
    demo mode at any Postgres database by setting DEMO_DATABASE_URL or DATABASE_URL.
    """
    return os.getenv("DEMO_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DEMO_DSN


def get_demo_questions() -> list[dict[str, str]]:
    """Return natural-language sample questions without SQL shortcuts."""
    return [dict(question) for question in _DEMO_QUESTIONS]


def build_demo_session(dsn: str | None = None, username: str | None = None) -> dict[str, Any]:
    """Create demo credentials for a browser session."""
    return {
        "username": username or f"demo_{uuid.uuid4().hex[:8]}",
        "api_key": generate_api_key(),
        "dsn": dsn or get_demo_dsn(),
        "dataset": DEMO_DATASET_NAME,
    }
