"""Unit tests for pre-click filtering, external ATS detection, session summary, and prompt enrichment."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator
from easy_apply_automator.domain.models import AppConfig
from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.qa.llm_client import LLMClient
from easy_apply_automator.services._submit_flow import SubmitFlowMixin


class DummyFlowBot(SubmitFlowMixin):
    """Stub to test SubmitFlowMixin methods in isolation."""

    def __init__(self, current_url: str = ""):
        self.bot = MagicMock()
        self.bot.browser.current_url = current_url
        self.bot.browser.find_elements.return_value = []
        self.bot.current_job_id = "12345"


class TestExternalRedirectDetection:
    """Test external ATS domain identification."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://company.workday.com/en-US/job/apply", True),
            ("https://boards.greenhouse.io/acme/jobs/123", True),
            ("https://jobs.lever.co/techcorp/456", True),
            ("https://jobs.smartrecruiters.com/one/789", True),
            ("https://jobs.ashbyhq.com/startup/apply", True),
            ("https://www.linkedin.com/jobs/view/4458484356/", False),
            ("https://www.linkedin.com/jobs/search/?keywords=python", False),
        ],
    )
    def test_is_external_redirect(self, url: str, expected: bool) -> None:
        flow = DummyFlowBot(current_url=url)
        assert flow._is_external_redirect() is expected


class TestOrchestratorBlacklistMethod:
    """Test is_title_blacklisted method on orchestrator instance."""

    def test_blacklist_matching(self) -> None:
        orchestrator = LinkedInEasyApplyOrchestrator.__new__(LinkedInEasyApplyOrchestrator)
        orchestrator.blacklist_titles = [
            "founder's office",
            "business development",
            "content writer",
            "marketing intern",
        ]
        orchestrator.medical_related_keywords = ["nurse", "physician", "clinical"]

        blocked, keyword = orchestrator.is_title_blacklisted("Founder's Office Intern")
        assert blocked is True
        assert keyword == "founder's office"

        blocked, keyword = orchestrator.is_title_blacklisted("Business Development Executive")
        assert blocked is True
        assert keyword == "business development"

        blocked, keyword = orchestrator.is_title_blacklisted("Staff Nurse - Night Shift")
        assert blocked is True
        assert keyword == "nurse"

        blocked, keyword = orchestrator.is_title_blacklisted("Python Backend Engineer")
        assert blocked is False
        assert keyword is None


class TestAutoAnswerJobContext:
    """Test AutoAnswer set_current_job and context inclusion."""

    def test_set_current_job_populates_context(self) -> None:
        auto_ans = AutoAnswer(
            qa_file=None,
            ans_yaml_path=Path("questions_answers.example.yaml"),
            salary="50000",
            hourly_rate="25",
            answers={},
            log=MagicMock(),
            full_name="Romil Doshi",
        )
        auto_ans.set_current_job("Data Analyst Intern", "TCS")
        context = auto_ans._build_profile_context()

        assert context["current_job_title"] == "Data Analyst Intern"
        assert context["current_job_company"] == "TCS"


class TestLLMClientPromptEnrichment:
    """Test build_prompt includes job target context when provided."""

    def test_prompt_includes_job_target(self) -> None:
        client = LLMClient(provider="groq", groq_api_key="mock_key")
        profile_context = {
            "candidate_name": "Romil Doshi",
            "current_job_title": "Python Developer Intern",
            "current_job_company": "Acme Tech",
        }
        prompt = client.build_prompt("Why do you want this role?", profile_context)

        assert "Python Developer Intern" in prompt
        assert "Acme Tech" in prompt
        assert "Tailor open-ended answers directly to this role" in prompt


class TestDebugSnapshotCleanup:
    """Test _cleanup_old_debug_snapshots prunes oldest directories when exceeding cap."""

    def test_prunes_old_directories(self) -> None:
        orchestrator = LinkedInEasyApplyOrchestrator.__new__(LinkedInEasyApplyOrchestrator)
        with tempfile.TemporaryDirectory() as tmpdir:
            failed_root = Path(tmpdir)
            orchestrator.debug_failed_root = failed_root

            # Create 10 dummy subdirectories
            for i in range(10):
                d = failed_root / f"job_{i:04d}"
                d.mkdir()

            orchestrator._cleanup_old_debug_snapshots(max_keep=4)
            remaining = [d for d in failed_root.iterdir() if d.is_dir()]
            assert len(remaining) == 4
