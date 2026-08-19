"""Clean domain models and data container classes representing configurations and run status."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionMetrics:
    """Holds job counts and status metrics for the current execution session."""

    jobs_processed: int = 0
    jobs_submitted: int = 0
    jobs_attempted: int = 0
    jobs_failed_attempts: int = 0
    jobs_failed_medical: int = 0


@dataclass(slots=True)
class RuntimeConfig:
    """Holds operational constraints like durations, thresholds, and break timing limits."""

    max_pages_per_search: int = 3
    session_duration_hours_min: float = 3.0
    session_duration_hours_max: float = 5.0
    short_break_min_seconds: int = 20
    short_break_max_seconds: int = 75
    short_break_every_min_minutes: int = 8
    short_break_every_max_minutes: int = 18
    throughput_window_minutes: int = 30
    shuffle_search_combos: bool = False
    max_apply_seconds: int = 20
    max_applications: int = 0
    dry_run: bool = False
    headless: bool = False
    user_data_dir: str = ""
    proxy: str = ""


@dataclass(slots=True)
class AppConfig:
    """Holds user profile preferences, login credentials, blacklist keywords, and file targets."""

    username: str = ""
    password: str = ""
    phone_number: str = ""
    salary: str = ""
    rate: str = ""
    positions: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    uploads: dict[str, str] = field(default_factory=dict)
    location_country: str = "IN"
    location_city: str = "Mumbai"
    linkedin_profile_url: str = ""
    # High-sensitivity PII used to auto-fill Easy Apply forms. Sourced from env
    # vars (see .env.example) — never persisted inside the repo.
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    form_email: str = ""
    github_url: str = ""
    blacklist: list[str] = field(default_factory=list)
    blacklist_titles: list[str] = field(default_factory=list)
    filters: dict[str, list[str]] = field(default_factory=dict)
    locators: dict[str, list[str]] = field(default_factory=dict)
    experience_level: list[int] = field(default_factory=list)
    date_posted: str = ""
    workplace_types: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    ans_yaml_path: str = "questions_answers.yaml"
    results_filename: str = "results.json"
    events_filename: str = "logs/events.jsonl"
    cookies_path: str = ".auth/linkedin_cookies.json"
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @classmethod
    def from_dict(cls, parameters: dict[str, Any], results_filename: str) -> AppConfig:
        uploads = parameters.get("uploads") or {}
        if not isinstance(uploads, dict):
            uploads = {}

        def _to_bool(val: Any, default: bool = False) -> bool:
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ("true", "1", "yes", "y")

        runtime = RuntimeConfig(
            max_pages_per_search=int(parameters.get("max_pages_per_search", 3)),
            session_duration_hours_min=float(parameters.get("session_duration_hours_min", 3.0)),
            session_duration_hours_max=float(parameters.get("session_duration_hours_max", 5.0)),
            short_break_min_seconds=int(parameters.get("short_break_min_seconds", 20)),
            short_break_max_seconds=int(parameters.get("short_break_max_seconds", 75)),
            short_break_every_min_minutes=int(parameters.get("short_break_every_min_minutes", 8)),
            short_break_every_max_minutes=int(parameters.get("short_break_every_max_minutes", 18)),
            throughput_window_minutes=int(parameters.get("throughput_window_minutes", 30)),
            shuffle_search_combos=_to_bool(parameters.get("shuffle_search_combos", False)),
            max_apply_seconds=int(parameters.get("max_apply_seconds", 20)),
            max_applications=int(parameters.get("max_applications", 0)),
            dry_run=_to_bool(parameters.get("dry_run", False)),
            headless=_to_bool(parameters.get("headless", False)),
            user_data_dir=str(parameters.get("user_data_dir", "")).strip(),
            proxy=str(parameters.get("proxy", "")).strip(),
        )

        level_map = {6: 1, 1: 2, 2: 3}
        experience_level = []
        for v in parameters.get("experience_level", []):
            if v is not None:
                val = int(v)
                experience_level.append(level_map.get(val, val))

        workplace_types = [str(w) for w in parameters.get("workplace_types", []) if w]
        job_types = [str(j) for j in parameters.get("job_types", []) if j]

        return cls(
            username=str(parameters.get("username", "")),
            password=str(parameters.get("password", "")),
            phone_number=str(parameters.get("phone_number", "")),
            salary=str(parameters.get("salary", "")),
            rate=str(parameters.get("rate", "")),
            positions=[str(p) for p in parameters.get("positions", []) if p is not None],
            locations=[str(loc) for loc in parameters.get("locations", []) if loc is not None],
            uploads=uploads,
            location_country=str(parameters.get("location_country", "IN")).strip() or "IN",
            location_city=str(parameters.get("location_city", "Mumbai")),
            linkedin_profile_url=str(parameters.get("linkedin_profile_url", "")),
            full_name=str(parameters.get("full_name", "")),
            first_name=str(parameters.get("first_name", "")),
            last_name=str(parameters.get("last_name", "")),
            form_email=str(parameters.get("form_email", "")),
            github_url=str(parameters.get("github_url", "")),
            blacklist=[str(v) for v in parameters.get("blacklist", [])],
            blacklist_titles=[str(v) for v in parameters.get("blackListTitles", [])],
            filters=parameters.get("filters", {}),
            locators=parameters.get("locators", {}),
            experience_level=experience_level,
            date_posted=str(parameters.get("date_posted", "")).strip(),
            workplace_types=workplace_types,
            job_types=job_types,
            ans_yaml_path=str(parameters.get("ans_yaml_path", "questions_answers.yaml")),
            results_filename=str(Path(results_filename).expanduser()),
            events_filename=str(
                Path(parameters.get("events_filename", "logs/events.jsonl")).expanduser()
            ),
            cookies_path=str(
                Path(parameters.get("cookies_path", ".auth/linkedin_cookies.json")).expanduser()
            ),
            runtime=runtime,
        )
