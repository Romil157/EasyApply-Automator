"""Tests for QuestionService — pure logic methods with no real browser."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.services.question_service import QuestionService


def _make_service() -> QuestionService:
    bot = MagicMock()
    bot.location_city = "Mumbai"
    bot.location_country = "India"
    svc = QuestionService.__new__(QuestionService)
    svc.bot = bot
    return svc


class TestLooksNumericQuestion:
    def test_numeric_markers(self):
        svc = _make_service()
        assert svc.looks_numeric_question("how many years of python experience") is True
        assert svc.looks_numeric_question("years experience do you have") is True
        assert svc.looks_numeric_question("decimal number") is True
        assert svc.looks_numeric_question("unrelated question") is False

    def test_input_id_fallback(self):
        svc = _make_service()
        assert svc.looks_numeric_question("some question", input_id="numeric-input") is True
        assert svc.looks_numeric_question("some question", input_id="normal-text") is False


class TestCoerceNumericAnswer:
    def test_extract_numbers(self):
        svc = _make_service()
        assert svc.coerce_numeric_answer("how many years", "5 years") == "5"
        assert svc.coerce_numeric_answer("how many years", "3.5") == "3.5"
        assert svc.coerce_numeric_answer("how many years", "$100,000") == "100000"

    def test_keyword_fallbacks(self):
        svc = _make_service()
        # Default fallback for unknown numeric questions
        assert svc.coerce_numeric_answer("blockchain experience", "") == "1"
        assert svc.coerce_numeric_answer("software engineering years", "") == "1"
        assert svc.coerce_numeric_answer("unrelated prompt", "") == "1"

    def test_zero_is_preserved(self):
        svc = _make_service()
        assert svc.coerce_numeric_answer("how many years of experience", "0") == "0"
        assert svc.coerce_numeric_answer("how many years of experience", "0.0") == "0.0"
        assert svc.coerce_numeric_answer("how many moving violations", "0") == "0"

    def test_floor_constraint_applied(self):
        svc = _make_service()
        # Strictly larger than 100 floor
        assert svc.coerce_numeric_answer("please enter expected ctc. Enter a whole number larger than 100", "0") == "101"
        assert svc.coerce_numeric_answer("please enter expected ctc. Enter a whole number larger than 100", "Open to discussion") == "101"
        # Already satisfies floor
        assert svc.coerce_numeric_answer("please enter expected ctc. Enter a whole number larger than 100", "300000") == "300000"


class TestCleanQuestionText:
    def test_basic_cleaning(self):
        assert (
            QuestionService.clean_question_text("  Are you authorized?  ") == "Are you authorized?"
        )
        assert (
            QuestionService.clean_question_text("Please enter a valid answer Are you authorized?")
            == "Are you authorized?"
        )

    def test_duplicate_substring_removal(self):
        # repeating substrings of exactly 12+ chars get deduped
        repeated = "abcde12345fghabcde12345fgh"
        cleaned = QuestionService.clean_question_text(repeated)
        assert cleaned == "abcde12345fgh"

    def test_character_counter_noise_removal(self):
        assert (
            QuestionService.clean_question_text("Description 405/2,000 2000 maximum characters allowed.")
            == "Description"
        )
        assert QuestionService.clean_question_text("Description 0/2,000") == "Description"
        assert (
            QuestionService.clean_question_text("Why Clearwater Analytics? 100/1,500 characters")
            == "Why Clearwater Analytics?"
        )


class TestAnswerAliases:
    def test_yes_aliases(self):
        aliases = QuestionService.answer_aliases("yes")
        assert "yes" in aliases
        assert "true" in aliases
        assert "y" in aliases
        assert "1" in aliases

    def test_no_aliases(self):
        aliases = QuestionService.answer_aliases("no")
        assert "no" in aliases
        assert "false" in aliases
        assert "n" in aliases
        assert "0" in aliases

    def test_other_values(self):
        aliases = QuestionService.answer_aliases("maybe")
        assert aliases == {"maybe"}


class TestIsLongFormPrompt:
    def test_input_type_textarea(self):
        svc = _make_service()
        assert svc.is_long_form_prompt("any question", input_type="textarea") is True

    def test_markers(self):
        svc = _make_service()
        assert svc.is_long_form_prompt("why do you want this role", input_type="text") is True
        assert svc.is_long_form_prompt("tell us about a project", input_type="text") is True
        assert svc.is_long_form_prompt("what is your name", input_type="text") is False


class TestDeriveDirectAnswer:
    def test_city_match(self):
        svc = _make_service()
        assert svc.derive_direct_answer("what is your city location") == "Mumbai"
        assert svc.derive_direct_answer("some question", input_id="location-city") == "Mumbai"

    def test_country_match(self):
        svc = _make_service()
        assert svc.derive_direct_answer("what is your phone country code") == "India"
        assert svc.derive_direct_answer("some question", input_id="location-country") == "India"

    def test_no_match(self):
        svc = _make_service()
        assert svc.derive_direct_answer("unrelated question") is None


class TestClampToFieldLimit:
    def test_maxlength_attribute(self):
        el = MagicMock()
        el.get_attribute.side_effect = lambda attr: "20" if attr == "maxlength" else None
        res = QuestionService.clamp_to_field_limit(el, "This is a very long string exceeding twenty chars", "bio")
        assert len(res) <= 20
        assert res == "This is a very long"

    def test_no_truncation_when_within_limit(self):
        el = MagicMock()
        el.get_attribute.side_effect = lambda attr: "50" if attr == "maxlength" else None
        res = QuestionService.clamp_to_field_limit(el, "Short answer", "headline")
        assert res == "Short answer"

    def test_headline_single_line_input_clamping(self):
        el = MagicMock()
        el.get_attribute.return_value = None
        el.tag_name = "input"
        long_headline = "Forward Deployed Engineer Intern with 2 years of full-stack and AI/ML experience, specializing in security-focused applications and data pipelines."
        res = QuestionService.clamp_to_field_limit(el, long_headline, "Headline")
        assert len(res) <= 100
        assert not res.endswith(" ")

    def test_comma_formatted_counter_limit(self):
        el = MagicMock()
        el.get_attribute.return_value = None
        el.tag_name = "textarea"

        parent = MagicMock()
        counter = MagicMock()
        counter.text = "405/2,000"
        parent.find_elements.return_value = [counter]
        el.find_element.return_value = parent

        short_ans = "A" * 300
        res = QuestionService.clamp_to_field_limit(el, short_ans, "Description")
        assert len(res) == 300
        assert res == short_ans

        long_ans = "B" * 2500
        res_clamped = QuestionService.clamp_to_field_limit(el, long_ans, "Description")
        assert len(res_clamped) == 2000

    def test_comma_formatted_maximum_characters_limit(self):
        el = MagicMock()
        el.get_attribute.return_value = None
        el.tag_name = "textarea"

        parent = MagicMock()
        counter = MagicMock()
        counter.text = "2,000 maximum characters allowed."
        parent.find_elements.return_value = [counter]
        el.find_element.return_value = parent

        short_ans = "A" * 300
        res = QuestionService.clamp_to_field_limit(el, short_ans, "Description")
        assert len(res) == 300

        long_ans = "B" * 2500
        res_clamped = QuestionService.clamp_to_field_limit(el, long_ans, "Description")
        assert len(res_clamped) == 2000


class TestYamlRulesResolution:
    def test_salutation_vs_job_title(self, tmp_path):
        import shutil

        yaml_path = Path("questions_answers.yaml")
        if not yaml_path.exists():
            return
        tmp_yaml = tmp_path / "questions_answers.yaml"
        shutil.copyfile(yaml_path, tmp_yaml)

        auto_answer = AutoAnswer(
            qa_file=None,
            ans_yaml_path=tmp_yaml,
            salary="100000",
            hourly_rate="50",
            answers={},
            log=MagicMock(),
        )

        assert auto_answer.ans_question("salutation") == "Mr."
        assert auto_answer.ans_question("prefix") == "Mr."

        # "Your title" or "Job title" must NOT match salutation ("Mr.")
        title_ans = auto_answer.ans_question("your title")
        assert title_ans != "Mr."
        assert "Intern" in title_ans or "Engineer" in title_ans

        # "Description" must match work experience description
        desc_ans = auto_answer.ans_question("description")
        assert "software" in desc_ans.lower() or "projects" in desc_ans.lower()

        # "Company" must NOT match Clearwater Analytics
        comp_ans = auto_answer.ans_question("company")
        assert comp_ans != "Clearwater Analytics"


class TestGetFieldQuestionTextSDUI:
    def test_resolves_question_from_ancestor_paragraph_when_fieldset_text_is_binary_options(self):
        svc = _make_service()
        fieldset = MagicMock()
        fieldset.text = "Yes\nNo"
        fieldset.get_attribute.return_value = ""
        fieldset.find_elements.side_effect = lambda by, sel: (
            [MagicMock(text="Have you completed the following level of education: Bachelor's Degree?*")]
            if "ancestor" in sel or "preceding-sibling" in sel
            else []
        )

        extracted = svc.get_field_question_text(fieldset)
        assert "Bachelor's Degree" in extracted
        assert "Yes" not in extracted

    def test_resolves_question_from_radio_aria_label(self):
        svc = _make_service()
        fieldset = MagicMock()
        fieldset.text = "Yes No"
        fieldset.get_attribute.return_value = ""

        radio_mock = MagicMock()
        radio_mock.get_attribute.side_effect = lambda attr: (
            "Do you have a valid driver's license?" if attr == "aria-label" else ""
        )

        def mock_find_elements(by, sel):
            if "role='radio'" in sel:
                return [radio_mock]
            return []

        fieldset.find_elements.side_effect = mock_find_elements

        extracted = svc.get_field_question_text(fieldset)
        assert "driver's license" in extracted.lower()

    def test_resolves_question_from_legend(self):
        svc = _make_service()
        fieldset = MagicMock()
        fieldset.text = "Yes\nNo"
        fieldset.get_attribute.return_value = ""

        legend_mock = MagicMock()
        legend_mock.text = "Are you legally authorized to work in India?"

        def mock_find_elements(by, sel):
            if by.lower() == "tag name" and sel == "legend":
                return [legend_mock]
            return []

        fieldset.find_elements.side_effect = mock_find_elements
        extracted = svc.get_field_question_text(fieldset)
        assert "legally authorized to work" in extracted.lower()


class TestRadioMatchesAnswerSDUI:
    def test_matches_via_ancestor_role_radio_text(self):
        svc = _make_service()
        field = MagicMock()
        radio = MagicMock()
        radio.get_attribute.return_value = ""

        container = MagicMock()
        container.text = "Yes"
        radio.find_element.return_value = container

        assert svc.radio_matches_answer(field, radio, "Yes") is True
        assert svc.radio_matches_answer(field, radio, "No") is False


class TestSelectRadioElement:
    def test_clicks_role_radio_container_and_verifies_state(self):
        svc = _make_service()
        field = MagicMock()
        radio = MagicMock()
        radio.is_selected.return_value = False

        container = MagicMock()
        container.is_displayed.return_value = True
        container.get_attribute.side_effect = lambda attr: "true" if attr == "aria-checked" else ""
        radio.find_element.return_value = container

        label = MagicMock()
        label.is_displayed.return_value = False
        field.find_element.return_value = label

        success = svc._select_radio_element(field, radio, "radio-123")
        assert success is True
        svc.bot._safe_click.assert_called_with(container)


class TestSkipAlreadyPopulatedInputs:
    def test_skips_phone_input_when_number_already_present(self):
        svc = _make_service()
        field = MagicMock()
        field.text = "Mobile phone number"
        field.find_elements.return_value = []

        phone_input = MagicMock()
        phone_input.is_displayed.return_value = True
        phone_input.is_enabled.return_value = True
        phone_input.get_attribute.side_effect = lambda attr: (
            "single-line-phoneNumber-nationalNumber" if attr == "id" else "9876543210" if attr == "value" else ""
        )
        field.find_element.return_value = phone_input

        svc.bot.browser.find_elements.return_value = [field]
        svc.process_questions()

        phone_input.clear.assert_not_called()
        phone_input.send_keys.assert_not_called()

    def test_skips_text_input_when_matching_value_already_present(self):
        svc = _make_service()
        field = MagicMock()
        field.text = "How many years of Python experience do you have?"
        field.find_elements.return_value = []

        text_input = MagicMock()
        text_input.is_displayed.return_value = True
        text_input.is_enabled.return_value = True
        text_input.get_attribute.side_effect = lambda attr: (
            "python-years" if attr == "id" else "3" if attr == "value" else ""
        )
        field.find_element.return_value = text_input

        svc.ans_question = MagicMock(return_value="3")
        svc.bot.browser.find_elements.return_value = [field]
        svc.process_questions()

        text_input.clear.assert_not_called()
        text_input.send_keys.assert_not_called()





