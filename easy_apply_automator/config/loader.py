"""Configuration loader module that parses settings from YAML files and environment variables."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .schema import RunConfig

ENV_TO_CONFIG_KEY = {
    "LINKEDIN_USERNAME": "username",
    "LINKEDIN_PASSWORD": "password",
    "LINKEDIN_PHONE_NUMBER": "phone_number",
    "LINKEDIN_LOCATION_COUNTRY": "location_country",
    "LINKEDIN_LOCATION_CITY": "location_city",
    "LINKEDIN_PROFILE_URL": "linkedin_profile_url",
    "LINKEDIN_SALARY": "salary",
    "LINKEDIN_RATE": "rate",
    # High-sensitivity PII used to auto-fill Easy Apply forms. Sourced from
    # env vars (instead of questions_answers.yaml) to keep personal data out of
    # git. These are injected into rule-answer {placeholders} at render time.
    "LINKEDIN_FULL_NAME": "full_name",
    "LINKEDIN_FIRST_NAME": "first_name",
    "LINKEDIN_LAST_NAME": "last_name",
    "LINKEDIN_EMAIL": "form_email",
    "LINKEDIN_GITHUB_URL": "github_url",
    "EASYAPPLY_HEADLESS": "headless",
    "EASYAPPLY_DRY_RUN": "dry_run",
    "EASYAPPLY_MAX_APPLICATIONS": "max_applications",
    "EASYAPPLY_CHROME_USER_DATA_DIR": "user_data_dir",
    "EASYAPPLY_PROXY": "proxy",
    "EASYAPPLY_DATE_POSTED": "date_posted",
    # AI / LLM Auto-Answer Configuration
    "GROQ_API_KEY": "groq_api_key",
    "GEMINI_API_KEY": "gemini_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "OLLAMA_HOST": "ollama_host",
    "AI_PROVIDER": "ai_provider",
    "AI_MODEL": "ai_model",
    "AI_AUTO_LEARN": "ai_auto_learn",
}


def load_run_config(config_path: str | Path = "config.yaml") -> RunConfig:
    load_dotenv()

    path = Path(config_path)
    with path.open("r", encoding="utf-8") as stream:
        parameters = yaml.safe_load(stream) or {}

    # Load locators from separate file
    locators_path = Path("locators.yaml")
    if locators_path.exists():
        with locators_path.open("r", encoding="utf-8") as loc_stream:
            parameters["locators"] = yaml.safe_load(loc_stream) or {}

    for env_key, config_key in ENV_TO_CONFIG_KEY.items():
        env_value = os.getenv(env_key)
        if env_value is not None and env_value != "":
            parameters[config_key] = env_value

    required_keys = ["positions", "locations"]
    missing = [key for key in required_keys if key not in parameters]
    if missing:
        raise KeyError(f"Missing required keys in config.yaml: {', '.join(missing)}")

    if not parameters["positions"] or not parameters["locations"]:
        raise ValueError("'positions' and 'locations' must contain at least one entry")

    # Default credentials to empty if not provided in config/.env
    if not parameters.get("username"):
        parameters["username"] = ""

    if not parameters.get("password"):
        parameters["password"] = ""

    if isinstance(parameters.get("uploads"), list):
        raise ValueError(
            "uploads in config.yaml must be a dict, not a list. Remove '-' before key/value entries."
        )

    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    results_filename = f"results/{date_folder}/{timestamp}.json"
    return RunConfig(parameters=parameters, results_filename=results_filename)
