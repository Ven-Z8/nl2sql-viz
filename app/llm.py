"""LLM client setup for NL2SQL Viz agents.

Centralizes model selection and provides pre-configured clients for all agents.
Uses NOOA's unifiedllm registry which routes through litellm — model names use
the OpenRouter prefix so all calls go via OpenRouter (key: OPENROUTER_API_KEY).
"""

import os

from dotenv import load_dotenv
from nooa.unifiedllm.registry import get_llm_client

load_dotenv(override=True)

# Primary model: used by SQLAgent, VizAgent, SchemaAgent for complex tasks
SONNET = get_llm_client(os.getenv("NL2SQL_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"))

# Fast model: used by route classification, simple predictions
HAIKU = get_llm_client(os.getenv("NL2SQL_FAST_MODEL", "inclusionai/ling-3.0-tiny:free"))
