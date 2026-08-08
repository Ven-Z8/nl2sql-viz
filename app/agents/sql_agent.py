"""SQLAgent — generates safe, optimized SQL from natural language questions.

NOOA Agent using CodeActStrategy: the model writes Python to iteratively
build, validate, and refine SQL queries. It can call self.estimate_cost()
and self.validate_sql() as deterministic helpers within the CodeAct loop.
"""

from __future__ import annotations


from nooa import Agent, strategy
from nooa.config import CodeActConfig
from nooa.strategies import CodeActStrategy, PredictStrategy

from app.core.math_tool import MathCalculator
from app.db.cost import estimate_cost
from app.db.guard import validate_read_only
from app.db.pool import PostgresPool
from app.llm import SONNET
from app.models import GeneratedSQL, QueryComplexity, QueryCost, QueryResult, SchemaMap

_SQL_SYSTEM_HINT = """\
You are a senior PostgreSQL analytics engineer. Given a natural language business \
question and a database schema, write safe, correct, optimized SQL.

Hard rules:
- Single read-only SELECT or WITH statement only
- Do not use SELECT *
- Use explicit JOIN conditions from schema relationships
- Guard division with NULLIF when needed
- Use DATE_TRUNC for time-series, ORDER BY time
- Use LIMIT for "top N" questions
- Prefer simple SQL over clever SQL
"""


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

    # ------------------------------------------------------------------
    # Deterministic helpers (callable from CodeAct Python)
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
    async def classify_complexity(self, question: str, schema_text: str) -> QueryComplexity:
        """Classify the complexity of this data question.

        Return one of: simple, moderate, complex

        - simple: single table, basic aggregation (COUNT, SUM, AVG)
        - moderate: joins between 2-3 tables, window functions, subqueries
        - complex: multi-step analysis, cross-table correlations, CTEs with multiple stages"""
        ...

    @strategy(CodeActStrategy(config=CodeActConfig(max_iterations=8)))
    async def generate(self, question: str, schema: SchemaMap) -> GeneratedSQL:
        """Generate a safe, correct PostgreSQL query that answers the question.

        Steps you should follow in your Python code:
        1. Write an initial SQL query based on the schema and question
        2. Call self.validate_sql(sql) to check it's safe
        3. Call self.estimate_cost(sql) to check it's efficient
        4. If cost is too high, add WHERE/GROUP BY/LIMIT and retry
        5. Optionally call self.execute_query(sql) to verify it returns data
        6. Return a GeneratedSQL with the final SQL

        The schema is: {schema.compact_repr()}

        Domain guidance (follow these analyst conventions):
        {self.domain_guidance}
        """
        ...
