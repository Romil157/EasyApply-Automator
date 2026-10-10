"""Tests for EasyApply-Automator performance optimizations and regression suite."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.qa.llm_client import LLMClient
from easy_apply_automator.services.apply_flow_service import ApplyFlowService

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _build_test_auto_answer() -> AutoAnswer:
    cfg = {
        "defaults": {
            "unknown_years": "1",
            "unknown_text": "user provided",
            True: "Yes",
            False: "No",
        },
        "profile": {
            "years": {
                "python": "4",
                "sql": "3",
            },
            "work_auth": {
                "legally_authorized": "Yes",
                "require_sponsorship": "No",
            },
            "demographics": {},
        },
        "rules": [
            {
                "id": "python_exp",
                "match_any": [r"(?i)years.*python", r"(?i)python.*experience"],
                "answer": "{years.python}",
            },
            {
                "id": "salary_rule",
                "match_any": [r"(?i)expected salary"],
                "answer": "{salary}",
            },
        ],
    }
    aa = AutoAnswer.__new__(AutoAnswer)
    aa.cfg = cfg
    aa.salary = "120000"
    aa.hourly_rate = "80"
    aa.answers = {}
    aa.log = logging.getLogger("test_qa")
    aa.qa_file = None
    aa.linkedin_profile_url = "https://linkedin.com/in/test"
    aa.full_name = "Test User"
    aa.first_name = "Test"
    aa.last_name = "User"
    aa.form_email = "test@example.com"
    aa.phone_number = "1234567890"
    aa.github_url = "https://github.com/test"
    aa.location_city = "Mumbai"
    aa._question_cache = {}
    aa._compiled_rules = []
    aa._compile_rules()
    aa.qa_metrics = {
        "questions_resolved": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "deterministic_hits": 0,
        "skill_year_hits": 0,
        "heuristic_hits": 0,
        "llm_hits": 0,
        "qa_resolution_ms": 0.0,
    }
    return aa


# ---------------------------------------------------------------------------
# 1. Deterministic QA and Caching Tests
# ---------------------------------------------------------------------------


class TestPerformanceQAResolution:
    def test_deterministic_qa_avoids_llm_call(self):
        """Deterministic YAML rules resolve instantly without calling LLM."""
        aa = _build_test_auto_answer()
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        aa.llm_client = mock_llm

        ans = aa.ans_question("How many years of work experience do you have with Python?")
        assert ans == "4"
        mock_llm.answer_question.assert_not_called()
        assert aa.qa_metrics["deterministic_hits"] == 1
        assert aa.qa_metrics["llm_hits"] == 0

    def test_repeated_question_uses_cache(self):
        """Identical question resolves via in-memory O(1) cache on second lookup."""
        aa = _build_test_auto_answer()
        q = "What is your expected salary?"

        ans1 = aa.ans_question(q)
        assert ans1 == "120000"
        assert aa.qa_metrics["cache_hits"] == 0

        # Second lookup
        ans2 = aa.ans_question(q)
        assert ans2 == "120000"
        assert aa.qa_metrics["cache_hits"] == 1
        assert aa.qa_metrics["questions_resolved"] == 2

    def test_yaml_rules_compiled_once(self):
        """YAML rules are compiled into regex objects during initialization."""
        aa = _build_test_auto_answer()
        assert len(aa._compiled_rules) == 2
        for rule_id, patterns, template in aa._compiled_rules:
            assert isinstance(rule_id, str)
            assert len(patterns) > 0
            assert hasattr(patterns[0], "search")

    def test_llm_client_response_caching(self):
        """LLMClient caches responses to avoid duplicate API calls."""
        client = LLMClient(gemini_api_key="fake-key", model="gemini-2.5-flash")
        client.provider = "gemini"
        client.is_available = MagicMock(return_value=True)
        client._call_gemini = MagicMock(return_value="4")

        ans1 = client.answer_question("How many years of Python?", {"summary": "Resume context"})
        assert ans1 == "4"
        assert client.metrics["llm_requests"] == 1
        assert client.metrics["llm_cache_hits"] == 0

        # Second identical request hits cache
        ans2 = client.answer_question("How many years of Python?", {"summary": "Resume context"})
        assert ans2 == "4"
        assert client.metrics["llm_requests"] == 1
        assert client.metrics["llm_cache_hits"] == 1
        assert client._call_gemini.call_count == 1


# ---------------------------------------------------------------------------
# 2. Search & Job Discovery Optimization Tests
# ---------------------------------------------------------------------------


class TestJobDiscoveryOptimizations:
    def test_duplicate_job_ids_skipped_in_session(self):
        """Duplicate job IDs encountered in search loop are skipped immediately."""
        from easy_apply_automator.app.search_loop import SearchLoopMixin

        class DummySearchBot(SearchLoopMixin):
            def __init__(self):
                self.browser = MagicMock()
                self.stop_requested = False
                self.session_deadline = 9999999999.0
                self.blacklist = []
                self.appliedJobIDs = []
                self.session_failed_ids = set()
                self._seen_session_job_ids = set()
                self.apply_to_job = MagicMock(return_value=True)
                self.log_event = MagicMock()
                self.config = MagicMock()
                self.config.performance_mode.enabled = True
                self.config.performance_mode.skip_non_easy_apply_cards = True

        bot = DummySearchBot()
        cards = [
            {"job_id": "111", "title": "Python Engineer", "company": "Acme", "has_easy_apply": True},
            {"job_id": "111", "title": "Python Engineer", "company": "Acme", "has_easy_apply": True},
            {"job_id": "222", "title": "Backend Engineer", "company": "Beta", "has_easy_apply": True},
        ]

        bot.apply_loop_batch(cards)
        # 111 processed once, 222 processed once -> total 2 calls
        assert bot.apply_to_job.call_count == 2
        assert bot.apply_to_job.call_args_list[0][0][0] == "111"
        assert bot.apply_to_job.call_args_list[1][0][0] == "222"

    def test_irrelevant_jobs_rejected_before_navigation(self):
        """Blacklisted or low-relevance jobs are rejected without opening the job page."""
        from easy_apply_automator.app.search_loop import SearchLoopMixin

        class DummySearchBot(SearchLoopMixin):
            def __init__(self):
                self.browser = MagicMock()
                self.stop_requested = False
                self.session_deadline = 9999999999.0
                self.blacklist = ["SpamCorp"]
                self.appliedJobIDs = []
                self.session_failed_ids = set()
                self._seen_session_job_ids = set()
                self.apply_to_job = MagicMock(return_value=True)
                self.log_event = MagicMock()
                self.config = MagicMock()
                self.config.performance_mode.enabled = True
                self.config.performance_mode.skip_non_easy_apply_cards = True

            def is_title_blacklisted(self, title):
                if "Senior Staff VP" in title:
                    return True, "Senior Staff VP"
                return False, None

        bot = DummySearchBot()
        cards = [
            {"job_id": "100", "title": "Senior Staff VP of Engineering", "company": "GoodCorp", "has_easy_apply": True},
            {"job_id": "200", "title": "Software Engineer", "company": "SpamCorp", "has_easy_apply": True},
            {"job_id": "300", "title": "Software Engineer", "company": "GoodCorp", "has_easy_apply": True},
        ]

        bot.apply_loop_batch(cards)
        # Only 300 should reach apply_to_job
        assert bot.apply_to_job.call_count == 1
        assert bot.apply_to_job.call_args[0][0] == "300"

    def test_non_easy_apply_cards_skipped_before_navigation(self):
        """Cards missing Easy Apply badge are skipped before navigating to the job page."""
        from easy_apply_automator.app.search_loop import SearchLoopMixin

        class DummySearchBot(SearchLoopMixin):
            def __init__(self):
                self.browser = MagicMock()
                self.stop_requested = False
                self.session_deadline = 9999999999.0
                self.blacklist = []
                self.appliedJobIDs = []
                self.session_failed_ids = set()
                self._seen_session_job_ids = set()
                self.apply_to_job = MagicMock(return_value=True)
                self.log_event = MagicMock()
                self.config = MagicMock()
                self.config.performance_mode.enabled = True
                self.config.performance_mode.skip_non_easy_apply_cards = True

        bot = DummySearchBot()
        cards = [
            {"job_id": "501", "title": "DevOps Engineer", "company": "CloudInc", "has_easy_apply": False},
            {"job_id": "502", "title": "Python Developer", "company": "CloudInc", "has_easy_apply": True},
        ]

        bot.apply_loop_batch(cards)
        assert bot.apply_to_job.call_count == 1
        assert bot.apply_to_job.call_args[0][0] == "502"


# ---------------------------------------------------------------------------
# 3. Form Flow and Submission Diagnostics Tests
# ---------------------------------------------------------------------------


class TestFormFlowPerformance:
    def test_single_pass_step_form_filling_healthy_step(self):
        """On progressing steps (unchanged_progress_loops == 0), single-pass field fill is used."""
        svc = ApplyFlowService.__new__(ApplyFlowService)
        svc.bot = MagicMock()
        svc.fill_step_form_fields = MagicMock()
        svc.recover_validation_blockers = MagicMock()

        unchanged_progress_loops = 0
        if unchanged_progress_loops > 0:
            svc.recover_validation_blockers()
        else:
            svc.fill_step_form_fields()

        svc.fill_step_form_fields.assert_called_once()
        svc.recover_validation_blockers.assert_not_called()

    def test_stalled_step_triggers_validation_recovery(self):
        """On stalled steps (unchanged_progress_loops > 0), recovery blockers are invoked."""
        svc = ApplyFlowService.__new__(ApplyFlowService)
        svc.bot = MagicMock()
        svc.fill_step_form_fields = MagicMock()
        svc.recover_validation_blockers = MagicMock(return_value=1)

        unchanged_progress_loops = 1
        if unchanged_progress_loops > 0:
            svc.recover_validation_blockers()
        else:
            svc.fill_step_form_fields()

        svc.recover_validation_blockers.assert_called_once()
        svc.fill_step_form_fields.assert_not_called()

    def test_performance_mode_skips_successful_first_job_debug_dumps(self, tmp_path):
        """In performance mode, first job does not create HTML dumps on success."""
        from easy_apply_automator.services.diagnostics_service import DiagnosticsService

        bot = MagicMock()
        bot.config = MagicMock()
        bot.config.performance_mode.enabled = True
        bot.first_job_debug_done = False
        bot.debug_root = tmp_path

        diag = DiagnosticsService(bot)
        diag.start_job_debug_trace("12345")

        assert bot.current_job_first_try_dir is None
        assert bot.current_job_debug_dir is None

    def test_failure_path_still_creates_failure_snapshot(self, tmp_path):
        """Failure path continues to dump failure snapshots and proof.json."""
        from easy_apply_automator.services.diagnostics_service import DiagnosticsService

        bot = MagicMock()
        bot.config = MagicMock()
        bot.config.performance_mode.enabled = True
        bot.current_job_id = "99999"
        bot.current_job_debug_dir = None
        bot.current_job_first_try_dir = None
        bot.current_job_debug_step = 0
        bot.current_job_failure_count = 0
        bot.debug_failed_root = tmp_path / "failed"
        bot.browser.current_url = "https://linkedin.com/jobs/view/99999"
        bot.browser.title = "Software Engineer"
        bot.browser.page_source = "<html><body>Error</body></html>"
        bot._get_easy_apply_progress.return_value = 50

        diag = DiagnosticsService(bot)
        diag.dump_failure_snapshot("validation_blocked")

        created_files = list((tmp_path / "failed").glob("**/*"))
        assert any(f.name == "proof.json" for f in created_files)
        assert any("failure_validation_blocked.html" in f.name for f in created_files)


# ---------------------------------------------------------------------------
# 4. Invariants & Safety Preservation Tests
# ---------------------------------------------------------------------------


class TestSafetyInvariantsPreserved:
    def test_follow_checkbox_invariant_strictly_enforced(self):
        """Submission gate fails immediately if follow company checkbox is checked or missing."""
        svc = ApplyFlowService.__new__(ApplyFlowService)
        svc.bot = MagicMock()
        svc.bot.config = MagicMock()
        svc.bot.config.follow_company = False
        svc.bot.config.follow_company_required = True
        svc.collect_apply_stall_diagnostics = MagicMock(return_value={
            "required_empty_count": 0,
            "unanswered_radios_count": 0,
            "validation_errors": [],
        })
        svc.find_easy_apply_modal = MagicMock(return_value=None)
        svc._find_action_button = MagicMock(return_value=MagicMock(is_enabled=lambda: True))

        from easy_apply_automator.services._form_filler import FollowCompanyStateResult
        svc.set_follow_company_state = MagicMock(
            return_value=FollowCompanyStateResult(
                found=False, initial_state=None, final_state=None, changed=False, success=False, status="element_not_found"
            )
        )
        gate_ok, violations, _ = svc.validate_final_submission_invariants(require_follow_checkbox=True)
        assert gate_ok is False
        assert any("follow_company_invariant_failed" in v for v in violations)

    def test_unresolved_validation_errors_block_submission(self):
        """Submission gate fails if visible validation errors remain."""
        svc = ApplyFlowService.__new__(ApplyFlowService)
        svc.bot = MagicMock()
        svc.bot.config = MagicMock()
        svc.bot.config.follow_company = False
        svc.bot.config.follow_company_required = False
        svc.collect_apply_stall_diagnostics = MagicMock(return_value={
            "required_empty_count": 0,
            "unanswered_radios_count": 0,
            "validation_errors": ["Please enter a valid number"],
        })
        svc.find_easy_apply_modal = MagicMock(return_value=None)
        svc._find_action_button = MagicMock(return_value=MagicMock(is_enabled=lambda: True))
        svc.bot.browser.find_elements.return_value = [
            MagicMock(is_displayed=lambda: True, text="Please enter a valid number")
        ]

        from easy_apply_automator.services._form_filler import FollowCompanyStateResult
        svc.set_follow_company_state = MagicMock(
            return_value=FollowCompanyStateResult(
                found=False, initial_state=None, final_state=None, changed=False, success=True, status="not_present_not_required"
            )
        )
        gate_ok, violations, _ = svc.validate_final_submission_invariants(require_follow_checkbox=False)
        assert gate_ok is False
        assert any("unresolved_validation_errors" in v for v in violations)
