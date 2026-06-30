"""Tests for easy_apply_automator.config.loader and .schema."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from easy_apply_automator.config.loader import load_run_config
from easy_apply_automator.config.schema import RunConfig
from easy_apply_automator.domain.models import AppConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(content: str, tmp_path: Path, name: str = "config.yaml") -> Path:
    p = tmp_path / name
    p.write_text(dedent(content), encoding="utf-8")
    return p


MINIMAL_VALID_YAML = """
positions:
  - Software Engineer
locations:
  - Remote
"""

FULL_VALID_YAML = """
username: "test@example.com"
password: "secret"
positions:
  - Software Engineer
  - Python Developer
locations:
  - Remote
  - Mumbai
max_pages_per_search: 5
session_duration_hours_min: 2.0
session_duration_hours_max: 4.0
short_break_min_seconds: 10
short_break_max_seconds: 30
experience_level:
  - 1
  - 2
salary: "120000"
rate: "60"
linkedin_profile_url: "https://www.linkedin.com/in/testuser/"
phone_number: "9999999999"
"""


# ---------------------------------------------------------------------------
# Test: RunConfig schema
# ---------------------------------------------------------------------------

class TestRunConfig:
    def test_run_config_dataclass_fields(self):
        rc = RunConfig(parameters={"positions": ["SWE"], "locations": ["Remote"]}, results_filename="results/out.json")
        assert rc.parameters["positions"] == ["SWE"]
        assert rc.results_filename == "results/out.json"

    def test_run_config_is_slots(self):
        rc = RunConfig(parameters={}, results_filename="x.json")
        with pytest.raises(AttributeError):
            rc.nonexistent_field = "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test: load_run_config — valid YAML
# ---------------------------------------------------------------------------

class TestLoadRunConfigValid:
    def test_minimal_config_parses(self, tmp_path):
        p = _write_yaml(MINIMAL_VALID_YAML, tmp_path)
        rc = load_run_config(p)
        assert isinstance(rc, RunConfig)
        assert "positions" in rc.parameters
        assert rc.parameters["positions"] == ["Software Engineer"]

    def test_results_filename_has_timestamp_format(self, tmp_path):
        p = _write_yaml(MINIMAL_VALID_YAML, tmp_path)
        rc = load_run_config(p)
        # Format: results/YYYY-MM-DD_HH-MM-SS.json
        assert rc.results_filename.startswith("results/")
        assert rc.results_filename.endswith(".json")

    def test_full_config_parses_all_fields(self, tmp_path):
        p = _write_yaml(FULL_VALID_YAML, tmp_path)
        rc = load_run_config(p)
        assert rc.parameters["max_pages_per_search"] == 5
        assert rc.parameters["salary"] == "120000"
        assert rc.parameters["linkedin_profile_url"] == "https://www.linkedin.com/in/testuser/"

    def test_env_overrides_yaml_field(self, tmp_path, monkeypatch):
        p = _write_yaml(MINIMAL_VALID_YAML, tmp_path)
        monkeypatch.setenv("LINKEDIN_USERNAME", "env_user@example.com")
        rc = load_run_config(p)
        assert rc.parameters["username"] == "env_user@example.com"

    def test_empty_env_var_does_not_override(self, tmp_path, monkeypatch):
        content = MINIMAL_VALID_YAML + '\nusername: "yaml_user@example.com"\n'
        p = _write_yaml(content, tmp_path)
        monkeypatch.setenv("LINKEDIN_USERNAME", "")
        rc = load_run_config(p)
        assert rc.parameters["username"] == "yaml_user@example.com"

    def test_missing_username_defaults_to_empty(self, tmp_path):
        p = _write_yaml(MINIMAL_VALID_YAML, tmp_path)
        rc = load_run_config(p)
        assert rc.parameters.get("username") == ""

    def test_missing_password_defaults_to_empty(self, tmp_path):
        p = _write_yaml(MINIMAL_VALID_YAML, tmp_path)
        rc = load_run_config(p)
        assert rc.parameters.get("password") == ""


# ---------------------------------------------------------------------------
# Test: load_run_config — missing required fields
# ---------------------------------------------------------------------------

class TestLoadRunConfigMissingFields:
    def test_missing_positions_raises_key_error(self, tmp_path):
        content = "locations:\n  - Remote\n"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(KeyError, match="positions"):
            load_run_config(p)

    def test_missing_locations_raises_key_error(self, tmp_path):
        content = "positions:\n  - Software Engineer\n"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(KeyError, match="locations"):
            load_run_config(p)

    def test_missing_both_raises_key_error(self, tmp_path):
        content = "max_pages_per_search: 3\n"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(KeyError):
            load_run_config(p)

    def test_empty_positions_list_raises_value_error(self, tmp_path):
        content = "positions: []\nlocations:\n  - Remote\n"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(ValueError, match="positions"):
            load_run_config(p)

    def test_empty_locations_list_raises_value_error(self, tmp_path):
        content = "positions:\n  - SWE\nlocations: []\n"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(ValueError, match="locations"):
            load_run_config(p)

    def test_uploads_as_list_raises_value_error(self, tmp_path):
        content = MINIMAL_VALID_YAML + "\nuploads:\n  - Resume: /path/to/resume.pdf\n"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(ValueError, match="uploads"):
            load_run_config(p)


# ---------------------------------------------------------------------------
# Test: load_run_config — malformed YAML
# ---------------------------------------------------------------------------

class TestLoadRunConfigMalformedYaml:
    def test_malformed_yaml_raises_yaml_error(self, tmp_path):
        content = "positions: [\nunot closed"
        p = _write_yaml(content, tmp_path)
        with pytest.raises(yaml.YAMLError):
            load_run_config(p)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_run_config(tmp_path / "does_not_exist.yaml")


# ---------------------------------------------------------------------------
# Test: AppConfig.from_dict
# ---------------------------------------------------------------------------

class TestAppConfigFromDict:
    def _base_params(self, **overrides):
        params = {
            "positions": ["Software Engineer"],
            "locations": ["Remote"],
            "username": "u@example.com",
            "password": "pass",
        }
        params.update(overrides)
        return params

    def test_basic_conversion(self):
        cfg = AppConfig.from_dict(self._base_params(), "results/out.json")
        assert cfg.positions == ["Software Engineer"]
        assert cfg.locations == ["Remote"]
        assert cfg.username == "u@example.com"

    def test_experience_level_remapping(self):
        # Config value 6 → maps to 1 (internship), 1 → maps to 2 (entry), 2 → maps to 3 (associate)
        cfg = AppConfig.from_dict(self._base_params(experience_level=[6, 1, 2]), "results/out.json")
        assert cfg.experience_level == [1, 2, 3]

    def test_runtime_config_defaults(self):
        cfg = AppConfig.from_dict(self._base_params(), "results/out.json")
        assert cfg.runtime.max_pages_per_search == 3
        assert cfg.runtime.session_duration_hours_min == 3.0

    def test_runtime_config_overrides(self):
        cfg = AppConfig.from_dict(
            self._base_params(max_pages_per_search=10, session_duration_hours_min=1.0),
            "results/out.json",
        )
        assert cfg.runtime.max_pages_per_search == 10
        assert cfg.runtime.session_duration_hours_min == 1.0

    def test_none_values_in_positions_filtered(self):
        cfg = AppConfig.from_dict(
            self._base_params(positions=["SWE", None, "Dev"]),
            "results/out.json",
        )
        assert None not in cfg.positions
        assert len(cfg.positions) == 2

    def test_uploads_as_dict_passes_through(self):
        cfg = AppConfig.from_dict(
            self._base_params(uploads={"Resume": "/tmp/cv.pdf"}),
            "results/out.json",
        )
        assert cfg.uploads == {"Resume": "/tmp/cv.pdf"}

    def test_uploads_invalid_type_becomes_empty_dict(self):
        cfg = AppConfig.from_dict(
            self._base_params(uploads="not_a_dict"),
            "results/out.json",
        )
        assert cfg.uploads == {}

    def test_empty_location_country_defaults_to_in(self):
        cfg = AppConfig.from_dict(
            self._base_params(location_country=""),
            "results/out.json",
        )
        assert cfg.location_country == "IN"

    def test_salary_and_rate_coerced_to_str(self):
        cfg = AppConfig.from_dict(
            self._base_params(salary=180000, rate=75),
            "results/out.json",
        )
        assert cfg.salary == "180000"
        assert cfg.rate == "75"
