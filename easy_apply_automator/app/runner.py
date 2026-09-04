from __future__ import annotations

import argparse
import signal
import sys

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
        help="Target role type: 1=Internship only, 2=Full-Time and Entry-Level, 3=Both (Default)",
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

    if choice is None and sys.stdin and sys.stdin.isatty():
        print("\n=======================================================")
        print("            SELECT TARGET ROLE TYPE")
        print("=======================================================")
        print(" [1] Internship Roles Only")
        print(" [2] Full-Time and Entry-Level Roles")
        print(" [3] Both (Internship and Full-Time) [Default]")
        print("=======================================================")
        try:
            user_input = input("Select option (1, 2, or 3) [Default: 3]: ").strip()
            choice = user_input if user_input in ("1", "2", "3") else "3"
        except (EOFError, KeyboardInterrupt):
            choice = "3"

    if choice == "1":
        app_config.experience_level = [1]
        app_config.job_types = ["internship"]
        log.info(
            "Target role type: Internship Roles Only "
            "(experience_level=[1], job_types=['internship'])"
        )
    elif choice == "2":
        app_config.experience_level = [2, 3]
        app_config.job_types = ["full_time", "contract"]
        log.info(
            "Target role type: Full-Time and Entry-Level Roles "
            "(experience_level=[2, 3], job_types=['full_time', 'contract'])"
        )
    elif choice == "3":
        app_config.experience_level = [1, 2, 3]
        app_config.job_types = ["internship", "full_time", "contract"]
        log.info(
            "Target role type: Both Internship and Full-Time "
            "(experience_level=[1, 2, 3], job_types=['internship', 'full_time', 'contract'])"
        )
    else:
        log.info(
            f"Using config.yaml settings (experience_level={app_config.experience_level}, "
            f"job_types={app_config.job_types})"
        )

    bot = LinkedInEasyApplyOrchestrator(app_config)
    interrupted_once = False

    def _sigint_handler(signum, frame):
        nonlocal interrupted_once
        if not interrupted_once:
            interrupted_once = True
            log.warning("Interrupt signal received (Ctrl+C). Initiating graceful shutdown...")
            bot.request_stop("keyboard_interrupt")
        else:
            log.warning("Second interrupt received. Forcing exit immediately...")
            try:
                bot.save_session_cookies()
            except Exception:
                pass
            try:
                bot.browser.quit()
            except Exception:
                pass
            sys.exit(130)

    old_sigint = signal.signal(signal.SIGINT, _sigint_handler)
    try:
        bot.start_apply(app_config.positions, app_config.locations)
    except KeyboardInterrupt:
        bot.log_event("session_interrupted", reason="keyboard_interrupt")
        log.warning("Session interrupted by user (Ctrl+C).")
    finally:
        signal.signal(signal.SIGINT, old_sigint)
        try:
            bot.save_session_cookies()
        except Exception as exc:
            log.debug(f"Failed to save cookies on shutdown: {exc}")
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
