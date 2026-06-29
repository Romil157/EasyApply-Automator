import csv
import re
import time
from pathlib import Path

import yaml


class AutoAnswer:
    def __init__(
        self,
        qa_file: Path | None,
        ans_yaml_path: Path,
        salary: str,
        hourly_rate: str,
        answers: dict,
        log,
        linkedin_profile_url: str = "",
    ):
        self.qa_file = qa_file
        self.salary = salary
        self.hourly_rate = hourly_rate
        self.answers = answers
        self.log = log
        self.linkedin_profile_url = (linkedin_profile_url or "").strip()
        self.cfg = self._load_yaml(ans_yaml_path)

    def _load_yaml(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                if isinstance(cfg, dict):
                    return cfg
        except FileNotFoundError:
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
            "yes": str(defaults.get(True, "Yes")),      # bare 'yes:' in YAML → Python True
            "no": str(defaults.get(False, "No")),        # bare 'no:' in YAML → Python False
            "prefer_not": str(defaults.get("prefer_not", "Wish not to answer")),
            "no_self_id": str(defaults.get("no_self_id", "I do not wish to self-identify")),
            **work_auth,
            **demographics,
        }

        if self.linkedin_profile_url:
            ctx["linkedin_profile_url"] = self.linkedin_profile_url

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
            self.log.info(
                "Not able to answer question automatically. Please provide answer"
            )
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
                    self.log.info(
                        f"Appended to QA file: '{q}' with answer: '{answer}'."
                    )
                except Exception as exc:
                    self.log.warning(
                        f"Failed to append QA record to {self.qa_file}: {exc}"
                    )

        return answer
