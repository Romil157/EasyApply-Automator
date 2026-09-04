"""Unit tests for build_cli_parser and CLI runner options."""

from __future__ import annotations

from easy_apply_automator.app.runner import build_cli_parser


class TestCliParser:
    def test_default_cli_parser(self):
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.config == "config.yaml"
        assert args.dry_run is False
        assert args.headless is False
        assert args.level is None
        assert args.max_apps is None

    def test_cli_flags_parsing(self):
        parser = build_cli_parser()
        args = parser.parse_args(
            [
                "--dry-run",
                "--headless",
                "--level",
                "1",
                "--date-posted",
                "past_24h",
                "--max-apps",
                "25",
                "--remote-only",
                "--config",
                "custom_config.yaml",
                "--proxy",
                "http://proxy.local:8080",
                "--user-data-dir",
                "/tmp/chrome-profile",
            ]
        )
        assert args.dry_run is True
        assert args.headless is True
        assert args.level == "1"
        assert args.date_posted == "past_24h"
        assert args.max_apps == 25
        assert args.remote_only is True
        assert args.config == "custom_config.yaml"
        assert args.proxy == "http://proxy.local:8080"
        assert args.user_data_dir == "/tmp/chrome-profile"

    def test_cli_level_choices(self):
        parser = build_cli_parser()
        for lvl in ["1", "2", "3"]:
            parsed = parser.parse_args(["--level", lvl])
            assert parsed.level == lvl

        import pytest
        with pytest.raises(SystemExit):
            parser.parse_args(["--level", "4"])
        with pytest.raises(SystemExit):
            parser.parse_args(["--level", "invalid"])


class TestRunFromConfig:
    def test_run_from_config_level_1(self, monkeypatch):
        from unittest.mock import MagicMock

        from easy_apply_automator.app.runner import build_cli_parser, run_from_config

        mock_bot = MagicMock()
        monkeypatch.setattr("easy_apply_automator.app.runner.LinkedInEasyApplyOrchestrator", mock_bot)

        parser = build_cli_parser()
        args = parser.parse_args(["--level", "1"])
        run_from_config("config.yaml", cli_args=args)

        created_config = mock_bot.call_args[0][0]
        assert created_config.experience_level == [1]
        assert created_config.job_types == ["internship"]

    def test_run_from_config_level_2(self, monkeypatch):
        from unittest.mock import MagicMock

        from easy_apply_automator.app.runner import build_cli_parser, run_from_config

        mock_bot = MagicMock()
        monkeypatch.setattr("easy_apply_automator.app.runner.LinkedInEasyApplyOrchestrator", mock_bot)

        parser = build_cli_parser()
        args = parser.parse_args(["--level", "2"])
        run_from_config("config.yaml", cli_args=args)

        created_config = mock_bot.call_args[0][0]
        assert created_config.experience_level == [2, 3]
        assert created_config.job_types == ["full_time", "contract"]

    def test_run_from_config_level_3(self, monkeypatch):
        from unittest.mock import MagicMock

        from easy_apply_automator.app.runner import build_cli_parser, run_from_config

        mock_bot = MagicMock()
        monkeypatch.setattr("easy_apply_automator.app.runner.LinkedInEasyApplyOrchestrator", mock_bot)

        parser = build_cli_parser()
        args = parser.parse_args(["--level", "3"])
        run_from_config("config.yaml", cli_args=args)

        created_config = mock_bot.call_args[0][0]
        assert created_config.experience_level == [1, 2, 3]
        assert created_config.job_types == ["internship", "full_time", "contract"]

