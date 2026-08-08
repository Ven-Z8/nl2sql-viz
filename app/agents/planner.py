"""QueryPlanner — decomposes complex questions into verifiable sub-queries.

Decomposition is the grounding strategy for hard questions: instead of letting
the model answer a multi-step question in one shot (where it may invent
intermediate numbers), the planner splits it into sub-questions, each of which
is answered by its own SQL query against real data.
"""

from __future__ import annotations

from nooa import Agent, strategy
from nooa.strategies import PredictStrategy

from app.llm import HAIKU
from app.models import SubQuery


class QueryPlanner(Agent, llm=HAIKU):
    """You are an analytics query planner. You break complex data questions into
    simple, verifiable sub-questions that can each be answered by one SQL query.

    Rules:
    - Each sub-question must be answerable by a single SELECT with basic aggregation
    - Never ask the model to compute derived metrics — those come later from data
    - Return an EMPTY list when the question is simple enough for one query
    - Prefer 2-4 sub-questions for genuinely complex questions
    """

    @strategy(PredictStrategy())
    async def decompose(self, question: str, schema_text: str, sample_text: str = "") -> list[SubQuery]:
        """Split ``question`` into verifiable sub-questions.

        Return an empty list if a single query can answer it. Each SubQuery must
        have a short unique id, the sub-question text, and a one-line purpose.

        Schema context:
        {schema_text}

        Sample data (real rows — use these to understand the data shape, grain,
        and value formats when choosing columns and writing sub-questions):
        {sample_text}
        """
        ...
