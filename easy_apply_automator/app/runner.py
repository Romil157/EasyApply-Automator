from __future__ import annotations

import argparse

from easy_apply_automator.config.loader import load_run_config
from easy_apply_automator.domain.models import AppConfig
from easy_apply_automator.observability.logger import log

from .orchestrator import LinkedInEasyApplyOrchestrator


def build_cli_parser() -> argparse.ArgumentParser:
    """Builds rich CLI argument parser for EasyApply Automator."""
    parser = argparse.ArgumentParser(
        description="EasyApply Automator – LinkedIn Easy Apply automation bot using Python and Selenium.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate the apply flow without clicking the final submit button",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless anti-detection mode",
    )
    parser.add_argument(
        "--level",
        choices=["1", "2", "3"],
        default=None,
        help="Experience level filter: 1=Internship, 2=Entry/Associate, 3=All Levels",
    )
    parser.add_argument(
        "--date-posted",
        choices=["past_24h", "past_week", "past_month", "all"],
        default=None,
        help="Filter jobs by posted date",
    )
    parser.add_argument(
        "--max-apps",
        type=int,
        default=None,
        help="Maximum number of applications to submit in this session",
    )
    parser.add_argument(
        "--remote-only",
        action="store_true",
        default=False,
        help="Only search and apply for remote positions",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="HTTP or SOCKS5 proxy server address",
    )
    parser.add_argument(
        "--user-data-dir",
        type=str,
        default=None,
        help="Path to persistent Chrome user profile directory",
    )
    return parser


def run_from_config(
    config_path: str = "config.yaml", cli_args: argparse.Namespace | None = None
) -> None:
    run_cfg = load_run_config(config_path)
    app_config = AppConfig.from_dict(run_cfg.parameters, results_filename=run_cfg.results_filename)

    # Apply CLI overrides if present
    if cli_args:
        if cli_args.dry_run:
            app_config.runtime.dry_run = True
        if cli_args.headless:
            app_config.runtime.headless = True
        if cli_args.max_apps is not None:
            app_config.runtime.max_applications = cli_args.max_apps
        if cli_args.date_posted:
            app_config.date_posted = cli_args.date_posted
        if cli_args.remote_only:
            app_config.workplace_types = ["remote"]
        if cli_args.proxy:
            app_config.runtime.proxy = cli_args.proxy
        if cli_args.user_data_dir:
            app_config.runtime.user_data_dir = cli_args.user_data_dir

    if app_config.runtime.dry_run:
        log.info("=" * 60)
        log.info(" [DRY RUN MODE ENABLED] No applications will actually be submitted.")
        log.info("=" * 60)

    choice = cli_args.level if cli_args and cli_args.level else None

    if choice is None:
        print("\n" + "=" * 50)
        print("      SELECT JOB EXPERIENCE LEVEL")
        print("=" * 50)
        print(" 1 -> Internship Only")
        print(" 2 -> Entry Level & Associate (Other)")
        print(" 3 -> All Levels (Internship, Entry Level & Associate)")
        print("=" * 50)

        choice = "3"
        try:
            user_input = input("Select option (1, 2, or 3) [Default: 3]: ").strip()
            if user_input in ["1", "2", "3"]:
                choice = user_input
        except (EOFError, OSError):
            pass

    if choice == "1":
        app_config.experience_level = [1]
        app_config.positions = [
            f"{pos} Intern"
            if not pos.lower().endswith("intern") and not pos.lower().endswith("internship")
            else pos
            for pos in app_config.positions
        ]
    elif choice == "2":
        app_config.experience_level = [2, 3]
    else:
        app_config.experience_level = [1, 2, 3]

    bot = LinkedInEasyApplyOrchestrator(app_config)
    try:
        bot.start_apply(app_config.positions, app_config.locations)
    except KeyboardInterrupt:
        bot.log_event("session_interrupted", reason="keyboard_interrupt")
        log.warning("Session interrupted by user (Ctrl+C).")
    finally:
        try:
            bot.browser.quit()
        except Exception:
            pass

        print("\n" + "=" * 50)
        print("           SESSION SUMMARY")
        print("=" * 50)
        print(f" Jobs Scanned:     {bot.session_jobs_processed}")
        print(f" Jobs Attempted:   {bot.session_jobs_attempted}")
        print(f" Jobs Submitted:   {bot.session_jobs_submitted}")
        print(f" Failed Attempts:  {bot.session_jobs_failed_attempts}")
        print(f" Results Saved To: {bot.results_filename}")
        print(" HTML Report:      results/report_latest.html")
        print("=" * 50 + "\n")


def main() -> None:
    parser = build_cli_parser()
    args = parser.parse_args()
    run_from_config(args.config, cli_args=args)
