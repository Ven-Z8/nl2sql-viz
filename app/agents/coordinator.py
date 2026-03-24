from typing import AsyncIterator, Any

from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.connectors.base import BaseConnector
from app.core.session import SessionStore


class Coordinator:
    """
    Orchestrates the nl2sql-viz pipeline: Schema → SQL → Viz.
    Streams progress events as an async generator.
    """

    def __init__(
        self,
        connector: BaseConnector,
        session_store: SessionStore,
        session_id: str,
    ):
        self._connector = connector
        self._session_store = session_store
        self._session_id = session_id

    async def run(self, nl_query: str) -> AsyncIterator[dict[str, Any]]:
        """
        Orchestrates the full nl2sql-viz pipeline.

        Yields progress events and final result as dicts. Event shapes:
          {"type": "progress", "message": "..."}
          {"type": "sql", "sql": "..."}
          {"type": "result", "vega_spec": "...", "rows": [...], "sql": "..."}
          {"type": "error", "message": "...", "details": "..."}

        Args:
            nl_query: Natural language query from the user.

        Yields:
            Dictionary events with type, message, and result data.
        """
        try:
            yield {"type": "progress", "message": "Analyzing your database schema..."}
            schema_agent = SchemaAgent(
                connector=self._connector,
                session_store=self._session_store,
                session_id=self._session_id,
            )
            schema_map = await schema_agent.get_schema_map()

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
            yield {"type": "progress", "message": "Generating visualization..."}

            viz_agent = VizAgent()
            vega_spec = await viz_agent.run(
                nl_query=nl_query,
                rows=sql_result["rows"],
            )

            yield {
                "type": "result",
                "vega_spec": vega_spec,
                "rows": sql_result["rows"],
                "sql": sql_result["sql"],
            }

        except Exception as e:
            yield {"type": "error", "message": str(e)}
