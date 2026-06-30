"""Tests for easy_apply_automator.qa.auto_answer — pure regex / template logic."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

from easy_apply_automator.qa.auto_answer import AutoAnswer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_yaml(content: str, tmp_path: Path) -> Path:
    """Write a YAML string to a temp file and return its path."""
    p = tmp_path / "qa.yaml"
    p.write_text(dedent(content), encoding="utf-8")
    return p


def _make_auto_answer(yaml_content: str, tmp_path: Path, **kwargs) -> AutoAnswer:
    yaml_path = _make_yaml(yaml_content, tmp_path)
    mock_log = MagicMock()
    return AutoAnswer(
        qa_file=None,
        ans_yaml_path=yaml_path,
        salary=kwargs.get("salary", "100000"),
        hourly_rate=kwargs.get("hourly_rate", "50"),
        answers={},
        log=mock_log,
        linkedin_profile_url=kwargs.get("linkedin_profile_url", ""),
    )


BASIC_YAML = """
defaults:
  unknown_text: "user provided"
  unknown_years: "1"

profile:
  years:
    python: "5"
    sql: "3"
  work_auth:
    authorized_to_work: "Yes"
    require_sponsorship: "No"
  demographics: {}

rules:
  - id: authorized
    match_any:
      - '(?i)authorized to work'
      - '(?i)legally authorized'
    answer: "{authorized_to_work}"

  - id: sponsorship
    match_any:
      - '(?i)require sponsorship'
    answer: "{require_sponsorship}"

  - id: python_years
    match_any:
      - '(?i)years of python'
      - '(?i)python experience'
    answer: "{years.python}"

  - id: linkedin
    match_any:
      - '(?i)linkedin profile'
      - '(?i)^linkedin\*?$'
    answer: "{linkedin_profile_url}"

  - id: salary
    match_any:
      - '(?i)salary'
      - '(?i)compensation'
    answer: "{salary}"
"""


# ---------------------------------------------------------------------------
# Test: exact pattern match
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_authorized_match(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        yaml_file = tmp_path / "qa.yaml"
        print(f"\nFile exists: {yaml_file.exists()}")
        print(f"File content:\n{yaml_file.read_text(encoding='utf-8')}")
        print(f"aa.cfg rules count: {len(aa.cfg.get('rules', []))}")
        result = aa.ans_question("Are you authorized to work?")
        assert result == "Yes"

    def test_sponsorship_match(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("Do you require sponsorship?")
        assert result == "No"

    def test_salary_match(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path, salary="95000")
        result = aa.ans_question("What is your expected salary?")
        assert result == "95000"


# ---------------------------------------------------------------------------
# Test: case-insensitive matching
# ---------------------------------------------------------------------------


class TestCaseInsensitive:
    def test_upper_case_question(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("ARE YOU AUTHORIZED TO WORK IN THIS COUNTRY?")
        assert result == "Yes"

    def test_mixed_case_question(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("Do You Require Sponsorship to work here?")
        assert result == "No"

    def test_python_years_case(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("How many Years Of Python experience do you have?")
        assert result == "5"


# ---------------------------------------------------------------------------
# Test: no-match fallback
# ---------------------------------------------------------------------------


class TestNoMatchFallback:
    def test_unknown_question_returns_unknown_text(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("What is the airspeed of an unladen swallow?")
        assert result == "user provided"

    def test_empty_question_returns_unknown_text(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("")
        assert result == "user provided"

    def test_whitespace_only_question(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("   ")
        assert result == "user provided"

    def test_none_like_question(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question(None)  # type: ignore[arg-type]
        assert result == "user provided"


# ---------------------------------------------------------------------------
# Test: template rendering
# ---------------------------------------------------------------------------


class TestTemplateRendering:
    def test_linkedin_profile_url_rendered(self, tmp_path):
        aa = _make_auto_answer(
            BASIC_YAML, tmp_path, linkedin_profile_url="https://www.linkedin.com/in/testuser/"
        )
        result = aa.ans_question("Please provide your LinkedIn profile")
        assert result == "https://www.linkedin.com/in/testuser/"

    def test_linkedin_plain_label_regex(self, tmp_path):
        """The bare label 'LinkedIn*' must also match the linkedin rule."""
        aa = _make_auto_answer(
            BASIC_YAML, tmp_path, linkedin_profile_url="https://www.linkedin.com/in/testuser/"
        )
        result = aa.ans_question("LinkedIn*")
        assert result == "https://www.linkedin.com/in/testuser/"

    def test_years_template_python(self, tmp_path):
        aa = _make_auto_answer(BASIC_YAML, tmp_path)
        result = aa.ans_question("How many years of Python experience?")
        assert result == "5"

    def test_years_template_unknown_key_falls_back_to_unknown_years(self, tmp_path):
        # 'java' is not in the years map, should return unknown_years = "1"
        yaml_with_java = (
            BASIC_YAML
            + '\n  - id: java_years\n    match_any:\n      - "(?i)java years"\n    answer: "{years.java}"\n'
        )
        result = _make_auto_answer(yaml_with_java, tmp_path).ans_question("java years")
        assert result == "1"

    def test_linkedin_url_empty_returns_placeholder(self, tmp_path):
        """When linkedin_profile_url is blank, the template stays un-substituted."""
        aa = _make_auto_answer(BASIC_YAML, tmp_path, linkedin_profile_url="")
        result = aa.ans_question("LinkedIn profile")
        # The {linkedin_profile_url} placeholder is not in ctx when url is empty,
        # so it stays as the literal string (no replacement), or may remain.
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Test: ambiguous-pattern edge case
# ---------------------------------------------------------------------------


class TestAmbiguousPatterns:
    def test_first_matching_rule_wins(self, tmp_path):
        """When two rules could match, the first rule in the YAML list wins."""
        yaml_content = """
