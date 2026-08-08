"""Tests for domain skills — SKILL.md bundles loaded via NOOA TextSkill."""

from nooa import TextSkill

from app.skills import DOMAIN_SKILLS, get_domain_skill, list_domains, skill_guidance


class TestDomainSkills:
    def test_all_skills_are_text_skills(self):
        for skill in DOMAIN_SKILLS.values():
            assert isinstance(skill, TextSkill)

    def test_registry_has_expected_domains(self):
        assert set(DOMAIN_SKILLS.keys()) == {
            "general", "retail", "healthcare", "finance", "marketing", "saas",
            "operations", "hr",
        }

    def test_get_domain_skill_returns_matching(self):
        assert get_domain_skill("retail").id == "retail"

    def test_unknown_domain_falls_back_to_general(self):
        assert get_domain_skill("astrology").id == "general"

    def test_guidance_is_non_empty(self):
        for skill in DOMAIN_SKILLS.values():
            assert len(skill_guidance(skill)) > 50, f"{skill.id} guidance too short"

    def test_guidance_mentions_kpis(self):
        retail = get_domain_skill("retail")
        assert "AOV" in skill_guidance(retail)
        assert "cohort" in skill_guidance(retail).lower()

    def test_list_domains_for_ui(self):
        domains = list_domains()
        assert any(d["id"] == "retail" for d in domains)
        assert all("name" in d and "id" in d for d in domains)

    def test_skill_has_description(self):
        assert get_domain_skill("retail").description == "Retail & E-commerce"