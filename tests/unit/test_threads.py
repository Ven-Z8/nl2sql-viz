"""Unit tests for the in-memory conversation ThreadStore (Contract V3, T1).

Covers TTL expiry, LRU eviction, ownership isolation, turn bounds, clarify
round-trip bookkeeping, and the compact-summary/context-block builders that
feed follow-up context into the pipeline.
"""
import pytest

from app.core.threads import (
    Thread,
    ThreadStore,
    build_context_block,
    compact_summary_from_rows,
    get_thread_store,
    tables_from_sql,
)


@pytest.fixture()
def store() -> ThreadStore:
    # Small bounds so eviction/expiry tests stay cheap and readable.
    return ThreadStore(ttl_seconds=1800, max_threads_per_user=3, max_turns_per_thread=4)


def _age(thread: Thread, seconds: float) -> None:
    """Rewind a thread's idle clock without sleeping."""
    thread.last_used_at -= seconds


# ----------------------------------------------------------------------
# Lifecycle: create / join / echo
# ----------------------------------------------------------------------

def test_create_then_join_returns_same_thread(store):
    t = store.resolve_or_create("alice")
    assert len(t.thread_id) == 36  # uuid4
    assert store.resolve_or_create("alice", t.thread_id) is t


def test_unknown_thread_id_starts_fresh(store):
    fresh = store.resolve_or_create("alice", "not-a-real-thread-id")
    assert fresh.thread_id != "not-a-real-thread-id"


def test_ttl_expiry_starts_fresh_and_drops_old_entry(store):
    t = store.resolve_or_create("alice")
    _age(t, 1800 + 1)  # just past the TTL
    revived = store.resolve_or_create("alice", t.thread_id)
    assert revived is not t
    assert revived.thread_id != t.thread_id
    assert store._threads.get(t.thread_id) is None  # swept lazily


def test_idle_but_within_ttl_thread_still_joins(store):
    t = store.resolve_or_create("alice")
    _age(t, 1799)
    assert store.resolve_or_create("alice", t.thread_id) is t


# ----------------------------------------------------------------------
# Ownership isolation — never an error, always a fresh thread
# ----------------------------------------------------------------------

def test_foreign_thread_id_is_not_found_and_starts_fresh(store):
    alice_t = store.resolve_or_create("alice")
    mallory_t = store.resolve_or_create("mallory", alice_t.thread_id)
    assert mallory_t is not alice_t
    assert mallory_t.thread_id != alice_t.thread_id
    assert mallory_t.user_id == "mallory"
    # Alice's thread untouched by the foreign access attempt.
    assert store._threads[alice_t.thread_id] is alice_t
    assert alice_t.turns == []


def test_evicted_thread_join_restarts_fresh(store):
    t1 = store.resolve_or_create("u")
    store.resolve_or_create("u")
    store.resolve_or_create("u")          # at cap of 3
    store.resolve_or_create("other-user")  # unrelated user unaffected
    store.resolve_or_create("u")          # evicts LRU → t1
    again = store.resolve_or_create("u", t1.thread_id)
    assert again is not t1 and again.user_id == "u"


# ----------------------------------------------------------------------
# Bounds: LRU eviction + max turns
# ----------------------------------------------------------------------

def test_lru_evicts_least_recently_used_thread(store):
    t1 = store.resolve_or_create("u")
    t2 = store.resolve_or_create("u")
    t3 = store.resolve_or_create("u")
    store.resolve_or_create("u", t2.thread_id)  # touch t2 → t1 becomes LRU
    t4 = store.resolve_or_create("u")
    ids = {tid for tid, t in store._threads.items() if t.user_id == "u"}
    assert ids == {t2.thread_id, t3.thread_id, t4.thread_id}
    assert t1.thread_id not in ids


def test_turn_cap_drops_oldest_keeps_counter_monotonic(store):
    t = store.resolve_or_create("u")
    indices = [
        store.record_turn(
            t, question=f"q{n}", sql="SELECT 1", row_count=n, summary="s"
        )
        for n in range(1, 7)
    ]
    assert indices == [1, 2, 3, 4, 5, 6]      # stable 1-based counter
    assert t.turn_counter == 6
    assert [turn.index for turn in t.turns] == [3, 4, 5, 6]
    assert [turn.question for turn in t.turns] == ["q3", "q4", "q5", "q6"]


