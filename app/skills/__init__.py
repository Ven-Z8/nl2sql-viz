"""Domain skills — per-domain analyst knowledge loaded from SKILL.md bundles.

NOOA's native skill system: each domain is a directory containing a
SKILL.md (frontmatter: name + description; body: analyst guidance). Skills
are loaded with TextSkill and their guidance is injected into SQL
generation so queries and answers follow domain conventions.
"""

from __future__ import annotations

from pathlib import Path

from nooa import TextSkill

_SKILLS_DIR = Path(__file__).parent


def _load_skills() -> dict[str, TextSkill]:
    skills: dict[str, TextSkill] = {}
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            try:
                skill = TextSkill(path=skill_dir)
                skills[skill.id] = skill
            except Exception:
                continue  # skip malformed skill dirs
    return skills


DOMAIN_SKILLS: dict[str, TextSkill] = _load_skills()


def get_domain_skill(domain: str) -> TextSkill:
    """Return the skill for a domain, falling back to general."""
    return DOMAIN_SKILLS.get(domain, DOMAIN_SKILLS["general"])


def skill_guidance(skill: TextSkill) -> str:
    """Extract the guidance body from a skill's SKILL.md (after frontmatter)."""
    content = skill.read_file("SKILL.md")
    parts = content.split("---", 2)
    return parts[2].strip() if len(parts) >= 3 else content


def list_domains() -> list[dict[str, str]]:
    """Return the available domains for the upload UI."""
    return [
        {"id": skill.id, "name": skill.description}
        for skill in DOMAIN_SKILLS.values()
    ]