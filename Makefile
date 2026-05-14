.PHONY: run test test-unit test-integration lint load-demo-data frontend-typecheck frontend-build

run:
	uv run uvicorn app.main:app --reload --port 8000

test: test-unit

test-unit:
	uv run pytest tests/unit -q

test-integration:
	uv run pytest tests/integration/test_postgres_connector.py tests/integration/test_schema_agent.py tests/integration/test_ravenstack_dataset.py -q

lint:
	uv run ruff check .

load-demo-data:
	uv run python -m scripts.load_ravenstack

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-build:
	cd frontend && npm run build