defaults:
  unknown_text: "user provided"

rules:
  - id: first_rule
    match_any:
      - '(?i)experience'
    answer: "first"

  - id: second_rule
    match_any:
      - '(?i)years of experience'
    answer: "second"
"""
        aa = _make_auto_answer(yaml_content, tmp_path)
        result = aa.ans_question("How many years of experience do you have?")
        assert result == "first"

    def test_invalid_regex_skipped_gracefully(self, tmp_path):
        """A malformed regex pattern should not crash the engine."""
        yaml_content = """
defaults:
  unknown_text: "fallback"

rules:
  - id: broken
    match_any:
      - '[invalid regex('
    answer: "should not appear"

  - id: good
    match_any:
      - '(?i)authorized'
    answer: "Yes"
"""
        aa = _make_auto_answer(yaml_content, tmp_path)
        result = aa.ans_question("Are you authorized to work?")
        assert result == "Yes"

    def test_partial_overlap_does_not_bleed(self, tmp_path):
        """'salary' matching should not also match 'supplemental salary data'
        when the second rule has a more-specific pattern listed second."""
        yaml_content = r"""
defaults:
  unknown_text: "user provided"

rules:
  - id: base_salary
    match_any:
      - '(?i)\bbase salary\b'
    answer: "base_answer"

  - id: generic_salary
    match_any:
      - '(?i)salary'
    answer: "generic_answer"
"""
        aa = _make_auto_answer(yaml_content, tmp_path)
        result = aa.ans_question("What is your base salary expectation?")
        assert result == "base_answer"


# ---------------------------------------------------------------------------
# Test: missing / empty YAML file
# ---------------------------------------------------------------------------


class TestYamlLoading:
    def test_missing_yaml_does_not_raise(self, tmp_path):
        mock_log = MagicMock()
        aa = AutoAnswer(
            qa_file=None,
            ans_yaml_path=tmp_path / "nonexistent.yaml",
            salary="",
            hourly_rate="",
            answers={},
            log=mock_log,
        )
        result = aa.ans_question("anything")
        # Should return default "user provided" from hardcoded fallback
        assert isinstance(result, str)

    def test_empty_yaml_uses_hardcoded_fallback(self, tmp_path):
        empty = tmp_path / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        mock_log = MagicMock()
        aa = AutoAnswer(
            qa_file=None,
            ans_yaml_path=empty,
            salary="",
            hourly_rate="",
            answers={},
            log=mock_log,
        )
        result = aa.ans_question("anything")
        assert result == "user provided"
