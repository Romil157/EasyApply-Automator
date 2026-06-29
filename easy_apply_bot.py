"""LinkedIn Easy Apply Bot – Main Entry Point.

Run this file to start the bot:
    python easy_apply_bot.py
"""

from easy_apply_automator.app.runner import run_from_config


if __name__ == "__main__":
    run_from_config("config.yaml")
