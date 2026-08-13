"""Unit tests for ApplyFlowService submit flow, confirmation detection, and locator wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

from selenium.webdriver.common.by import By

from easy_apply_automator.services.apply_flow_service import ApplyFlowService


def _make_submit_flow_service(
    page_source: str = "",
    modal: MagicMock | None = None,
    locator_overrides: dict | None = None,
    clickable_returns: dict | None = None,
) -> ApplyFlowService:
    bot = MagicMock()
    browser = MagicMock()
    browser.page_source = page_source
    browser.current_url = "https://www.linkedin.com/jobs/view/12345/"
    browser.find_elements.return_value = []
    bot.browser = browser

    if locator_overrides is not None:
        bot.locator = locator_overrides
    else:
        bot.locator = {
            "next": (By.CSS_SELECTOR, "button[aria-label='Continue to next step']"),
            "review": (By.CSS_SELECTOR, "button[aria-label='Review your application']"),
            "submit": (By.CSS_SELECTOR, "button[aria-label='Submit application']"),
        }

    click_map = clickable_returns or {}

    def _find_clickable_side_effect(selectors):
        for by, val in selectors:
            if (by, val) in click_map:
                return click_map[(by, val)]
        return None

    bot._find_clickable.side_effect = _find_clickable_side_effect
    bot._safe_click.return_value = True

    svc = ApplyFlowService.__new__(ApplyFlowService)
    svc.bot = bot

    if modal is not None:
        svc.find_easy_apply_modal = MagicMock(return_value=modal)  # type: ignore[assignment]
    else:
        svc.find_easy_apply_modal = MagicMock(return_value=None)  # type: ignore[assignment]

    return svc


class TestIsSubmitConfirmationState:
    def test_detects_standard_confirmation_phrases(self):
        phrases = [
            "Your application was submitted to ACME Corp.",
            "Application sent successfully!",
            "Your application has been sent.",
            "Thanks for applying!",
            "Thank you for applying to this role.",
            "Application received.",
        ]
        for phrase in phrases:
            svc = _make_submit_flow_service(page_source=f"<div>{phrase}</div>")
            assert svc.is_submit_confirmation_state() is True, f"Failed for phrase: {phrase}"

    def test_returns_false_for_regular_form_page(self):
        html = "<div>Contact information step 1 of 3</div>"
        svc = _make_submit_flow_service(page_source=html)
        assert svc.is_submit_confirmation_state() is False

    def test_structural_modal_confirmation_state(self):
        modal = MagicMock()
        modal.get_attribute.return_value = "<div>Your application went to Google</div>"

        svc = _make_submit_flow_service(modal=modal)
        assert svc.is_submit_confirmation_state() is True

    def test_structural_modal_done_button_no_fields(self):
        modal = MagicMock()
        modal.get_attribute.return_value = "<div>Modal Content</div>"

        done_btn = MagicMock()
        done_btn.text = "Done"

        def modal_find_elements(by, value):
            if by == By.TAG_NAME and value == "button":
                return [done_btn]
            return []

        modal.find_elements.side_effect = modal_find_elements

        svc = _make_submit_flow_service(modal=modal)
        assert svc.is_submit_confirmation_state() is True


class TestGetActionSelectorsAndLocatorsWiring:
    def test_get_action_selectors_prioritizes_custom_locator(self):
        custom_submit = (By.CSS_SELECTOR, "button.custom-submit-btn")
        svc = _make_submit_flow_service(
            locator_overrides={"submit": custom_submit}
        )
        selectors = svc._get_action_selectors("submit")
        assert selectors[0] == custom_submit
        assert len(selectors) > 1

    def test_resolve_step_action_uses_custom_locators(self):
        custom_next = (By.XPATH, "//button[@id='custom-next']")
        svc = _make_submit_flow_service(
            locator_overrides={"next": custom_next}
        )
        action, selectors = svc._resolve_step_action("next")
        assert action == "next"
        assert selectors[0] == custom_next

    def test_detect_easy_apply_state_resolves_via_locators(self):
        custom_submit = (By.XPATH, "//button[@id='my-submit']")
        btn_mock = MagicMock()
        svc = _make_submit_flow_service(
            locator_overrides={"submit": custom_submit},
            clickable_returns={custom_submit: btn_mock},
        )
        state, details = svc.detect_easy_apply_state()
        assert state == "submit"


class TestHandleSubmitAction:
    def test_handle_submit_action_success_when_modal_closed(self):
        svc = _make_submit_flow_service(modal=None)
        submitted, clicked = svc._handle_submit_action(submit_clicked=False)
        assert submitted is True
        assert clicked is True

    def test_handle_submit_action_success_when_confirmation_detected(self):
        svc = _make_submit_flow_service(page_source="<div>Your application was sent</div>")
        submitted, clicked = svc._handle_submit_action(submit_clicked=False)
        assert submitted is True
        assert clicked is True
