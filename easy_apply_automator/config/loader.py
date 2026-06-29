from __future__ import annotations

import getpass
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import yaml

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
}


def load_run_config(config_path: str | Path = "config.yaml") -> RunConfig:
    load_dotenv(override=True)

    path = Path(config_path)
    with path.open("r", encoding="utf-8") as stream:
        parameters = yaml.safe_load(stream) or {}

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

    results_filename = f"results/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    return RunConfig(parameters=parameters, results_filename=results_filename)
