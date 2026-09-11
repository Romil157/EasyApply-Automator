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
    _matches_title_keyword = staticmethod(LinkedInEasyApplyOrchestrator._matches_title_keyword)
    _classify_job = LinkedInEasyApplyOrchestrator._classify_job
    is_title_blacklisted = LinkedInEasyApplyOrchestrator.is_title_blacklisted


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

    def test_similar_jobs_redirect(self, classifier):
        classifier.browser.current_url = "https://www.linkedin.com/jobs/collections/similar-jobs/?currentJobId=12345"
        classifier.browser.title = "Similar Jobs | LinkedIn"
        btn = MagicMock()
        result, reason, _ = classifier._classify_job("12345", btn)
        assert result is False
        assert reason == "similar_jobs_redirect"


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

    def test_new_blacklist_keywords_and_word_boundaries(self):
        blacklist = [
            "strategy analyst",
            "strategy",
            "writer",
            "lead",
            "vp",
            "marketing lead",
            "founding",
        ]
        orchestrator = DummyOrchestrator(blacklist_titles=blacklist)

        # Should be blocked
        blocked_titles = [
            "Strategy Analyst | Joveo | LinkedIn",
            "Research Analyst Writer Intern | InternBuddy | LinkedIn",
            "Founding Marketing Lead | Gravity.fast | LinkedIn",
            "Lead Backend Engineer | Tech | LinkedIn",
            "VP of Engineering | Tech | LinkedIn",
        ]
        for title in blocked_titles:
            is_blocked, matched = orchestrator.is_title_blacklisted(title)
            assert is_blocked is True
            assert matched is not None

        # Should NOT be blocked by word boundaries (no substring false positives)
        allowed_titles = [
            "Software Engineer Intern | Google | LinkedIn",
            "Data Analyst Intern | Analytics Co | LinkedIn",
            "DevOps Engineer | Startup | LinkedIn",
        ]
        for title in allowed_titles:
            is_blocked, _ = orchestrator.is_title_blacklisted(title)
            assert is_blocked is False

    def test_is_global_search_element(self):
        from easy_apply_automator.services._form_filler import FormFillerMixin

        search_input = MagicMock()
        search_input.get_attribute.side_effect = lambda attr: {
            "class": "search-global-typeahead__input",
            "id": "global-nav-typeahead",
            "placeholder": "Search",
            "aria-label": "Search",
        }.get(attr, "")
        assert FormFillerMixin._is_global_search_element(search_input) is True

        form_input = MagicMock()
        form_input.get_attribute.side_effect = lambda attr: {
            "class": "fb-dash-form-element",
            "id": "single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement",
            "placeholder": "Years of experience",
            "aria-label": "How many years of Python experience do you have?",
        }.get(attr, "")
        assert FormFillerMixin._is_global_search_element(form_input) is False
