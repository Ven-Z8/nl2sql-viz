import uuid
from typing import Any

from app.core.auth import generate_api_key

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


def get_demo_questions() -> list[dict[str, str]]:
    """Return natural-language sample questions without SQL shortcuts."""
    return [dict(question) for question in _DEMO_QUESTIONS]


DEMO_FOCUS_TABLE = "accounts"


def build_demo_session(username: str | None = None) -> dict[str, Any]:
    """Create demo credentials for a browser session.

    Deliberately contains NO DSN — the demo database is registered in the
    server-side connection registry (app.core.connections); clients receive
    only its opaque ``connection_id``, which the caller attaches.
    """
    return {
        "username": username or f"demo_{uuid.uuid4().hex[:8]}",
        "api_key": generate_api_key(),
        "dataset": DEMO_DATASET_NAME,
        "focus_table": DEMO_FOCUS_TABLE,
    }
