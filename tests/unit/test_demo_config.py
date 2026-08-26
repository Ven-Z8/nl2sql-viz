from app.core.demo import build_demo_session, get_demo_questions


def test_build_demo_session_has_no_dsn() -> None:
    """Demo sessions expose credentials + an opaque connection_id — never a DSN."""
    session = build_demo_session(username="demo_analyst")

    assert session["username"] == "demo_analyst"
    assert len(session["api_key"]) == 32
    assert session["dataset"] == "RavenStack SaaS Analytics"
    assert "dsn" not in session


def test_demo_questions_are_suggestions_not_sql_shortcuts() -> None:
    questions = get_demo_questions()

    assert len(questions) >= 5
    assert all(question["question"] for question in questions)
    assert all("sql" not in question for question in questions)
