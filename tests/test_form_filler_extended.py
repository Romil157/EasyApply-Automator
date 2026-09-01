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


class TestRequiredCheckboxesAndComboboxRecovery:
    def test_recover_required_checkboxes_checks_unselected(self):
        svc = _make_mock_apply_flow()
        cb = MagicMock()
        cb.is_displayed.return_value = True
        cb.is_selected.return_value = False
        cb.get_attribute.return_value = "terms-agree-checkbox"

        svc.bot.browser.find_elements.return_value = [cb]
        svc.bot._safe_click.return_value = True

        recovered = svc.recover_required_checkboxes()
        assert recovered == 1
        svc.bot._safe_click.assert_called()

    def test_recover_unselected_comboboxes_fills_empty_input(self):
        svc = _make_mock_apply_flow()
        box = MagicMock()
        box.is_displayed.return_value = True
        box.tag_name = "input"
        box.get_attribute.side_effect = lambda attr: "" if attr == "value" else "city-input"

        svc.bot.browser.find_elements.return_value = [box]
        svc.bot._clean_question_text.return_value = "City"
        svc.bot._derive_direct_answer.return_value = "Mumbai"
        svc.bot._normalize_text_answer.return_value = "Mumbai"
        svc.bot._fill_typeahead_input.return_value = True

        recovered = svc.recover_unselected_comboboxes()
        assert recovered == 1
        svc.bot._fill_typeahead_input.assert_called_with(box, "Mumbai")

