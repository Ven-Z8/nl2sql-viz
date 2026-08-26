"""Lightweight NLP classifier for fast query routing.

Uses spaCy for entity extraction and pattern matching when the
``en_core_web_sm`` model is available (~50-100ms inference), and falls back to
a deterministic keyword/heuristic classifier otherwise, so the pipeline works
on any deployment (the model is NOT downloaded at import time — a missing
spaCy or model must never break boot).

Everything here degrades gracefully: spaCy is imported lazily inside the
classifier init, and every public method has a keyword-only code path that
produces stable, sensible results without it.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_AGG_LEMMAS = {"sum", "count", "average", "avg", "total", "max", "min", "mean"}
_JOIN_LEMMAS = {"join", "combine", "merge", "across", "between"}
_COMPARE_WORDS = {"compare", "versus", "vs", "vs.", "compared", "difference"}
_SUBQUERY_HINTS = {"per", "for each", "within", "where", "for every"}

_TIME_FILTER_RE = re.compile(
    r"\b(?:20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    r"|\b(?:last|past|this)\s+(?:\d+\s+)?(?:day|week|month|quarter|year)s?\b",
    re.IGNORECASE,
)


class QueryClassifier:
    """Fast NLP-based query classifier for routing decisions."""

    def __init__(self) -> None:
        self._nlp = None
        self._matcher = None
        self._load_spacy()

    # ------------------------------------------------------------------
    # Lazy, guarded spaCy loading — never raises, never downloads at import
    # ------------------------------------------------------------------

    def _load_spacy(self) -> None:
        try:
            # Optional heavy dependency — imported lazily, never at module load
            import spacy
            from spacy.matcher import Matcher
        except Exception as e:  # ImportError or broken install
            logger.info("spaCy unavailable (%s) — using heuristic classifier", e)
            return
        try:
            self._nlp = spacy.load("en_core_web_sm")
            self._matcher = Matcher(self._nlp.vocab)
            self._setup_patterns()
        except Exception as e:  # OSError: model not installed
            logger.info("spaCy model en_core_web_sm unavailable (%s) — using heuristic classifier", e)
            self._nlp = None
            self._matcher = None

    def _setup_patterns(self) -> None:
        """Setup spaCy matcher patterns for different query types."""
        assert self._matcher is not None

        # KPI/aggregate queries
        self._matcher.add("KPI", [
            [{"LEMMA": {"IN": ["count", "sum", "average", "total", "number"]}}, {"POS": "NOUN"}],
            [{"TEXT": {"IN": ["how many", "how much", "what is the total"]}}, {"POS": "NOUN"}],
        ])

        # Trend/time-series queries
        self._matcher.add("TREND", [
            [{"LEMMA": {"IN": ["trend", "over", "time", "period", "month", "year", "week"]}}],
            [{"TEXT": {"REGEX": r"\b(20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b"}}],
        ])

        # Comparison queries
        self._matcher.add("COMPARISON", [
            [{"LEMMA": {"IN": ["compare", "vs", "versus", "difference", "between"]}}],
            [{"TEXT": {"IN": ["vs", "versus"]}}],
        ])

        # Ranking queries
        self._matcher.add("RANKING", [
            [{"LEMMA": {"IN": ["top", "best", "highest", "lowest", "worst"]}}, {"POS": "NOUN"}],
            [{"TEXT": {"REGEX": r"\btop\s+\d+\b"}}],
        ])

    @property
    def spacy_available(self) -> bool:
        return self._nlp is not None

    def _doc(self, question: str):
        """Return a spaCy doc, or None when running on the fallback path."""
        if self._nlp is None:
            return None
        return self._nlp(question.lower())

    # ------------------------------------------------------------------
    # Public API — each method falls back to keywords when spaCy is absent
    # ------------------------------------------------------------------

    def _augmented(self, question: str, context: str) -> str:
        """Fold conversation context into the working text when present.

        Follow-up questions ("what about 2019?") mention none of the schema,
        so the classifier sees the prior turns' text too. Empty context is a
        no-op — the stateless path is byte-identical to before.
        """
        if not context:
            return question
        return f"{question}\n{context}"

    def classify_complexity(
        self, question: str, schema_tables: list[str], context: str = ""
    ) -> str:
        """
        Classify query complexity: simple, moderate, complex.

        Args:
            question: Natural language question
            schema_tables: List of available table names
            context: Optional conversation context for follow-up questions

        Returns:
            "simple" | "moderate" | "complex"
        """
        q = self._augmented(question, context).lower()
        doc = self._doc(q)

        num_tables_mentioned = sum(1 for table in schema_tables if table.lower() in q)

        if doc is not None:
            num_entities = len([ent for ent in doc.ents if ent.label_ in ["DATE", "CARDINAL", "MONEY"]])
            lemmas = {token.lemma_ for token in doc}
            texts = {token.text for token in doc}
            has_aggregation = bool(lemmas & _AGG_LEMMAS)
            has_join_keywords = bool(lemmas & _JOIN_LEMMAS)
            has_comparison = bool(lemmas & _COMPARE_WORDS or texts & _COMPARE_WORDS)
            has_subquery_indicators = bool(lemmas & {"per", "within", "where"})
        else:
            # Deterministic keyword fallback (no POS/entity data)
            words = set(re.findall(r"\b\w+\b", q))
            num_entities = len(_TIME_FILTER_RE.findall(q))  # dates are the common entity type
            has_aggregation = bool(words & _AGG_LEMMAS)
            has_join_keywords = bool(words & _JOIN_LEMMAS)
            has_comparison = bool(words & _COMPARE_WORDS)
            has_subquery_indicators = bool(words & {"per", "within", "where"}) or any(
                p in q for p in ("for each", "for every")
            )

        complexity_score = 0.0
        complexity_score += num_tables_mentioned
        complexity_score += num_entities * 0.5
        complexity_score += 2 if has_aggregation else 0
        complexity_score += 3 if has_join_keywords else 0
        complexity_score += 6 if has_comparison else 0
        complexity_score += 2 if has_subquery_indicators else 0
        if complexity_score <= 2:
            return "simple"
        elif complexity_score <= 5:
            return "moderate"
        else:
            return "complex"

    def classify_question_type(self, question: str) -> str:
        """
        Classify question type for routing.

        Returns:
            "kpi" | "trend" | "comparison" | "ranking" | "breakdown"
        """
        doc = self._doc(question.lower())
        if doc is not None and self._matcher is not None:
            matches = self._matcher(doc)
            type_counts: dict[str, int] = {}
            for match_id, start, end in matches:
                rule_name = self._nlp.vocab.strings[match_id]
                type_counts[rule_name] = type_counts.get(rule_name, 0) + 1
            if type_counts:
                return max(type_counts, key=lambda k: type_counts[k]).lower()

        # Keyword fallback
        q = question.lower()
        if any(h in q for h in ("how many", "how much", "what is the total")) or \
                re.search(r"\b(count|sum|total|average)\b", q):
            return "kpi"
        if any(h in q for h in ("over time", "trend", "by month", "by year", "monthly", "weekly")) or \
                re.search(r"\b20\d{2}\b", q):
            return "trend"
        if any(h in q for h in (" vs ", " versus ", "compare", "difference between")):
            return "comparison"
        if re.search(r"\b(top|best|highest|lowest|worst)\b", q):
            return "ranking"
        return "breakdown"

    def extract_entities(
        self,
        question: str,
        schema_tables: list[str],
        schema_columns: dict[str, list[str]],
        context: str = "",
    ) -> dict[str, Any]:
        """
        Extract entities and map to schema for fast linking.

        Args:
            question: Natural language question
            schema_tables: List of available table names
            schema_columns: Table name -> column names
            context: Optional conversation context for follow-up questions

        Returns:
            {
                "tables": List[str],
                "columns": List[str],
                "time_filters": List[str],
                "aggregations": List[str]
            }
        """
        q = self._augmented(question, context).lower()
        doc = self._doc(q)

        # Extract mentioned tables (substring match — no NLP required)
        mentioned_tables = [table for table in schema_tables if table.lower() in q]

        # Extract mentioned columns (substring match — no NLP required)
        mentioned_columns = []
        for table, columns in schema_columns.items():
            for col in columns:
                if col.lower() in q:
                    mentioned_columns.append(f"{table}.{col}")

        # Extract time filters
        if doc is not None:
            time_filters = [ent.text for ent in doc.ents if ent.label_ in ["DATE", "TIME"]]
        else:
            time_filters = [m.group(0) for m in _TIME_FILTER_RE.finditer(question)]

        # Extract aggregation functions
        aggregations = []
        if doc is not None:
            aggregations = [token.lemma_ for token in doc if token.lemma_ in _AGG_LEMMAS]
        else:
            words = re.findall(r"\b\w+\b", q)
            aggregations = [w for w in words if w in _AGG_LEMMAS]

        return {
            "tables": mentioned_tables,
            "columns": mentioned_columns,
            "time_filters": time_filters,
            "aggregations": aggregations,
        }


# Singleton instance
_classifier: QueryClassifier | None = None


def get_classifier() -> QueryClassifier:
    """Get singleton classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier
