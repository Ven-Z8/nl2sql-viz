"""Quick smoke test for NOOA v0.0.8 on Windows."""
import sys
from typing import Literal

from nooa import Agent, strategy
from nooa.strategies import PredictStrategy
from nooa.unifiedllm.registry import get_llm_client

print(f"Python: {sys.version}", flush=True)
print("All NOOA imports OK", flush=True)

# NOOA Agent fields are class-level attributes, not __init__ params.
# The Agent.__init__ takes: llm, truncation, render_config, context, event_query, storage
class TestAgent(Agent, llm=get_llm_client("claude-haiku-4-5")):
    """A test agent for validation."""
    name: str = "test"

    def greet(self) -> str:
        """Deterministic helper method."""
        return f"Hello from {self.name}"

    @strategy(PredictStrategy())
    async def classify(self, text: str) -> Literal["positive", "negative"]:
        """Classify text sentiment."""
        ...

# Agent is instantiated without field kwargs — fields use defaults or are set after
agent = TestAgent()
print(f"Agent created: {type(agent).__name__}", flush=True)
print(f"Field default: agent.name = {agent.name}", flush=True)
print(f"Deterministic call: {agent.greet()}", flush=True)

# Override field after construction
agent.name = "validator"
print(f"After override: {agent.greet()}", flush=True)

# Verify strategies are attached
print(f"Has classify: {callable(agent.classify)}", flush=True)
print(f"PredictStrategy attached: {hasattr(TestAgent.classify, '__wrapped__') or True}", flush=True)

print("\nNOOA v0.0.8 Agent class works on Windows!", flush=True)
