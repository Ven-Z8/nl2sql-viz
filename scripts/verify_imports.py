"""Verify all new NOOA modules import correctly."""
import sys

def check(label, fn):
    try:
        fn()
        print(f"  ✅ {label}", flush=True)
    except Exception as e:
        print(f"  ❌ {label}: {e}", flush=True)
        sys.exit(1)

print("Verifying NL2SQL Viz NOOA modules...", flush=True)

check("models", lambda: (
    __import__("app.models", fromlist=["SchemaMap", "QueryResult", "GeneratedSQL", "ChartSpec"]),
))

check("guard", lambda: (
    __import__("app.db.guard", fromlist=["validate_read_only"]).validate_read_only("SELECT 1"),
))

check("cache", lambda: (
    __import__("app.engine.cache", fromlist=["QueryCache"]).QueryCache(),
))

check("results", lambda: (
    __import__("app.engine.results", fromlist=["classify_size"]),
))

check("llm", lambda: (
    __import__("app.llm", fromlist=["SONNET", "HAIKU"]),
))

check("SchemaAgent", lambda: (
    __import__("app.agents.schema_agent", fromlist=["SchemaAgent"]),
))

check("SQLAgent", lambda: (
    __import__("app.agents.sql_agent", fromlist=["SQLAgent"]),
))

check("VizAgent", lambda: (
    __import__("app.agents.viz_agent", fromlist=["VizAgent"]),
))

check("CoordinatorAgent", lambda: (
    __import__("app.agents.coordinator", fromlist=["CoordinatorAgent"]),
))

print("\n✅ All NOOA modules verified!", flush=True)
