"""Tests for domain skills — registry, guidance content, NOOA Skill integration."""

from app.skills import DOMAIN_SKILLS, get_domain_skill, list_domains
from app.skills.base import DomainSkill


class TestDomainSkills:
    def test_all_skills_are_domain_skills(self):
        for skill in DOMAIN_SKILLS.values():
            assert isinstance(skill, DomainSkill)

    def test_registry_has_expected_domains(self):
        assert set(DOMAIN_SKILLS.keys()) == {
            "general", "retail", "healthcare", "finance", "marketing", "saas", "operations",
        }

    def test_get_domain_skill_returns_matching(self):
        assert get_domain_skill("retail").domain == "retail"

    def test_unknown_domain_falls_back_to_general(self):
        assert get_domain_skill("astrology").domain == "general"

    def test_guidance_is_non_empty(self):
        for skill in DOMAIN_SKILLS.values():
            assert len(skill.guidance()) > 50, f"{skill.domain} guidance too short"

    def test_guidance_mentions_kpis(self):
        retail = get_domain_skill("retail")
        assert "AOV" in retail.guidance()
        assert "cohort" in retail.guidance().lower()

    def test_list_domains_for_ui(self):
        domains = list_domains()
        assert any(d["id"] == "retail" for d in domains)
        assert all("name" in d and "id" in d for d in domains)

    def test_skill_is_nooa_skill(self):
        from nooa.skill import Skill
        assert issubclass(DomainSkill, Skill)