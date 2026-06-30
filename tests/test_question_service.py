"""Tests for QuestionService — pure logic methods with no real browser."""

from __future__ import annotations

from unittest.mock import MagicMock

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
        # Crypto fallback
        assert svc.coerce_numeric_answer("blockchain experience", "") == "8"
        # Software engineering fallback
        assert svc.coerce_numeric_answer("software engineering years", "") == "12"
        # Default fallback
        assert svc.coerce_numeric_answer("unrelated prompt", "") == "1"


class TestCleanQuestionText:
    def test_basic_cleaning(self):
        assert QuestionService.clean_question_text("  Are you authorized?  ") == "Are you authorized?"
        assert QuestionService.clean_question_text("Please enter a valid answer Are you authorized?") == "Are you authorized?"

    def test_duplicate_substring_removal(self):
        # repeating substrings of exactly 12+ chars get deduped
        repeated = "abcde12345fghabcde12345fgh"
        cleaned = QuestionService.clean_question_text(repeated)
        assert cleaned == "abcde12345fgh"


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
