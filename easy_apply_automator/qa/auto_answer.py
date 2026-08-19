"""Automatic question answering service containing match rules and pattern lists."""
import csv
import re
from pathlib import Path

import yaml


class AutoAnswer:
    """Uses loaded YAML config rules and regular expressions to resolve form question answers."""

    def __init__(
        self,
        qa_file: Path | None,
        ans_yaml_path: Path,
        salary: str,
        hourly_rate: str,
        answers: dict,
        log,
        linkedin_profile_url: str = "",
        *,
        full_name: str = "",
        first_name: str = "",
        last_name: str = "",
        form_email: str = "",
        phone_number: str = "",
        github_url: str = "",
        location_city: str = "",
    ):
        self.qa_file = qa_file
        self.salary = salary
        self.hourly_rate = hourly_rate
        self.answers = answers
        self.log = log
        # High-sensitivity PII is sourced from environment variables (see
        # .env.example) and injected into rule-answer templates as {placeholders}.
        # Keeping these out of the YAML file prevents personal data from being
        # committed to git.
        self.linkedin_profile_url = (linkedin_profile_url or "").strip()
        self.full_name = (full_name or "").strip()
        self.first_name = (first_name or "").strip()
        self.last_name = (last_name or "").strip()
        self.form_email = (form_email or "").strip()
        self.phone_number = (phone_number or "").strip()
        self.github_url = (github_url or "").strip()
        self.location_city = (location_city or "").strip()
        self.cfg = self._load_yaml(ans_yaml_path)

    def _load_yaml(self, path: Path) -> dict:
        try:
            with open(path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                if isinstance(cfg, dict):
                    return cfg
        except FileNotFoundError:
            # Fall back to the tracked template file (e.g. questions_answers.example.yaml)
            # so a fresh clone still works without manual setup. Personal values are
            # then sourced from env vars / the user's later-edited local copy.
            example_path = path.with_name(path.stem + ".example" + path.suffix)
            if example_path != path and example_path.exists():
                self.log.info(
                    f"Answer config not found at {path}. Falling back to template at "
                    f"{example_path}. Copy this template to {path.name} and fill in "
                    f"your personal values, or supply them via env vars."
                )
                try:
                    with open(example_path, encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                        if isinstance(cfg, dict):
                            return cfg
                except Exception as exc:
                    self.log.warning(
                        f"Failed to load answer template at {example_path}: {exc}. "
                        f"Using fallback behavior."
                    )
                    return {}
            else:
                self.log.warning(
                    f"Answer config not found at {path}, using fallback behavior."
                )
        except Exception as exc:
            self.log.warning(
                f"Failed to load answer config at {path}: {exc}. Using fallback behavior."
            )
        return {}

    def _render(self, template: str) -> str:
        defaults = self.cfg.get("defaults", {})
        profile = self.cfg.get("profile", {})
        years = profile.get("years", {})
        work_auth = profile.get("work_auth", {})
        demographics = profile.get("demographics", {})

        ctx = {
            "salary": self.salary,
            "hourly_rate": self.hourly_rate,
            "unknown_years": str(defaults.get("unknown_years", "1")),
            "unknown_text": str(defaults.get("unknown_text", "user provided")),
            "yes": str(defaults.get(True, "Yes")),  # bare 'yes:' in YAML → Python True
            "no": str(defaults.get(False, "No")),  # bare 'no:' in YAML → Python False
            "prefer_not": str(defaults.get("prefer_not", "Wish not to answer")),
            "no_self_id": str(defaults.get("no_self_id", "I do not wish to self-identify")),
            **work_auth,
            **demographics,
        }

        # Env-sourced personal fields override anything that happens to be
        # present in the YAML profile blocks. Only inject when non-empty so
        # that an unset env var leaves the {placeholder} intact in the answer
        # (a visible signal to the user that the value is missing).
        personal = {
            "linkedin_profile_url": self.linkedin_profile_url,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "form_email": self.form_email,
            "phone_number": self.phone_number,
            "github_url": self.github_url,
            "location_city": self.location_city,
        }
        for key, value in personal.items():
            if value:
                ctx[key] = value

        def repl_years(match):
            key = match.group(1)
            return str(years.get(key, ctx["unknown_years"]))

        rendered = re.sub(r"\{years\.([a-zA-Z0-9_]+)\}", repl_years, template)

        for key, value in ctx.items():
            rendered = rendered.replace("{" + key + "}", str(value))

        return rendered

    def ans_question(self, question: str) -> str:
        q = (question or "").strip()
        answer = None

        for rule in self.cfg.get("rules", []):
            for pattern in rule.get("match_any", []):
                try:
                    if re.search(pattern, q):
                        answer = self._render(str(rule.get("answer", "")))
                        break
                except re.error as exc:
                    self.log.warning(
                        f"Invalid regex in answer rule '{rule.get('id', 'unknown')}': {exc}"
                    )
            if answer is not None:
                break

        if answer is None:
            self.log.info("Not able to answer question automatically. Please provide answer")
            answer = self.cfg.get("defaults", {}).get("unknown_text", "user provided")

        self.log.info(f"Answering question: {q} with answer: {answer}")

        if q and q not in self.answers:
            self.answers[q] = answer
            if self.qa_file is not None:
                try:
                    self.qa_file.parent.mkdir(parents=True, exist_ok=True)
                    file_exists = self.qa_file.exists()
                    with open(self.qa_file, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        if not file_exists:
                            writer.writerow(["Question", "Answer"])
                        writer.writerow([q, answer])
                    self.log.info(f"Appended to QA file: '{q}' with answer: '{answer}'.")
                except Exception as exc:
                    self.log.warning(f"Failed to append QA record to {self.qa_file}: {exc}")

        return answer
