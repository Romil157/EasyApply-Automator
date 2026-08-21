"""Unit tests for job classification and title blacklist filtering."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


class DummyOrchestrator:
    """Lightweight test fixture mimicking LinkedInEasyApplyOrchestrator for title classification."""

    def __init__(
        self,
        blacklist_titles: list[str] | None = None,
        database_keywords: list[str] | None = None,
        medical_keywords: list[str] | None = None,
    ):
        self.blacklist_titles = blacklist_titles or []
        self.database_related_title_keywords = database_keywords or []
        self.medical_related_keywords = medical_keywords or []
        self.browser = MagicMock()
        self.stop_requested = False
        self.stop_reason = None
        self.log_event = MagicMock()

    def _medical_keyword_match(self) -> str | None:
        title = self.browser.title.lower() if self.browser.title else ""
        for kw in self.medical_related_keywords:
            if kw.lower() in title:
                return kw
        return None

    _normalize_title_text = staticmethod(LinkedInEasyApplyOrchestrator._normalize_title_text)
    _classify_job = LinkedInEasyApplyOrchestrator._classify_job


class TestJobClassification:
    @pytest.fixture
    def classifier(self):
        blacklist = [
            "founder's office",
            "business development",
            "operations & strategy",
            "brand face",
            "growth intern",
            "ui/ux design",
            "outreach",
            "sales intern",
            "human resources",
            "hr intern",
            "marketing research",
            "growth & gtm",
            "growth & strategy",
            "private equity",
            "data annotator",
            "b2b lead generation",
        ]
        medical = ["medical", "clinical", "healthcare"]
        return DummyOrchestrator(
            blacklist_titles=blacklist,
            database_keywords=[],  # database_related removed for tech/data roles
            medical_keywords=medical,
        )

    @pytest.mark.parametrize(
        "title,expected_reason",
        [
            ("Founder’s Office Intern | Volody | LinkedIn", "title_blacklisted"),
            ("Business Development Intern | OTMOS | LinkedIn", "title_blacklisted"),
            ("Operations & Strategy Intern | Joveo | LinkedIn", "title_blacklisted"),
            ("Brand Face & Growth Intern — Founder's Office | Sankar Group", "title_blacklisted"),
            ("UI/UX Design Founding Intern | KauROs | LinkedIn", "title_blacklisted"),
            ("Outreach Intern | LockedIn. | LinkedIn", "title_blacklisted"),
            ("Sales Intern | ABC Corp | LinkedIn", "title_blacklisted"),
            ("HR Intern | Tech Services | LinkedIn", "title_blacklisted"),
            ("Marketing Research Intern | Rablo | LinkedIn", "title_blacklisted"),
            ("Growth & GTM Intern | EnglishBhashi | LinkedIn", "title_blacklisted"),
            ("Private Equity Intern | Zetheta Algorithms | LinkedIn", "title_blacklisted"),
            ("Data Annotator Intern | Zapdos Labs | LinkedIn", "title_blacklisted"),
            ("B2B Lead Generation Internship | Tech Trek | LinkedIn", "title_blacklisted"),
            ("Clinical Research Assistant | HealthCorp | LinkedIn", "medical_related_title"),
        ],
    )
    def test_unwanted_titles_are_skipped(self, classifier, title, expected_reason):
        classifier.browser.title = title
        btn = MagicMock()
        result, reason, _ = classifier._classify_job("12345", btn)
        assert result is False
        assert reason == expected_reason

    def test_relevant_software_and_data_jobs_not_blacklisted(self, classifier):
        # Verify that Data Engineering / SQL / Python roles are NOT skipped
        relevant_titles = [
            "Software Engineering Intern | Google | LinkedIn",
            "Python Developer Intern | Startup | LinkedIn",
            "Marketing Data Engineering Intern | Martechture | LinkedIn",
            "Data Science internship | Sekuen | LinkedIn",
            "Data Analyst Intern | Analytics Co | LinkedIn",
            "AI / ML Engineer Intern | AI Corp | LinkedIn",
            "Cybersecurity Intern | Security Inc | LinkedIn",
            "Finance Intern | Goldman Sachs | LinkedIn",
            "Financial Analyst Intern | Morgan Stanley | LinkedIn",
            "Investment Banking Analyst | J.P. Morgan | LinkedIn",
        ]
        for title in relevant_titles:
            classifier.browser.title = title
            btn = MagicMock()
            # Mock downstream apply methods to simulate successful progression
            classifier._click_easy_apply = MagicMock()
            classifier._dump_debug_html = MagicMock()
            classifier._human_sleep = MagicMock()
            classifier.fill_out_fields = MagicMock()
            classifier.send_resume = MagicMock(return_value=True)

            result, reason, _ = classifier._classify_job("12345", btn)
            assert result is True
            assert reason == "submitted"
