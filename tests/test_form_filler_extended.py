"""Unit tests for FormFillerMixin country dial-codes, resume auto-selection, and dry-run."""

from __future__ import annotations

from unittest.mock import MagicMock

from easy_apply_automator.services._form_filler import COUNTRY_DIAL_CODES
from easy_apply_automator.services.apply_flow_service import ApplyFlowService


def _make_mock_apply_flow(
    location_country: str = "IN",
    uploads: dict | None = None,
    dry_run: bool = False,
) -> ApplyFlowService:
    bot = MagicMock()
    bot.location_country = location_country
    bot.uploads = uploads or {}
    bot.runtime = MagicMock()
    bot.runtime.dry_run = dry_run
    bot.browser = MagicMock()
    bot.browser.title = "Senior Data Scientist | Python | Machine Learning"
    bot.current_job_id = "998877"

    svc = ApplyFlowService.__new__(ApplyFlowService)
    svc.bot = bot
    return svc


class TestCountryDialCodes:
    def test_country_dial_codes_dictionary(self):
        assert "IN" in COUNTRY_DIAL_CODES
        assert "US" in COUNTRY_DIAL_CODES
        assert "GB" in COUNTRY_DIAL_CODES
        assert "DE" in COUNTRY_DIAL_CODES
        assert "India (+91)" in COUNTRY_DIAL_CODES["IN"]
        assert "United States (+1)" in COUNTRY_DIAL_CODES["US"]


class TestSelectMatchingResume:
    def test_select_matching_resume_by_keyword(self):
        uploads = {
            "Resume": "resumes/general.pdf",
            "data": "resumes/data_science.pdf",
            "python": "resumes/python_developer.pdf",
        }
        svc = _make_mock_apply_flow(uploads=uploads)
        matching = svc._select_matching_resume()
        assert matching == "resumes/data_science.pdf"

    def test_select_default_resume_when_no_title_match(self):
        uploads = {
            "Resume": "resumes/general.pdf",
            "frontend": "resumes/frontend.pdf",
        }
        svc = _make_mock_apply_flow(uploads=uploads)
        svc.bot.browser.title = "Marketing Specialist"
        matching = svc._select_matching_resume()
        assert matching == "resumes/general.pdf"


class TestDryRunSubmitSimulation:
    def test_dry_run_submit_simulation_returns_true_and_dismisses_modal(self):
        svc = _make_mock_apply_flow(dry_run=True)
        svc.dismiss_easy_apply_modal = MagicMock(return_value=True)

        submitted, clicked = svc._handle_submit_action(submit_clicked=False)
        assert submitted is True
        assert clicked is True
        svc.dismiss_easy_apply_modal.assert_called_once()
