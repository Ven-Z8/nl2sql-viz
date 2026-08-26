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
    # Per-dataset few-shot examples (Vanna-style RAG). Each entry is
    # {"question": ..., "sql": ...} and gets injected into the prompt
    # so the model sees the actual JOIN patterns and column names for
    # this dataset instead of guessing. Empty list = no examples.
    few_shot_examples: list[dict[str, str]] = []

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

    def _format_few_shot(self) -> str:
        """Format the per-dataset examples as a prompt block (Vanna-style).

        Returns an empty string when no examples are loaded so the prompt
        stays clean for custom-DSN connections.
        """
        if not self.few_shot_examples:
            return ""
        lines = ["## Few-shot examples for this dataset (use as reference for column names, JOIN patterns, and conventions)", ""]
        for i, ex in enumerate(self.few_shot_examples, 1):
            q = ex.get("question", "").strip()
            sql = ex.get("sql", "").strip()
            if not q or not sql:
                continue
            lines.append(f"### Example {i}")
            lines.append(f"Q: {q}")
            lines.append("```sql")
            lines.append(sql)
            lines.append("```")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Generation methods
    # ------------------------------------------------------------------

    @strategy(PredictStrategy())
    async def generate_simple(self, question: str, schema: SchemaMap, sample_text: str = "", feedback: str = "") -> GeneratedSQL:
        """You are a senior PostgreSQL analytics engineer. Generate ONE
        read-only SELECT that answers the question. Think step-by-step, then
        output the SQL.

        ## Reasoning steps (think before writing SQL)
        1. What is the question actually asking? Restate it in your own words.
        2. Which table(s) in the schema hold the data? Use ONLY the tables
           and columns listed in the schema below — never invent column names.
        3. Which columns answer the question (metric, dimension, filter)?
           Cross-check EVERY column you plan to use against the schema. If a
           column is not in the schema, it does not exist — pick a different one.
        4. What aggregation/grouping/ordering is needed? Use the user's own
           words: "largest" → ORDER BY ... DESC LIMIT, "trend over time" →
           GROUP BY date/time column, "share" → ratio with NULLIF guard, etc.
        5. Are derived metrics safe in SQL? Prefer SQL for ratios/percentages
           using NULLIF(denominator, 0). For percentages 0-1, multiply by 100.

        ## Hard rules (violations fail validation)
        - READ-ONLY: no INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE.
        - Every column you reference MUST appear in the schema below.
        - Prefer a single query. Use CTEs (WITH ... AS) if you need a temp step.
        - Date filters must use ISO format. Text filters: case-insensitive (ILIKE).
        - For "top N": ORDER BY <metric> DESC LIMIT N. For "bottom N": ASC LIMIT N.
        - Do NOT compute percentages by hardcoding a denominator — derive it
          from the data (e.g. (revenue / NULLIF(total_revenue, 0)) * 100).
        - If a filter is ambiguous (e.g. "active users"), use a defensible
          interpretation based on the schema and state your interpretation
          in the explanation.

        ## Schema
        {schema.compact_repr()}

        ## Sample rows (verify column names and value formats here)
        {sample_text}

        ## Domain guidance
        {self.domain_guidance}

        {self.conversation_context}

        {self._format_few_shot()}

        ## Previous attempt feedback (if any — fix these specific errors)
        {feedback}

        ## Output
        Return GeneratedSQL{{sql: <final SQL>, explanation: <one sentence>}}
        """
        ...

    @strategy(PredictStrategy())
    async def plan_analysis(self, question: str, schema: SchemaMap, sample_text: str = "") -> list[SubQuery]:
        """You are decomposing a complex business question into 3-5
        independent sub-questions that, when answered together, give the
        full picture.

        ## Reasoning steps
        1. Read the question. Identify the distinct comparisons, time periods,
           or entities the user wants to understand.
        2. Each sub-question must be answerable by ONE SELECT with basic
           aggregation (GROUP BY + COUNT/SUM/AVG, optional ORDER BY + LIMIT).
        3. Sub-questions should be INDEPENDENT (one can fail without
           breaking the others). Don't chain them with UNIONs or joins.
        4. Order them so the first sub-question is the most foundational /
           headline answer; later sub-questions provide context or contrast.
        5. Avoid sub-questions that return nothing useful on their own
           (e.g. "show me a single row count" when the question is about
           change over time).

        ## Sub-question rules
        - Each sub-question must reference ONLY columns in the schema.
        - Each must be a self-contained natural-language question a user
          would ask, NOT a SQL fragment.
        - 3-5 sub-questions total. If the question is simple, return an
          empty list — the simple path handles it.

        ## Schema
        {schema.compact_repr()}

        ## Sample rows
        {sample_text}

        ## Domain guidance
        {self.domain_guidance}

        {self.conversation_context}

        {self._format_few_shot()}
        """
        ...
