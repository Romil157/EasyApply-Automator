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
