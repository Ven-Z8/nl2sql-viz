.PHONY: run test test-unit test-integration lint benchmark load-demo-data frontend-typecheck frontend-build

# Benchmark dataset subset — override: make benchmark SUBSET=olist,tpcds
SUBSET ?= olist,tpcds

run:
	uv run uvicorn app.main:app --port 8000

test:
	uv run pytest tests -q

test-unit:
	uv run pytest tests/unit -q

test-integration:
	uv run pytest tests/integration/test_postgres_connector.py tests/integration/test_schema_agent.py tests/integration/test_ravenstack_dataset.py -q

lint:
	uv run ruff check app

# Very-complex benchmark against a live backend on :8000.
# Prereqs: `make run` + Postgres (docker compose up -d) + OPENROUTER_API_KEY
# in .env. --load POSTs each dataset's /load endpoint first (needed when the
# target DB is empty). Results stream incrementally into bench_results.json.
benchmark:
	uv run python -m scripts.benchmark_very_complex --datasets $(SUBSET) --json bench_results.json --load

load-demo-data:
	uv run python -m scripts.load_ravenstack

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-build:
	cd frontend && npm run build
