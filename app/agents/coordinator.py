from typing import AsyncIterator, Any

from anthropic import AsyncAnthropic

from app.agents.code_exec_agent import CodeExecAgent
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.connectors.base import BaseConnector
from app.core.session import SessionStore

_ROUTE_SYSTEM = """\
Decide if a user's data question requires JavaScript post-processing after SQL execution.

Reply with ONLY one of these two words — nothing else:
  sql_only
  needs_transform

Choose needs_transform ONLY when the query requires:
- Multi-step rolling averages or cumulative sums across partitions
- Pivot / unpivot / matrix reshaping
- Percentile ranking across multiple independent dimensions
- Complex regex or string transformation on result sets
- Custom data shaping that standard PostgreSQL window/aggregate functions cannot produce

Choose sql_only for everything else: aggregations, GROUP BY, JOINs, window functions, filters."""


class Coordinator:
    """Orchestrates the nl2sql-viz pipeline with optional code execution routing.

    Pipeline:
      Schema Agent → [route decision] → SQL Agent → (optional) Code Exec Agent → Viz Agent

    Streams progress events as an async generator.
    """

    def __init__(
        self,
        connector: BaseConnector,
        session_store: SessionStore,
        session_id: str,
    ) -> None:
        self._connector = connector
        self._session_store = session_store
        self._session_id = session_id
        self._client = AsyncAnthropic()

    async def _decide_route(self, nl_query: str, schema_map: str) -> str:
        """Ask Claude Haiku whether the query needs post-SQL transformation.

        Returns "sql_only" or "needs_transform".
        Defaults to "sql_only" on any unexpected response.
        """
        response = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            system=_ROUTE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Schema:\n{schema_map}\n\nQuery: {nl_query}",
                }
            ],
        )
        decision = response.content[0].text.strip().lower()
        return "needs_transform" if "needs_transform" in decision else "sql_only"

    async def run(self, nl_query: str) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate the full pipeline, yielding WebSocket events."""
        try:
            yield {"type": "progress", "message": "Analyzing your database schema..."}
            schema_agent = SchemaAgent(
                connector=self._connector,
                session_store=self._session_store,
                session_id=self._session_id,
            )
            schema_map = await schema_agent.get_schema_map()

            yield {"type": "progress", "message": "Planning query approach..."}
            route = await self._decide_route(nl_query, schema_map)

            yield {"type": "progress", "message": "Writing and running SQL query..."}
            sql_agent = SQLAgent(connector=self._connector)
            sql_result = await sql_agent.run(nl_query=nl_query, schema_map=schema_map)

            if sql_result["status"] == "error":
                yield {
                    "type": "error",
                    "message": sql_result["message"],
                    "details": sql_result.get("last_error"),
                }
                return

            yield {"type": "sql", "sql": sql_result["sql"]}

            rows = sql_result["rows"]

            if route == "needs_transform":
                yield {"type": "progress", "message": "Transforming results..."}
                code_agent = CodeExecAgent()
                exec_result = await code_agent.run(
                    nl_query=nl_query,
                    rows=rows,
                    schema_map=schema_map,
                )
                if exec_result["status"] == "success":
                    rows = exec_result["rows"]
                else:
                    yield {
                        "type": "progress",
                        "message": "Transform failed, using raw SQL result...",
                    }

            yield {"type": "progress", "message": "Generating visualization..."}
            viz_agent = VizAgent()
            vega_spec = await viz_agent.run(nl_query=nl_query, rows=rows)

            yield {
                "type": "result",
                "vega_spec": vega_spec,
                "rows": rows,
                "sql": sql_result["sql"],
            }

        except Exception as e:
            yield {"type": "error", "message": str(e)}
