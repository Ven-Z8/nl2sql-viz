from app.core.demo import build_demo_session, get_demo_questions


def test_build_demo_session_uses_configured_postgres_dsn() -> None:
    session = build_demo_session(
        dsn="postgresql://analyst:secret@localhost:5432/warehouse",
        username="demo_analyst",
    )

    assert session["username"] == "demo_analyst"
    assert session["dsn"] == "postgresql://analyst:secret@localhost:5432/warehouse"
    assert len(session["api_key"]) == 32


def test_demo_questions_are_suggestions_not_sql_shortcuts() -> None:
    questions = get_demo_questions()

    assert len(questions) >= 5
    assert all(question["question"] for question in questions)
    assert all("sql" not in question for question in questions)
