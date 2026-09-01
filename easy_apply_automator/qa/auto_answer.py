"""Automatic question answering service containing match rules and pattern lists."""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from easy_apply_automator.qa.llm_client import LLMClient


class AutoAnswer:
    """Uses loaded YAML config rules, regular expressions, and AI/LLM fallback to resolve form answers."""

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
        llm_client: LLMClient | None = None,
    ):
        self.qa_file = qa_file
        self.ans_yaml_path = Path(ans_yaml_path) if ans_yaml_path else None
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
        self.current_job_title = ""
        self.current_job_company = ""
        self.cfg = self._load_yaml(self.ans_yaml_path) if self.ans_yaml_path else {}
        self.llm_client = llm_client or LLMClient.from_env_or_config(self.cfg, log=self.log)

    def set_current_job(self, job_title: str = "", company: str = "") -> None:
        """Set the active job title and company context to tailor LLM responses."""
        self.current_job_title = (job_title or "").strip()
        self.current_job_company = (company or "").strip()

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
                self.log.warning(f"Answer config not found at {path}, using fallback behavior.")
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

    def _normalize_skill_key(self, skill: str) -> str:
        """Normalizes skill text into a clean key matching profile.years dictionary keys."""
        s = skill.strip().lower()
        aliases = {
            "reactjs": "react",
            "react.js": "react",
            "nodejs": "nodejs",
            "node.js": "nodejs",
            "amazon web services": "aws",
            "c++": "cpp",
            "c#": "csharp",
            "golang": "go",
            "postgre": "sql",
            "postgresql": "sql",
            "postgres": "sql",
            "mysql": "sql",
            "nosql": "mongodb",
            "mongo": "mongodb",
            "gen ai": "llm_genai",
            "generative ai": "llm_genai",
            "artificial intelligence": "ai_ml",
            "ai/ml": "ai_ml",
            "ml": "machine_learning",
            "software development": "overall_software",
            "software engineering": "overall_software",
        }
        if s in aliases:
            return aliases[s]
        s_clean = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return aliases.get(s_clean, s_clean)

    def _extract_skill_years(self, question: str) -> str | None:
        """Dynamically identifies skill names in experience questions and looks up profile.years."""
        profile = self.cfg.get("profile", {})
        years = profile.get("years", {})
        if not years:
            return None

        q = question.lower()
        patterns = [
            r"how many years(?: of (?:work |professional )?experience)?(?: do you have)? (?:with|in|using|of)\s+([a-zA-Z0-9#\+\.\s\-_/]+?)(?:\?|$|\bexperience\b)",
            r"years of (?:work |professional )?experience (?:with|in|using|of)\s+([a-zA-Z0-9#\+\.\s\-_/]+?)(?:\?|$)",
            r"experience (?:with|in|using)\s+([a-zA-Z0-9#\+\.\s\-_/]+?)(?:\?|$)",
        ]
        for pat in patterns:
            match = re.search(pat, q)
            if match:
                raw_skill = match.group(1).strip(" .?:")
                norm_key = self._normalize_skill_key(raw_skill)
                if norm_key in years:
                    return str(years[norm_key])
        if any(
            w in q
            for w in ("year", "years", "experience", "how long", "rate", "scale", "level")
        ):
            for k, v in years.items():
                pattern = rf"\b{re.escape(k.replace('_', ' '))}\b"
                if re.search(pattern, q):
                    return str(v)

        return None

    def _heuristic_fallback(self, question: str) -> str | None:
        """Classifies common recruitment intent and provides smart context-aware answers."""
        q = (question or "").lower()
        defaults = self.cfg.get("defaults", {})
        profile = self.cfg.get("profile", {})
        work_auth = profile.get("work_auth", {})

        if any(
            w in q
            for w in (
                "notice period",
                "how soon can you start",
                "available start date",
                "earliest start date",
            )
        ):
            return "Immediately"
        if any(w in q for w in ("willing to relocate", "relocation")):
            return "Yes"
        if any(w in q for w in ("willing to commute", "commute to", "commute daily")):
            return "Yes"
        if any(w in q for w in ("driver's license", "drivers license", "valid driver")):
            return "Yes"
        if any(w in q for w in ("drug test", "background check", "criminal background")):
            return "Yes"
        if any(w in q for w in ("authorized to work", "legally authorized", "legal right to work")):
            return str(work_auth.get("legally_authorized", defaults.get(True, "Yes")))
        if any(w in q for w in ("require sponsorship", "need visa sponsorship", "require visa")):
            return str(work_auth.get("require_sponsorship", defaults.get(False, "No")))
        if any(
            w in q for w in ("highest level of education", "degree completed", "highest degree")
        ):
            return "Bachelor's Degree"
        if any(w in q for w in ("gpa", "cgpa", "grade point average")):
            return "9.0"
        if any(w in q for w in ("english proficiency", "english level", "proficiency in english")):
            return "Professional"
        if any(w in q for w in ("hybrid schedule", "onsite work", "in-person attendance")):
            return "Yes"
        return None

    def _build_profile_context(self) -> dict[str, Any]:
        """Assembles structured candidate background data and resume text to inform LLM zero-shot answers."""
        profile = self.cfg.get("profile", {})
        context: dict[str, Any] = {
            "candidate_name": self.full_name or f"{self.first_name} {self.last_name}".strip(),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.form_email,
            "phone": self.phone_number,
            "city": self.location_city,
            "linkedin_url": self.linkedin_profile_url,
            "github_url": self.github_url,
            "expected_salary": self.salary,
            "hourly_rate": self.hourly_rate,
            "skill_experience_years": profile.get("years", {}),
            "work_authorization": profile.get("work_auth", {}),
            "demographics": profile.get("demographics", {}),
            "defaults": self.cfg.get("defaults", {}),
            "current_job_title": getattr(self, "current_job_title", ""),
            "current_job_company": getattr(self, "current_job_company", ""),
        }
        resume_file = Path("resume.md")
        if resume_file.exists():
            try:
                context["resume_markdown"] = resume_file.read_text(encoding="utf-8")
            except Exception:
                pass
        return context

    def _persist_learned_rule(self, question: str, answer: str) -> None:
        """Appends an AI-resolved answer into local questions_answers.yaml for zero-cost reuse."""
        try:
            q_clean = question.strip()
            safe_id = "ai_" + re.sub(r"[^a-zA-Z0-9_]+", "_", q_clean).strip("_")[:35].lower()
            escaped_pattern = f"(?i){re.escape(q_clean)}"
            new_rule = {
                "id": safe_id,
                "match_any": [escaped_pattern],
                "answer": answer,
            }
            if "rules" not in self.cfg or not isinstance(self.cfg["rules"], list):
                self.cfg["rules"] = []
            self.cfg["rules"].append(new_rule)

            if self.ans_yaml_path and Path(self.ans_yaml_path).exists():
                pattern_dump = yaml.dump(escaped_pattern, default_style="'").strip()
                answer_dump = yaml.dump(answer, default_style='"').strip()
                with open(self.ans_yaml_path, "a", encoding="utf-8") as f:
                    f.write(
                        f"\n  # Auto-learned by AI on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write(f"  - id: {safe_id}\n")
                    f.write("    match_any:\n")
                    f.write(f"      - {pattern_dump}\n")
                    f.write(f"    answer: {answer_dump}\n")
                self.log.info(
                    f"Persisted AI-learned question '{q_clean}' -> '{answer}' to {self.ans_yaml_path}"
                )
        except Exception as exc:
            self.log.warning(f"Failed to persist learned AI rule: {exc}")

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
            extracted_years = self._extract_skill_years(q)
            if extracted_years is not None:
                answer = extracted_years

        if answer is None:
            heuristic_ans = self._heuristic_fallback(q)
            if heuristic_ans is not None:
                answer = heuristic_ans

        # Zero-shot AI/LLM fallback when available
        if answer is None and hasattr(self, "llm_client") and self.llm_client.is_available():
            self.log.info(f"Querying AI/LLM for unknown question: '{q}'")
            ai_answer = self.llm_client.answer_question(q, self._build_profile_context())
            if ai_answer:
                answer = ai_answer
                self.log.info(f"AI resolved question '{q}' with answer: '{answer}'")
                if getattr(self.llm_client, "auto_learn", True):
                    self._persist_learned_rule(q, answer)

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
