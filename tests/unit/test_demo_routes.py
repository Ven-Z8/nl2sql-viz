from starlette.testclient import TestClient

from app.main import app


def test_demo_questions_endpoint_returns_suggestions() -> None:
    with TestClient(app) as client:
        response = client.get("/api/demo/questions")

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "RavenStack SaaS Analytics"
    assert len(body["questions"]) >= 5
    assert "sql" not in body["questions"][0]


def test_demo_session_registers_temporary_demo_user() -> None:
    with TestClient(app) as client:
        response = client.post("/api/demo/session")

    assert response.status_code == 200
    body = response.json()
    assert body["username"].startswith("demo_")
    assert body["dsn"].startswith("postgresql://")
    assert len(body["api_key"]) == 32
