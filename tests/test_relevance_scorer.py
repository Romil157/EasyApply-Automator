"""Unit tests for RelevanceScorer evaluating job title relevance against candidate resume profile."""

from __future__ import annotations

import pytest

from easy_apply_automator.qa.relevance_scorer import RelevanceScorer


@pytest.fixture
def scorer() -> RelevanceScorer:
    return RelevanceScorer()


class TestRelevanceScorerMatches:
    """Test titles that directly match the candidate's software, data, security, or IT skills."""

    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineer Intern",
            "Python Developer",
            "Junior Backend Engineer",
            "Full Stack Developer",
            "Data Analyst Intern",
            "Data Scraping Specialist",
            "ETL Pipeline Engineer",
            "Cybersecurity Analyst",
            "Information Security Intern",
            "SOC Analyst",
            "IT Support Engineer",
            "Technical Support Specialist",
            "AI / ML Engineer",
            "Generative AI Intern",
            "Machine Learning Intern",
            "QA Automation Engineer",
            "Financial Analyst",
            "SEO Specialist Intern",
            "Web Development Intern",
            "Node.js Backend Developer",
            "Flask API Engineer",
        ],
    )
    def test_relevant_roles_pass(self, scorer: RelevanceScorer, title: str) -> None:
        assert scorer.is_relevant(title) is True
        assert scorer.score(title) >= 0.5


class TestRelevanceScorerHardBlockers:
    """Test roles that must be blocked immediately (language-specific, creative, healthcare, manual labor)."""

    @pytest.mark.parametrize(
        "title",
        [
            "AI Ad Video Creator - Kannada Language",
            "Content Writer - Hindi",
            "Tamil Voice Over Artist",
            "Video Editor & Motion Designer",
            "Photographer & Videographer",
            "TikTok Creator Intern",
            "Staff Nurse - ICU",
            "Clinical Research Physician",
            "Dental Assistant",
            "Delivery Driver",
            "Warehouse Associate",
            "Kitchen Cook",
            "Primary School Teacher",
            "Real Estate Agent",
            "Insurance Sales Officer",
        ],
    )
    def test_hard_blockers_return_zero(self, scorer: RelevanceScorer, title: str) -> None:
        assert scorer.is_relevant(title) is False
        assert scorer.score(title) == 0.0


class TestRelevanceScorerEdgeCases:
    """Test edge cases such as empty strings, whitespace, special characters, and non-matching titles."""

    def test_empty_and_whitespace_titles(self, scorer: RelevanceScorer) -> None:
        assert scorer.score("") == 0.0
        assert scorer.is_relevant("") is False
        assert scorer.score("   ") == 0.0
        assert scorer.is_relevant("   ") is False

    def test_none_input(self, scorer: RelevanceScorer) -> None:
        assert scorer.score(None) == 0.0  # type: ignore[arg-type]
        assert scorer.is_relevant(None) is False  # type: ignore[arg-type]

    def test_completely_irrelevant_tech_adjacent_title(self, scorer: RelevanceScorer) -> None:
        assert scorer.is_relevant("Office Receptionist") is False
        assert scorer.is_relevant("HR Generalist") is False
        assert scorer.is_relevant("Event Coordinator") is False

    def test_punctuation_and_symbols_in_title(self, scorer: RelevanceScorer) -> None:
        assert scorer.is_relevant("Python / Django / SQL Developer (Intern)") is True
        assert scorer.is_relevant("Backend Engineer [Node.js & Flask]") is True
