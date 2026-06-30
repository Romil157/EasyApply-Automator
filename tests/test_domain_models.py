"""Tests for easy_apply_automator.domain.models dataclasses."""

from __future__ import annotations

import pytest

from easy_apply_automator.config.schema import RunConfig
from easy_apply_automator.domain.models import AppConfig, RuntimeConfig, SessionMetrics

# ---------------------------------------------------------------------------
# SessionMetrics
# ---------------------------------------------------------------------------


class TestSessionMetrics:
    def test_default_values(self):
        m = SessionMetrics()
        assert m.jobs_processed == 0
        assert m.jobs_submitted == 0
        assert m.jobs_attempted == 0
        assert m.jobs_failed_attempts == 0
        assert m.jobs_failed_medical == 0

    def test_manual_construction(self):
        m = SessionMetrics(jobs_processed=10, jobs_submitted=5, jobs_attempted=8)
        assert m.jobs_processed == 10
        assert m.jobs_submitted == 5
        assert m.jobs_attempted == 8

    def test_slots_prevent_arbitrary_attributes(self):
        m = SessionMetrics()
        with pytest.raises(AttributeError):
            m.unknown_field = 42  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# RuntimeConfig
# ---------------------------------------------------------------------------


class TestRuntimeConfig:
    def test_all_defaults(self):
        rc = RuntimeConfig()
        assert rc.max_pages_per_search == 3
        assert rc.session_duration_hours_min == 3.0
        assert rc.session_duration_hours_max == 5.0
        assert rc.short_break_min_seconds == 20
        assert rc.short_break_max_seconds == 75
        assert rc.short_break_every_min_minutes == 8
        assert rc.short_break_every_max_minutes == 18
        assert rc.throughput_window_minutes == 30
        assert rc.shuffle_search_combos is False
        assert rc.max_apply_seconds == 20

    def test_custom_values(self):
        rc = RuntimeConfig(max_pages_per_search=10, shuffle_search_combos=True)
        assert rc.max_pages_per_search == 10
        assert rc.shuffle_search_combos is True

    def test_slots_prevent_arbitrary_attributes(self):
        rc = RuntimeConfig()
        with pytest.raises(AttributeError):
            rc.made_up = "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AppConfig defaults
# ---------------------------------------------------------------------------


class TestAppConfigDefaults:
    def test_default_field_values(self):
        cfg = AppConfig()
        assert cfg.username == ""
        assert cfg.password == ""
        assert cfg.phone_number == ""
        assert cfg.salary == ""
        assert cfg.rate == ""
        assert cfg.positions == []
        assert cfg.locations == []
        assert cfg.uploads == {}
        assert cfg.location_country == "IN"
        assert cfg.location_city == "Mumbai"
        assert cfg.linkedin_profile_url == ""
        assert cfg.blacklist == []
        assert cfg.blacklist_titles == []
        assert cfg.experience_level == []
        assert cfg.ans_yaml_path == "questions_answers.yaml"
        assert cfg.results_filename == "results.json"
        assert cfg.events_filename == "logs/events.jsonl"
        assert cfg.cookies_path == ".auth/linkedin_cookies.json"
        assert isinstance(cfg.runtime, RuntimeConfig)

    def test_mutable_defaults_are_independent(self):
        a = AppConfig()
        b = AppConfig()
        a.positions.append("SWE")
        assert b.positions == []

    def test_slots_prevent_arbitrary_attributes(self):
        cfg = AppConfig()
        with pytest.raises(AttributeError):
            cfg.nonexistent = "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AppConfig.from_dict
# ---------------------------------------------------------------------------


class TestAppConfigFromDict:
    def _params(self, **kw):
        base = {"positions": ["SWE"], "locations": ["Remote"]}
        base.update(kw)
        return base

    def test_positions_and_locations_populated(self):
        cfg = AppConfig.from_dict(self._params(), "results/out.json")
        assert "SWE" in cfg.positions
        assert "Remote" in cfg.locations

    def test_blacklist_titles_reads_from_blackListTitles_key(self):
        cfg = AppConfig.from_dict(
            self._params(blackListTitles=["Manager", "Director"]), "results/out.json"
        )
        assert "Manager" in cfg.blacklist_titles

    def test_results_filename_stored(self):
        cfg = AppConfig.from_dict(self._params(), "results/2024-01-01_12-00-00.json")
        assert "2024-01-01" in cfg.results_filename

    def test_shuffle_defaults_to_false(self):
        cfg = AppConfig.from_dict(self._params(), "results/out.json")
        assert cfg.runtime.shuffle_search_combos is False

    def test_shuffle_can_be_enabled(self):
        cfg = AppConfig.from_dict(self._params(shuffle_search_combos=True), "results/out.json")
        assert cfg.runtime.shuffle_search_combos is True

    def test_experience_level_empty_by_default(self):
        cfg = AppConfig.from_dict(self._params(), "results/out.json")
        assert cfg.experience_level == []

    def test_experience_level_remapping_internship(self):
        # YAML value 6 → maps to 1 (Internship)
        cfg = AppConfig.from_dict(self._params(experience_level=[6]), "results/out.json")
        assert cfg.experience_level == [1]

    def test_experience_level_remapping_entry(self):
        # YAML value 1 → maps to 2 (Entry Level)
        cfg = AppConfig.from_dict(self._params(experience_level=[1]), "results/out.json")
        assert cfg.experience_level == [2]

    def test_experience_level_unmapped_values_pass_through(self):
        # Value 5 (Director) is not in the remap dict, so it stays 5
        cfg = AppConfig.from_dict(self._params(experience_level=[5]), "results/out.json")
        assert 5 in cfg.experience_level

    def test_none_values_in_experience_level_filtered(self):
        cfg = AppConfig.from_dict(self._params(experience_level=[1, None, 2]), "results/out.json")
        assert None not in cfg.experience_level


# ---------------------------------------------------------------------------
# RunConfig schema
# ---------------------------------------------------------------------------


class TestRunConfig:
    def test_run_config_holds_parameters_and_filename(self):
        rc = RunConfig(parameters={"a": 1}, results_filename="results/x.json")
        assert rc.parameters == {"a": 1}
        assert rc.results_filename == "results/x.json"

    def test_run_config_is_immutable_via_slots(self):
        rc = RunConfig(parameters={}, results_filename="x")
        with pytest.raises(AttributeError):
            rc.extra = "nope"  # type: ignore[attr-defined]
