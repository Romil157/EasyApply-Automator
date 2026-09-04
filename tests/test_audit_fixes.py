"""Unit tests verifying audit fixes: logger auto-init, file upload discovery, event durability, and regex seniority filtering."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from easy_apply_automator.app.search_loop import SearchLoopMixin
from easy_apply_automator.observability.events import EventLogger
from easy_apply_automator.observability.logger import log, setup_logger
from easy_apply_automator.services._submit_flow import SubmitFlowMixin


class TestLoggerAutoInit:
    def test_logger_has_handlers(self):
        assert len(log.handlers) >= 2
        # Verify setup_logger is idempotent
        returned = setup_logger()
        assert returned is log


class TestFindFileInputHiddenElement:
    def test_find_file_input_ignores_hidden_status(self):
        mixin = SubmitFlowMixin()
        bot = MagicMock()
        browser = MagicMock()

        # Mock hidden file input element (is_displayed is False, is_enabled is True)
        hidden_file_input = MagicMock()
        hidden_file_input.is_displayed.return_value = False
        hidden_file_input.is_enabled.return_value = True

        browser.find_elements.return_value = [hidden_file_input]
        bot.browser = browser
        mixin.bot = bot

        selectors = [("css selector", "input[type='file']")]
        found = mixin._find_file_input(selectors)
        assert found is hidden_file_input


class TestEventLoggerDurability:
    def test_event_logger_writes_and_flushes(self, tmp_path):
        events_file = tmp_path / "events.jsonl"
        logger = EventLogger(str(events_file))

        with patch("os.fsync") as mock_fsync:
            logger.log_event("test_durability_event", status="ok", count=42)
            assert mock_fsync.called

        assert events_file.exists()
        lines = events_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "test_durability_event"
        assert data["status"] == "ok"
        assert data["count"] == 42


class DummySearchSeniority(SearchLoopMixin):
    def __init__(self, title: str, experience_level: list[int]):
        self.browser = MagicMock()
        self.browser.title = title
        self.experience_level = experience_level


class TestExperienceLevelRegexBoundaries:
    def test_blocks_senior_with_trailing_punctuation(self):
        # "lead" followed by pipe or dash or end-of-string
        bot1 = DummySearchSeniority("Software Engineer - Lead | TechCorp | LinkedIn", [1, 2])
        assert bot1._matches_selected_experience_level() is False

        bot2 = DummySearchSeniority("Team Lead | TechCorp | LinkedIn", [1, 2])
        assert bot2._matches_selected_experience_level() is False

        bot3 = DummySearchSeniority("Senior Architect | TechCorp | LinkedIn", [1, 2])
        assert bot3._matches_selected_experience_level() is False

        bot4 = DummySearchSeniority("VP, Engineering | TechCorp | LinkedIn", [1, 2])
        assert bot4._matches_selected_experience_level() is False

    def test_allows_entry_level_and_internship(self):
        bot = DummySearchSeniority("Junior Python Developer | TechCorp | LinkedIn", [1, 2])
        assert bot._matches_selected_experience_level() is True

        bot2 = DummySearchSeniority("Software Engineering Intern | TechCorp | LinkedIn", [1])
        assert bot2._matches_selected_experience_level() is True
