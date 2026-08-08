"""Domain skills package — analyst knowledge per industry."""

from app.skills.base import DomainSkill
from app.skills.domains import DOMAIN_SKILLS, get_domain_skill, list_domains

__all__ = ["DomainSkill", "DOMAIN_SKILLS", "get_domain_skill", "list_domains"]