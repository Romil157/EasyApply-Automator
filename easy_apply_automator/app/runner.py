from __future__ import annotations

from easy_apply_automator.config.loader import load_run_config
from easy_apply_automator.domain.models import AppConfig
from easy_apply_automator.observability.logger import log

from .orchestrator import LinkedInEasyApplyOrchestrator


def run_from_config(config_path: str = "config.yaml") -> None:
    run_cfg = load_run_config(config_path)
    app_config = AppConfig.from_dict(
        run_cfg.parameters, results_filename=run_cfg.results_filename
    )

    log.info(
        {
            k: run_cfg.parameters[k]
            for k in run_cfg.parameters.keys()
            if k not in ["username", "password"]
        }
    )

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


def main() -> None:
    run_from_config("config.yaml")
