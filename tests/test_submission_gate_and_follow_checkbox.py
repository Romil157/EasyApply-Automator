"""Regression tests for follow company idempotent state-setting and centralized submission gate.

Verifies:
1. Selected checkbox becomes unchecked.
2. Already unchecked checkbox remains unchecked.
3. Normalization is strictly idempotent across multiple calls.
4. DOM retry mechanism on failed initial action.
5. Missing checkbox blocks submission when required.
6. Unverifiable final state blocks submission.
7. Unrelated checkboxes are ignored and never modified.
8. Exact regression case from the TIC screenshot.
9. Submission gate blocks on validation errors.
10. Submission gate passes when all invariants are satisfied.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from selenium.webdriver.common.by import By

from easy_apply_automator.services.apply_flow_service import ApplyFlowService


def _create_mock_element(
    tag_name: str = "div",
    text: str = "",
    attrs: dict[str, str] | None = None,
    children: list[MagicMock] | None = None,
    selected: bool = False,
    displayed: bool = True,
    enabled: bool = True,
) -> MagicMock:
    el = MagicMock()
    el.tag_name = tag_name
    el.text = text
    el.is_selected.return_value = selected
    el.is_displayed.return_value = displayed
    el.is_enabled.return_value = enabled

    attributes = attrs or {}

    def get_attr(name: str):
        return attributes.get(name)

    el.get_attribute.side_effect = get_attr

    def find_sub(by, query):
        results = []
        if children:
            for c in children:
                c_tag = getattr(c, "tag_name", "").lower()
                c_attrs = getattr(c, "_attrs", {})
                if by == By.TAG_NAME and query.lower() == c_tag:
                    results.append(c)
                elif by == By.CSS_SELECTOR:
                    if query == "label" and c_tag == "label":
                        results.append(c)
                    elif query == "input" and c_tag == "input":
                        results.append(c)
                    elif "input[type='checkbox']" in query and c_tag == "input" and c_attrs.get("type") == "checkbox":
                        results.append(c)
        return results

    el.find_elements.side_effect = find_sub
    el._attrs = attributes
    return el


def _build_test_service(page_elements: list[MagicMock], modal: MagicMock | None = None) -> ApplyFlowService:
    bot = MagicMock()
    browser = MagicMock()
    bot.browser = browser
    bot.locator = {
        "follow": (By.CSS_SELECTOR, "div[role='checkbox'][aria-label*='Follow ' i]"),
        "submit": (By.CSS_SELECTOR, "button[aria-label='Submit application']"),
    }
    bot.config = MagicMock()
    bot.config.follow_company = False
    bot.config.follow_company_required = True

    def browser_find(by, query):
        if by == By.CSS_SELECTOR:
            if "role='checkbox'" in query:
                return [e for e in page_elements if getattr(e, "_attrs", {}).get("role") == "checkbox"]
            if "artdeco-inline-feedback" in query:
                return [e for e in page_elements if "artdeco-inline-feedback" in getattr(e, "_attrs", {}).get("class", "")]
        return []

    browser.find_elements.side_effect = browser_find

    svc = ApplyFlowService.__new__(ApplyFlowService)
    svc.bot = bot
    svc.find_easy_apply_modal = MagicMock(return_value=modal)
    svc.collect_apply_stall_diagnostics = MagicMock(return_value={
        "required_empty_count": 0,
        "unanswered_radios_count": 0,
        "validation_errors": [],
    })
    return svc


class TestFollowCompanyCheckboxState:
    def test_selected_checkbox_becomes_unchecked(self):
        """Selected checkbox -> becomes unchecked."""
        attrs = {
            "role": "checkbox",
            "aria-checked": "true",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        custom_cb = _create_mock_element("div", attrs=attrs)
        svc = _build_test_service([custom_cb])

        def on_click(el):
            attrs["aria-checked"] = "false"
            return True

        svc.bot._safe_click.side_effect = on_click

        res = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res.success is True
        assert res.changed is True
        assert res.final_state is False
        assert svc.bot._safe_click.call_count == 1

    def test_already_unchecked_remains_unchecked(self):
        """Already unchecked -> remains unchecked (idempotent, no click performed)."""
        attrs = {
            "role": "checkbox",
            "aria-checked": "false",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        custom_cb = _create_mock_element("div", attrs=attrs)
        svc = _build_test_service([custom_cb])

        res = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res.success is True
        assert res.changed is False
        assert res.final_state is False
        assert svc.bot._safe_click.call_count == 0

    def test_normalization_is_idempotent(self):
        """Normalization is idempotent across sequential calls without re-toggling."""
        attrs = {
            "role": "checkbox",
            "aria-checked": "true",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        custom_cb = _create_mock_element("div", attrs=attrs)
        svc = _build_test_service([custom_cb])

        def on_click(el):
            attrs["aria-checked"] = "false"
            return True

        svc.bot._safe_click.side_effect = on_click

        res1 = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res1.success is True
        assert res1.changed is True
        assert res1.final_state is False

        # Second call must be idempotent
        res2 = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res2.success is True
        assert res2.changed is False
        assert res2.final_state is False

        # Third call must remain unchanged
        res3 = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res3.success is True
        assert res3.changed is False
        assert res3.final_state is False

        assert svc.bot._safe_click.call_count == 1

    def test_dom_changes_retry_works(self):
        """DOM retry succeeds when first action fails to change state."""
        attrs = {
            "role": "checkbox",
            "aria-checked": "true",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        label = _create_mock_element("label", attrs={"for": "cb_1"})
        custom_cb = _create_mock_element("div", attrs=attrs, children=[label])
        svc = _build_test_service([custom_cb])

        call_count = 0

        def on_click(el):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                attrs["aria-checked"] = "false"
            return True

        svc.bot._safe_click.side_effect = on_click

        res = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res.success is True
        assert res.final_state is False
        assert res.status == "transitioned_to_desired_state_after_retry"
        assert svc.bot._safe_click.call_count == 2

    def test_missing_checkbox_blocks_submission_when_required(self):
        """Missing checkbox -> submission is blocked when required."""
        svc = _build_test_service([])  # Empty page
        res = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res.success is False
        assert res.found is False
        assert res.status == "element_not_found"

        gate_ok, violations, _ = svc.validate_final_submission_invariants(require_follow_checkbox=True)
        assert gate_ok is False
        assert any("follow_company_invariant_failed" in v for v in violations)

    def test_final_state_cannot_be_verified_blocks_submission(self):
        """Final state cannot be verified -> submission is blocked."""
        attrs = {
            "role": "checkbox",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        custom_cb = _create_mock_element("div", attrs=attrs)
        svc = _build_test_service([custom_cb])

        res = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res.success is False
        assert res.status == "initial_state_unknown"

        gate_ok, violations, _ = svc.validate_final_submission_invariants(require_follow_checkbox=True)
        assert gate_ok is False
        assert any("follow_company_invariant_failed" in v for v in violations)

    def test_unrelated_checkboxes_are_not_modified(self):
        """Unrelated checkboxes (terms, job alerts, switches) are strictly ignored."""
        job_alert_switch = _create_mock_element(
            "div",
            attrs={
                "role": "switch",
                "aria-checked": "true",
                "aria-label": "Set alert for similar jobs as Software Engineer",
            },
        )
        terms_cb = _create_mock_element(
            "input",
            attrs={"type": "checkbox", "id": "agree-to-terms"},
            selected=True,
        )
        svc = _build_test_service([job_alert_switch, terms_cb])

        controls = svc.find_follow_company_controls()
        assert controls is None

    def test_exact_regression_case_from_tic_screenshot(self):
        """Exact regression case from supplied TIC screenshot:

        Follow The Information Company (TIC) to stay up to date with their page
        """
        tic_attrs = {
            "role": "checkbox",
            "aria-checked": "true",
            "aria-label": "Follow The Information Company (TIC) to stay up to date with their page",
            "componentkey": "d3c1aeaf-0aee-432a-a4f3-68dd7dee2007",
            "tabindex": "0",
        }
        inner_input = _create_mock_element("input", attrs={"type": "checkbox", "id": "_r_10_"}, selected=True)
        inner_label = _create_mock_element("label", attrs={"for": "_r_10_"})
        text_p = _create_mock_element(
            "p",
            text="Follow The Information Company (TIC) to stay up to date with their page",
        )

        tic_cb = _create_mock_element(
            "div",
            attrs=tic_attrs,
            children=[inner_input, inner_label, text_p],
        )

        svc = _build_test_service([tic_cb])

        def on_click(el):
            tic_attrs["aria-checked"] = "false"
            inner_input.is_selected.return_value = False
            return True

        svc.bot._safe_click.side_effect = on_click

        res = svc.set_follow_company_state(desired_state=False, require_present=True)
        assert res.success is True
        assert res.changed is True
        assert res.final_state is False
        assert tic_attrs["aria-checked"] == "false"


class TestCentralizedSubmissionGate:
    def test_submission_gate_blocks_on_validation_errors(self):
        """Submission gate blocks when active validation error is present."""
        attrs = {
            "role": "checkbox",
            "aria-checked": "false",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        custom_cb = _create_mock_element("div", attrs=attrs)
        err_msg = _create_mock_element(
            "div",
            text="Please select an option",
            attrs={"class": "artdeco-inline-feedback--error"},
            displayed=True,
        )

        svc = _build_test_service([custom_cb, err_msg])
        gate_ok, violations, _ = svc.validate_final_submission_invariants(require_follow_checkbox=True)
        assert gate_ok is False
        assert any("unresolved_validation_errors" in v for v in violations)

    def test_submission_gate_passes_when_all_invariants_satisfied(self):
        """Submission gate passes when all invariants are satisfied."""
        attrs = {
            "role": "checkbox",
            "aria-checked": "false",
            "aria-label": "Follow Acme Corp to stay up to date with their page",
        }
        custom_cb = _create_mock_element("div", attrs=attrs)
        submit_btn = _create_mock_element(
            "button",
            attrs={"aria-label": "Submit application"},
            enabled=True,
            displayed=True,
        )

        svc = _build_test_service([custom_cb])
        svc._find_action_button = MagicMock(return_value=submit_btn)

        gate_ok, violations, _ = svc.validate_final_submission_invariants(require_follow_checkbox=True)
        assert gate_ok is True
        assert len(violations) == 0


class TestQuestionAndRulePersistenceGuards:
    def test_clean_question_text_ignores_character_counters(self):
        from easy_apply_automator.services.question_service import QuestionService
        svc = QuestionService.__new__(QuestionService)
        # Exactly the 2026-10-06 error string
        assert svc.clean_question_text("29 of 100 characters") == ""
        assert svc.clean_question_text("Why are you a good fit? 29 of 100 characters") == "Why are you a good fit?"
        assert svc.clean_question_text("0/500 characters") == ""

    def test_persist_learned_rule_guards_counter_and_files(self):
        from easy_apply_automator.qa.auto_answer import AutoAnswer
        log = MagicMock()
        aa = AutoAnswer(
            qa_file=None,
            ans_yaml_path=None,
            salary="1000",
            hourly_rate="50",
            answers={},
            log=log,
        )
        aa.cfg = {"rules": [{"id": "deterministic_rule", "match_any": ["abc"], "answer": "xyz"}]}

        # Should be rejected
        aa._persist_learned_rule("29 of 100 characters", "some answer")
        assert len(aa.cfg["rules"]) == 1

        aa._persist_learned_rule("resume.pdf", "some answer")
        assert len(aa.cfg["rules"]) == 1

        aa._persist_learned_rule("", "some answer")
        assert len(aa.cfg["rules"]) == 1

        # Should be rejected if ID collision with deterministic rule
        aa._persist_learned_rule("deterministic rule", "new answer")
        assert len(aa.cfg["rules"]) == 1