def test_record_turn_updates_last_used_for_lru(store):
    # Oldest thread gets a turn recorded → its access recency jumps ahead
    # of two threads created later, and IT survives the next eviction.
    t = store.resolve_or_create("u")
    _age(t, 500)                                   # stale TTL clock
    other = store.resolve_or_create("u")           # created later...
    third = store.resolve_or_create("u")
    store.record_turn(t, question="q", row_count=0, summary="")  # ...but t used now
    final = store.resolve_or_create("u")           # over cap → LRU (`other`) goes
    live_ids = {
        tid for tid, thread in store._threads.items() if thread.user_id == "u"
    }
    assert live_ids == {t.thread_id, third.thread_id, final.thread_id}
    assert store._threads.get(other.thread_id) is None


# ----------------------------------------------------------------------
# Clarify round-trip bookkeeping
# ----------------------------------------------------------------------

def test_note_clarification_attaches_to_next_recorded_turn(store):
    t = store.resolve_or_create("u")
    store.note_clarification(t, "Focus on which table?", "orders")
    idx = store.record_turn(t, question="show totals", row_count=2, summary="s")
    assert t.turns[-1].clarification == 'asked \'Focus on which table?\' -> orders'
    assert idx == 1


def test_pending_clarification_cleared_on_next_query_join(store):
    t = store.resolve_or_create("u")
    store.note_clarification(t, "Which table?", "orders")
    # Query errored out before a result; the next query re-joins the thread.
    same = store.resolve_or_create("u", t.thread_id)
    assert same is t
    store.record_turn(same, question="next question", row_count=1, summary="s")
    assert same.turns[-1].clarification is None  # stale pending never leaks


# ----------------------------------------------------------------------
# compact_summary_from_rows
# ----------------------------------------------------------------------

def test_compact_summary_columns_with_at_most_three_example_values():
    rows = [
        {"region": f"R{i}", "amount": i * 10} for i in range(5)
    ]
    summary = compact_summary_from_rows(rows)
    assert "region" in summary and "amount" in summary
    # exactly 3 example values per column, NOT all five rows
    assert summary.count(",") <= summary.count(" in (") * 2
    assert "R0" in summary and "R2" in summary and "R4" not in summary


def test_compact_summary_truncates_long_values_and_sanitizes_braces():
    rows = [{"note": "x" * 100 + "{}"}]
    summary = compact_summary_from_rows(rows)
    assert "{" not in summary and "}" not in summary
    assert len(summary) < 100


def test_compact_summary_handles_empty_rows_and_missing_values():
    assert compact_summary_from_rows([]) == "no rows"
    summary = compact_summary_from_rows([{"a": None}])
    assert "n/a" in summary


# ----------------------------------------------------------------------
# tables_from_sql + context block
# ----------------------------------------------------------------------

def test_tables_from_sql_parses_sqlglot_extracts_tables():
    sql = (
        "SELECT r.region, SUM(s.amount) FROM sales s "
        "JOIN regions r ON r.id = s.region_id GROUP BY r.region"
    )
    tables = tables_from_sql(sql)
    lowered = [t.lower() for t in tables]
    assert "sales" in lowered and "regions" in lowered


def test_tables_from_sql_regex_fallback_on_unparseable_sql():
    sql = "GIBBERISH ### FROM mystery_tbl JOIN other_tbl ON 1=1 ((("
    tables = [t.lower() for t in tables_from_sql(sql)]
    assert "mystery_tbl" in tables and "other_tbl" in tables


def test_tables_from_sql_empty_input():
    assert tables_from_sql("") == []


def test_context_block_contains_question_summaries_and_schema_link():
    store = ThreadStore()
    thread = store.resolve_or_create("u")
    store.record_turn(
        thread,
        question="Total sales by region",
        sql="SELECT region, SUM(amount) FROM sales GROUP BY region",
        row_count=4,
        summary=compact_summary_from_rows([{"region": "North", "amount": 2500.0}]),
        tables=["sales"],
    )
    block = build_context_block(thread.turns)
    assert "CONVERSATION CONTEXT" in block
    assert "Total sales by region" in block
    assert "sales" in block                      # schema link from prior turn
    assert "North" in block                      # example value, not full rows
    assert "SELECT region" not in block          # SQL itself stays out


def test_context_block_empty_without_prior_turns():
    assert build_context_block([]) == ""
    store = ThreadStore()
    assert store.context_block(store.resolve_or_create("u")) == ""


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------

def test_singleton_is_stable_and_resettable():
    assert get_thread_store() is get_thread_store()
    get_thread_store().reset()
    get_thread_store().resolve_or_create("temp-user")
    get_thread_store().reset()  # don't leak state into other tests
    assert get_thread_store()._threads == {}
