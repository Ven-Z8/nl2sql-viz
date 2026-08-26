"""In-memory per-user conversation thread registry (Contract V3).

Threads give follow-up questions ("what about 2019?", "show only the top 5",
"now split by region") short-term conversational memory. Each turn stores the
question text, the SQL that ran, the row count and a COMPACT summary of the
result (columns + a few example values — never full rows), plus the tables
the turn touched so pronouns resolve against the right part of the schema.

Bounds & lifecycle:
- max 20 turns per thread — oldest dropped past the cap, while the 1-based
  turn counter keeps increasing so indices stay stable for clients
- max 50 threads per user, LRU-evicted on insert
- 30 min idle TTL, swept lazily whenever that user touches the store

Every operation is synchronous dict/dataclass mutation (no awaits), so under
the asyncio event loop each one is atomic without locks. Ownership is enforced
at lookup: another user's thread_id is indistinguishable from an unknown one
and silently starts a fresh thread — it can never raise or leak state.
A process restart forgets all threads; clients then simply get new ids.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field

MAX_TURNS_PER_THREAD = 20        # oldest turns dropped past this
MAX_THREADS_PER_USER = 50        # LRU-evicted on insert
THREAD_TTL_SECONDS = 30 * 60     # idle TTL — lazy sweep on access

_MAX_SUMMARY_VALUES = 3          # example values per column in summaries
_MAX_SUMMARY_COLUMNS = 8         # columns tracked per turn summary
_MAX_VALUE_CHARS = 24            # per example value
_MAX_QUESTION_CHARS = 200        # per question inside summaries/context
_MAX_CONTEXT_TURNS = 10          # turns rendered into one context block

# Fallback table-name extraction when sqlglot cannot parse the SQL.
_FROM_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", re.IGNORECASE)


@dataclass
class Turn:
    """One completed question/answer round inside a thread."""

    index: int                       # 1-based, monotonic within the thread
    question: str
    sql: str
    row_count: int
    compact_summary: str             # columns + example values, never full rows
    tables: list[str] = field(default_factory=list)  # schema link for this turn
    clarification: str | None = None  # clarify round-trip outcome, when any


@dataclass
class Thread:
    """A per-user conversation thread."""

    thread_id: str
    user_id: str
    created_at: float                # time.monotonic()
    last_used_at: float              # time.monotonic() — drives the idle TTL
    turns: list[Turn] = field(default_factory=list)
    turn_counter: int = 0            # survives eviction of old turns
    pending_clarification: str | None = None  # set mid-query, consumed on record
    # Monotonic access sequence — breaks LRU ties when several threads are
    # touched within the same clock tick (coarse on some platforms).
    last_seq: int = 0


def compact_summary_from_rows(rows: list[dict]) -> str:
    """Summarize result rows as columns + up to 3 example values each.

    Deliberately NOT full rows — the context block must stay small enough to
    inject into every SQL-generation prompt. Braces are neutralized because
    the block is interpolated into LLM prompt templates.
    """
    if not rows:
        return "no rows"
    parts: list[str] = []
    for col in list(rows[0].keys())[:_MAX_SUMMARY_COLUMNS]:
        values: list[str] = []
        seen: set[str] = set()
        for row in rows:
            raw = row.get(col)
            if raw is None:
                continue
            text = str(raw)[:_MAX_VALUE_CHARS].replace("{", "(").replace("}", ")")
            if text not in seen:
                seen.add(text)
                values.append(text)
            if len(values) >= _MAX_SUMMARY_VALUES:
                break
        parts.append(f"{col} in ({', '.join(values) if values else 'n/a'})")
    return "; ".join(parts)


def tables_from_sql(sql: str) -> list[str]:
    """Extract the table names a turn's SQL touched (best-effort, deduped).

    Used as the "current schema link from the prior turn". sqlglot parses
    real SQL; anything unparseable falls back to a FROM/JOIN regex. Never
    raises — a broken extractor must not break turn recording.
    """
    if not sql:
        return []
    names: list[str] = []
    try:
        import sqlglot
        from sqlglot import exp

        parsed = sqlglot.parse_one(sql, dialect="postgres")
        for node in parsed.find_all(exp.Table):
            name = node.name
            if name:
                names.append(name)
    except Exception:  # noqa: BLE001 — parsing is best-effort
        names = [m.group(1).split(".")[-1] for m in _FROM_RE.finditer(sql)]
    deduped: list[str] = []
    for name in names:
        if name.lower() not in {d.lower() for d in deduped}:
            deduped.append(name)
    return deduped[:6]


def build_context_block(turns: list[Turn]) -> str:
    """Render recent turns into the follow-up context block for LLM prompts.

    Empty when there are no prior turns, so self-contained questions produce
    byte-identical prompts to the stateless pipeline.
    """
    if not turns:
        return ""
    lines = [
        "CONVERSATION CONTEXT — this question may be a FOLLOW-UP referring to",
        'earlier turns. Resolve pronouns and ellipsis ("what about 2019?",',
        '"only the top 5", "now split by region") against this history:',
    ]
    for t in turns[-_MAX_CONTEXT_TURNS:]:
        question = t.question[:_MAX_QUESTION_CHARS]
        line = (
            f"- Turn {t.index}: asked {question!r} -> {t.row_count} rows; "
            f"columns/values: {t.compact_summary}"
        )
        if t.tables:
            line += f"; tables used: {', '.join(t.tables)}"
        if t.clarification:
            line += f"; clarification: {t.clarification}"
        lines.append(line)
    lines.append(
        "Reuse these tables/columns unless the new question clearly targets "
        "something else."
    )
    # The block is interpolated into LLM prompt templates — neutralize any
    # braces coming from user-typed questions so template engines that
    # re-parse interpolated values can never choke on them.
    block = "\n".join(lines)
    return block.replace("{", "(").replace("}", ")")


class ThreadStore:
    """Per-user in-memory thread registry with TTL, LRU and turn bounds."""

    def __init__(
        self,
        ttl_seconds: float = THREAD_TTL_SECONDS,
        max_threads_per_user: int = MAX_THREADS_PER_USER,
        max_turns_per_thread: int = MAX_TURNS_PER_THREAD,
    ) -> None:
        self._threads: dict[str, Thread] = {}
        self._ttl_seconds = ttl_seconds
        self._max_threads_per_user = max_threads_per_user
        self._max_turns_per_thread = max_turns_per_thread
        self._seq = 0  # process-wide access counter — LRU ordering

    def _touch(self, thread: Thread) -> None:
        """Mark a thread as just used (TTL clock + strict LRU order)."""
        thread.last_used_at = time.monotonic()
        self._seq += 1
        thread.last_seq = self._seq

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def resolve_or_create(self, user_id: str, thread_id: str | None = None) -> Thread:
        """Join ``thread_id`` when owned and fresh; otherwise start a new one.

        Unknown, expired AND foreign ids are treated identically (fresh
        thread, no error) so ownership leaks nothing.
        """
        self._sweep_user(user_id)
        if thread_id:
            thread = self._threads.get(thread_id)
            if thread is not None and thread.user_id == user_id:
                # A brand-new query invalidates any clarify left pending by a
                # previous failed/timed-out run.
                thread.pending_clarification = None
                self._touch(thread)
                return thread
        return self._create(user_id)

    def record_turn(
        self,
        thread: Thread,
        *,
        question: str,
        sql: str = "",
        row_count: int = 0,
        summary: str = "",
        tables: list[str] | None = None,
    ) -> int:
        """Append a completed turn and return its stable 1-based index."""
        thread.turn_counter += 1
        turn = Turn(
            index=thread.turn_counter,
            question=question[:_MAX_QUESTION_CHARS],
            sql=sql[:500],
            row_count=row_count,
            compact_summary=summary or "no rows",
            tables=list(tables or []),
            clarification=thread.pending_clarification,
        )
        thread.pending_clarification = None
        thread.turns.append(turn)
        while len(thread.turns) > self._max_turns_per_thread:
            thread.turns.pop(0)
        self._touch(thread)
        return turn.index

    def note_clarification(self, thread: Thread, question: str, outcome: str) -> None:
        """Attach a clarify round-trip to the turn currently being answered.

        Consumed by the next record_turn() call — i.e. it lands on the very
        turn the clarification belonged to.
        """
        thread.pending_clarification = (
            f'asked {question[:120]!r} -> {outcome[:120]}'
        )

    def context_block(self, thread: Thread) -> str:
        """The follow-up context block for this thread's NEXT query."""
        return build_context_block(thread.turns)

    def reset(self) -> None:
        """Test/dev helper — drop every thread (mirrors connections.reset_registry)."""
        self._threads.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create(self, user_id: str) -> Thread:
        now = time.monotonic()
        thread = Thread(
            thread_id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            last_used_at=now,
        )
        self._threads[thread.thread_id] = thread
        self._touch(thread)
        self._evict_lru(user_id)
        return thread

    def _sweep_user(self, user_id: str) -> None:
        """Lazy TTL sweep — only runs when this user touches the store."""
        now = time.monotonic()
        expired = [
            tid
            for tid, t in self._threads.items()
            if t.user_id == user_id and now - t.last_used_at > self._ttl_seconds
        ]
        for tid in expired:
            del self._threads[tid]

    def _evict_lru(self, user_id: str) -> None:
        """Keep at most max_threads_per_user live threads per user."""
        mine = sorted(
            (t.last_seq, tid)
            for tid, t in self._threads.items()
            if t.user_id == user_id
        )
        while len(mine) > self._max_threads_per_user:
            _, oldest = mine.pop(0)
            del self._threads[oldest]


_store: ThreadStore | None = None


def get_thread_store() -> ThreadStore:
    """Get the process-wide singleton thread store."""
    global _store
    if _store is None:
        _store = ThreadStore()
    return _store
