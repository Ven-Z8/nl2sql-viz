"""Unit tests for follow-up context injection points (Contract V3, T2).

The context block must reach BOTH halves of the pipeline:
  - the fast NLP classifier (schema linking + complexity routing), and
  - the NL2SQL / planner prompts (SQLAgent template slots).
Empty context must be a strict no-op everywhere (stateless regression guard).
"""
from app.agents.sql_agent import SQLAgent
from app.core.threads import ThreadStore
from app.engine.nlp_classifier import get_classifier

_CONTEXT = (
    "CONVERSATION CONTEXT - this question may be a FOLLOW UP referring to\n"
    "earlier turns:\n"
    "- Turn 1: asked 'total sales by region' -> 3 rows; columns/values: "
    "region in (North, South, East); amount in (2500.0, 1800.0); "
    "tables used: sales"
)


def _classifier():
    return get_classifier()


def test_extract_entities_context_resolves_prior_turn_tables():
    c = _classifier()
    tables = ["sales", "customers"]
    columns = {"sales": ["region", "amount"], "customers": ["name"]}

    # Elliptical follow-up alone names no schema objects...
    solo = c.extract_entities("what about 2019?", tables, columns)
    assert solo["tables"] == []

    # ...but the SAME question inside its thread links the prior turn's table,
    # which is exactly how "show only the top 5" keeps working on sales.
    linked = c.extract_entities("what about 2019?", tables, columns, context=_CONTEXT)
    assert linked["tables"] == ["sales"]


def test_classify_complexity_context_can_escalate_routing():
    c = _classifier()
    # A terse follow-up alone routes as simple...
    assert c.classify_complexity("now split by region", ["sales"]) == "simple"

    # ...while the same words inside a comparative conversation route complex.
    ctx = "Turn 1: asked 'compare north versus south revenue' -> 2 rows"
    escalated = c.classify_complexity(
        "now split by region", ["sales"], context=ctx
    )
    assert escalated in ("moderate", "complex")


def test_empty_context_is_a_strict_noop_for_classifier():
    c = _classifier()
    tables = ["sales"]
    columns = {"sales": ["region"]}
    baseline = c.extract_entities("total sales by region", tables, columns)
    explicit_empty = c.extract_entities(
        "total sales by region", tables, columns, context=""
    )
    assert baseline == explicit_empty


def test_threadstore_context_block_only_after_first_turn():
    store = ThreadStore()
    thread = store.resolve_or_create("u")
    assert store.context_block(thread) == ""          # self-contained query
    store.record_turn(thread, question="q1", row_count=2, summary="a in (1, 2)")
    block = store.context_block(thread)
    assert "CONVERSATION CONTEXT" in block
    assert "{" not in block and "}" not in block      # template-safe


def test_sqlagent_prompts_have_context_slots_defaulting_empty():
    # Field defaults empty -> stateless prompts render byte-identical.
    agent = SQLAgent()
    assert agent.conversation_context == ""
    agent.conversation_context = _CONTEXT             # assignable per query
    assert agent.conversation_context == _CONTEXT

    # Both generation prompts carry the slot.
    assert "{self.conversation_context}" in SQLAgent.generate_simple.__doc__
    assert "{self.conversation_context}" in SQLAgent.plan_analysis.__doc__
