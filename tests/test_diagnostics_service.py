"""Unit tests for DiagnosticsService metadata extraction and parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

from easy_apply_automator.services.diagnostics_service import DiagnosticsService


def _make_diagnostics_service(
    page_source: str = "",
    title: str = "",
    current_url: str = "https://www.linkedin.com/jobs/view/1234567890/",
    medical_keywords: list[str] | None = None,
) -> DiagnosticsService:
    bot = MagicMock()
    browser = MagicMock()
    browser.page_source = page_source
    browser.title = title
    browser.current_url = current_url
    bot.browser = browser
    bot.medical_related_keywords = medical_keywords or ["medical", "pharma"]
    bot._get_easy_apply_progress.return_value = None

    svc = DiagnosticsService.__new__(DiagnosticsService)
    svc.bot = bot
    return svc


class TestExtractJobMetadata:
    def test_multi_pipe_title_parsing(self):
        title = "Business Analyst Intern | SQL | Excel | Power BI | Analytics | Wake Up Whistle | LinkedIn"
        svc = _make_diagnostics_service(title=title)
        meta = svc.extract_job_metadata()
        assert meta["job_id"] == "1234567890"
        assert meta["company"] == "Wake Up Whistle"
        assert meta["job_title"] == "Business Analyst Intern | SQL | Excel | Power BI | Analytics"

    def test_standard_title_parsing(self):
        title = "Software Engineer Intern | SkillsCapital | LinkedIn"
        svc = _make_diagnostics_service(title=title)
        meta = svc.extract_job_metadata()
        assert meta["company"] == "SkillsCapital"
        assert meta["job_title"] == "Software Engineer Intern"

    def test_dom_selectors_override_fallback(self):
        html = """
        <html>
            <body>
                <h1 class="top-card-layout__title">AI Engineer Intern</h1>
                <a class="topcard__org-name-link" href="#">OpenAI</a>
                <span class="topcard__flavor--bullet">Remote</span>
            </body>
        </html>
        """
        svc = _make_diagnostics_service(page_source=html, title="Generic Title | LinkedIn")
        meta = svc.extract_job_metadata()
        assert meta["job_title"] == "AI Engineer Intern"
        assert meta["company"] == "OpenAI"
        assert meta["location"] == "Remote"
