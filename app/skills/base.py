"""DomainSkill — per-domain analyst knowledge injected into SQL generation.

Each domain skill carries the KPIs, metric definitions, analysis patterns,
chart preferences, and pitfalls that a human analyst in that domain would
know. When a user uploads a dataset and picks a domain, the active skill's
guidance is injected into the SQL agent's context so generated queries and
answers are grounded in domain conventions.
"""

from __future__ import annotations

from typing import Any

from nooa.skill import Skill


class DomainSkill(Skill):
    """Base class for domain analytics skills."""

    domain: str = "general"
    display_name: str = "General Analytics"

    _guidance: str = ""

    def guidance(self) -> str:
        """Return the domain guidance text injected into SQL generation."""
        return self._guidance

    def attach(self, agent: Any) -> None:
        """NOA Skill hook — keep a reference to the host agent."""
        self._agent = agent