"""SQLAgent — generates safe, optimized SQL from natural language questions.

NOOA Agent using PredictStrategy for single-shot SQL generation and planning.
Deterministic helpers expose EXPLAIN-based costing, read-only validation,
execution, and exact math for derived metrics.
"""

from __future__ import annotations

from nooa import Agent, strategy
from nooa.strategies import PredictStrategy

from app.core.math_tool import MathCalculator
from app.db.cost import estimate_cost
from app.db.guard import validate_read_only
from app.db.pool import PostgresPool
from app.llm import SONNET
from app.models import (
    GeneratedSQL,
    QueryCost,
    QueryResult,
    SchemaMap,
    SubQuery,
)


class SQLAgent(Agent, llm=SONNET):
    """You are a senior PostgreSQL analytics engineer for a BI copilot.
    You generate safe, correct, optimized SQL from natural language questions.

    You have access to:
    - self.pool: PostgresPool for executing SQL and running EXPLAIN
    - self.estimate_cost(sql): deterministic helper that runs EXPLAIN and returns QueryCost
    - self.validate_sql(sql): deterministic helper that checks SQL safety
    - self.execute_query(sql): deterministic helper that executes SQL and returns QueryResult
    - self.calculate(expr, variables): deterministic calculator for derived metrics —
      NEVER compute percentages, growth, or ratios in your head; always use this tool
      on the numbers returned by execute_query()

    Use these helpers in your Python code to test and validate your SQL before returning it.
    """

    pool: PostgresPool
    math: MathCalculator = MathCalculator()
    domain_guidance: str = ""
    # Conversation context block for follow-up questions (Contract V3).
    # Empty on the stateless path — prompts stay byte-identical to before.
    conversation_context: str = ""

    # ------------------------------------------------------------------
    # Deterministic helpers
    # ------------------------------------------------------------------

    async def estimate_cost(self, sql: str) -> QueryCost:
        """Run EXPLAIN and return estimated cost. Use this to check if your query is safe."""
        return await estimate_cost(self.pool, sql)

    def validate_sql(self, sql: str) -> str:
        """Validate that SQL is read-only. Returns 'OK' or error message."""
        try:
            validate_read_only(sql)
            return "OK"
        except ValueError as e:
            return str(e)

    async def execute_query(self, sql: str) -> QueryResult:
        """Execute a validated SQL query and return results."""
        validate_read_only(sql)
        return await self.pool.execute(sql)

    def calculate(self, expression: str, variables: dict[str, float] | None = None) -> float:
        """Compute a derived metric deterministically from query results.

        Example: self.calculate("(revenue - cost) / cost * 100",
                                {"revenue": rev, "cost": cost})
        """
        return self.math.calculate(expression, variables)

    # ------------------------------------------------------------------
    # Generation methods
    # ------------------------------------------------------------------

    @strategy(PredictStrategy())
    async def generate_simple(self, question: str, schema: SchemaMap, sample_text: str = "", feedback: str = "") -> GeneratedSQL:
        """Generate a safe, correct PostgreSQL query that answers the question.

        Return a GeneratedSQL with the final SQL and a brief explanation.

        The schema is: {schema.compact_repr()}

        Sample data (real rows — use these to understand the column names, grain,
        and value formats. Pick columns that actually exist in the sample):
        {sample_text}

        Domain guidance (follow these analyst conventions):
        {self.domain_guidance}

        {self.conversation_context}

        Previous attempt feedback (fix these errors — use ONLY the listed columns):
        {feedback}
        """
        ...

    @strategy(PredictStrategy())
    async def plan_analysis(self, question: str, schema: SchemaMap, sample_text: str = "") -> list[SubQuery]:
        """Break a COMPLEX question into 3-5 verifiable sub-questions.

        Each sub-question must be answerable by a single SELECT with basic
        aggregation. The sub-questions are designed so their results can be
        compared or joined to build the final report. Keep each sub-question
        short and specific.

        The schema is: {schema.compact_repr()}

        Sample data (real rows — use these to understand the column names, grain,
        and value formats. Pick columns that actually exist in the sample):
        {sample_text}

        Domain guidance (follow these analyst conventions):
        {self.domain_guidance}

        {self.conversation_context}
        """
        ...
