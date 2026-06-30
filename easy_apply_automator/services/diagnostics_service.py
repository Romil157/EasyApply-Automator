from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .base import ServiceBase


class DiagnosticsService(ServiceBase):
    @staticmethod
    def sanitize_for_path(value: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", value or "")
        return safe.strip("._") or "unknown"

    def start_job_debug_trace(self, job_id: str) -> None:
        self.bot.current_job_id = str(job_id)
        self.bot.current_job_debug_step = 0
        self.bot.current_job_failure_count = 0
        self.bot.current_job_first_try_dir = None
        if not self.bot.first_job_debug_done:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.bot.current_job_debug_dir = (
                self.bot.debug_root
                / f"first_job_{self.sanitize_for_path(str(job_id))}_{ts}"
            )
            self.bot.current_job_debug_dir.mkdir(parents=True, exist_ok=True)
            self.bot.current_job_first_try_dir = (
                self.bot.current_job_debug_dir / "first_try"
            )
            self.bot.current_job_first_try_dir.mkdir(parents=True, exist_ok=True)
            self.bot.log_event(
                "debug_trace_started",
                mode="first_job",
                job_id=str(job_id),
                debug_dir=str(self.bot.current_job_debug_dir),
                first_try_dir=str(self.bot.current_job_first_try_dir),
                html_capture=True,
            )
        else:
            self.bot.current_job_debug_dir = None
            self.bot.current_job_first_try_dir = None
            self.bot.log_event(
                "debug_trace_started",
                mode="normal_job",
                job_id=str(job_id),
                debug_dir=None,
                first_try_dir=None,
                html_capture=False,
            )

    def finish_job_debug_trace(self) -> None:
        mode = (
            "first_job" if self.bot.current_job_debug_dir is not None else "normal_job"
        )
        if self.bot.current_job_debug_dir is not None:
            self.bot.log_event(
                "debug_trace_finished",
                mode=mode,
                job_id=self.bot.current_job_id,
                debug_dir=str(self.bot.current_job_debug_dir),
                html_capture=True,
            )
            self.bot.first_job_debug_done = True
        else:
            self.bot.log_event(
                "debug_trace_finished",
                mode=mode,
                job_id=self.bot.current_job_id,
                debug_dir=None,
                html_capture=False,
            )

        self.bot.current_job_id = None
        self.bot.current_job_debug_dir = None
        self.bot.current_job_first_try_dir = None
        self.bot.current_job_debug_step = 0
        self.bot.current_job_failure_count = 0

    def dump_debug_html(
        self, tag: str, force_dir: Path | None = None, extra: dict | None = None
    ) -> None:
        target_dir = force_dir or self.bot.current_job_first_try_dir
        if target_dir is None:
            return
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            self.bot.current_job_debug_step += 1
            prefix = f"{self.bot.current_job_debug_step:03d}"
            filename = f"{prefix}_{self.sanitize_for_path(tag)}.html"
            html_path = target_dir / filename
            html_path.write_text(self.bot.browser.page_source or "", encoding="utf-8")
            meta = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "tag": tag,
                "job_id": self.bot.current_job_id,
                "url": self.bot.browser.current_url,
                "title": self.bot.browser.title,
                "progress": self.bot._get_easy_apply_progress(),
                **(extra or {}),
            }
            meta_path = target_dir / f"{prefix}_{self.sanitize_for_path(tag)}.json"
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            self.bot.log_event("debug_dump_error", tag=tag, error=str(exc))

    def dump_failure_snapshot(
        self, reason: str, force_failed_root: bool = False
    ) -> None:
        reason_safe = self.sanitize_for_path(reason)

        if self.bot.current_job_debug_dir is not None and not force_failed_root:
            self.bot.current_job_failure_count += 1
            failure_dir = (
                self.bot.current_job_debug_dir
                / f"failed_{self.bot.current_job_failure_count:04d}"
            )
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            job_id = self.sanitize_for_path(
                str(self.bot.current_job_id or "unknown_job")
            )
            job_debug_dir = self.bot.debug_failed_root / f"job_{job_id}_{ts}"
            job_debug_dir.mkdir(parents=True, exist_ok=True)
            failure_dir = job_debug_dir / "failed_0001"

        failure_dir.mkdir(parents=True, exist_ok=True)
        self.dump_debug_html(
            f"failure_{reason_safe}",
            force_dir=failure_dir,
            extra={"failure_reason": reason},
        )
        proof = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "job_id": self.bot.current_job_id,
            "reason": reason,
            "url": self.bot.browser.current_url,
            "title": self.bot.browser.title,
            "progress": self.bot._get_easy_apply_progress(),
            "failure_dir": str(failure_dir),
        }
        try:
            (failure_dir / "proof.json").write_text(
                json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            self.bot.log_event(
                "debug_dump_error",
                tag="proof_json",
                error=str(exc),
                failure_dir=str(failure_dir),
            )
        self.bot.log_event(
            "debug_failure_snapshot",
            reason=reason,
            job_id=self.bot.current_job_id,
            debug_dir=str(failure_dir),
        )

    def extract_job_metadata(self, job_id: str | None = None) -> dict:
        page_title = self.bot.browser.title or ""
        current_url = self.bot.browser.current_url or ""
        page_source = self.bot.browser.page_source or ""
        soup = BeautifulSoup(page_source, "lxml")

        def first_text(selectors: list[tuple[str, str]]) -> str | None:
            for by, value in selectors:
                node = None
                if by == "css":
                    node = soup.select_one(value)
                if node:
                    text = node.get_text(" ", strip=True)
                    if text:
                        return text
            return None

        title_from_page = first_text(
            [
                ("css", "h1"),
                ("css", ".top-card-layout__title"),
                ("css", ".jobs-unified-top-card__job-title"),
            ]
        )
        company_from_page = first_text(
            [
                ("css", ".topcard__org-name-link"),
                ("css", ".jobs-unified-top-card__company-name"),
                ("css", "a[data-tracking-control-name='public_jobs_topcard-org-name']"),
            ]
        )
        location_from_page = first_text(
            [
                ("css", ".topcard__flavor--bullet"),
                ("css", ".jobs-unified-top-card__bullet"),
            ]
        )

        salary_snippet = None

        def normalize_salary(value: str) -> str:
            return re.sub(r"\s+", " ", value).strip(" ,;:-")

        def extract_salary_from_text(
            text: str, require_context: bool = True
        ) -> str | None:
            if not text:
                return None

            normalized = " ".join(text.split())
            lowered = normalized.lower()
            has_context = any(
                key in lowered
                for key in (
                    "salary",
                    "compensation",
                    "pay range",
                    "base pay",
                    "base salary",
                    "hourly",
                    "per year",
                    "per hour",
                    "/year",
                    "/yr",
                    "/hour",
                    "/hr",
                )
            )
            if require_context and not has_context:
                return None

            range_match = re.search(
                r"(\$[\d,]+(?:\.\d+)?\s*[kKmM]?\s*(?:-|to)\s*\$?[\d,]+(?:\.\d+)?\s*[kKmM]?(?:\s*(?:/|per)\s*(?:year|yr|month|mo|hour|hr))?)",
                normalized,
                flags=re.IGNORECASE,
            )
            if range_match:
                return normalize_salary(range_match.group(1))

            unit_match = re.search(
                r"(\$[\d,]+(?:\.\d+)?\s*[kKmM]?\s*(?:/|per)\s*(?:year|yr|month|mo|hour|hr))",
                normalized,
                flags=re.IGNORECASE,
            )
            if unit_match:
                return normalize_salary(unit_match.group(1))

            simple_match = re.search(
                r"(\$[\d,]+(?:\.\d+)?\s*[kKmM])", normalized, flags=re.IGNORECASE
            )
            if simple_match:
                return normalize_salary(simple_match.group(1))
            return None

        try:
            for node in soup.select("script[type='application/ld+json']"):
                raw = node.get_text(strip=True)
                if not raw:
                    continue
                payload = json.loads(raw)
                entries = payload if isinstance(payload, list) else [payload]
                for entry in entries:
                    if (
                        not isinstance(entry, dict)
                        or entry.get("@type") != "JobPosting"
                    ):
                        continue
                    base_salary = entry.get("baseSalary")
                    if isinstance(base_salary, dict):
                        currency = base_salary.get("currency")
                        value_block = base_salary.get("value", {})
                        if isinstance(value_block, dict):
                            min_value = value_block.get("minValue")
                            max_value = value_block.get("maxValue")
                            unit_text = value_block.get("unitText")
                            value = value_block.get("value")
                            currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(
                                str(currency), str(currency or "")
                            )
                            unit_map = {
                                "YEAR": "/year",
                                "MONTH": "/month",
                                "HOUR": "/hour",
                                "WEEK": "/week",
                            }
                            unit_suffix = (
                                unit_map.get(
                                    str(unit_text).upper(), f"/{unit_text.lower()}"
                                )
                                if unit_text
                                else ""
                            )
                            if min_value is not None and max_value is not None:
                                salary_snippet = normalize_salary(
                                    f"{currency_symbol}{min_value}-{currency_symbol}{max_value} {unit_suffix}"
                                )
                            elif value is not None:
                                salary_snippet = normalize_salary(
                                    f"{currency_symbol}{value} {unit_suffix}"
                                )
                    if salary_snippet:
                        break
                if salary_snippet:
                    break
        except Exception:
            salary_snippet = None

        if not salary_snippet:
            salary_selectors = [
                ".jobs-unified-top-card__job-insight",
                ".job-details-jobs-unified-top-card__job-insight",
                ".jobs-unified-top-card__subtitle-secondary-grouping",
                ".jobs-description__content",
            ]
            for selector in salary_selectors:
                for node in soup.select(selector):
                    salary_snippet = extract_salary_from_text(
                        node.get_text(" ", strip=True), require_context=True
                    )
                    if salary_snippet:
                        break
                if salary_snippet:
                    break

        if not salary_snippet:
            salary_snippet = extract_salary_from_text(
                soup.get_text(" ", strip=True), require_context=True
            )

        derived_job_id = job_id
        if not derived_job_id:
            id_match = re.search(r"/jobs/view/(\d+)", current_url)
            if id_match:
                derived_job_id = id_match.group(1)

        title_parts = page_title.split(" | ") if page_title else []
        fallback_title = title_parts[0] if title_parts else None
        fallback_company = title_parts[1] if len(title_parts) > 1 else None

        return {
            "job_id": derived_job_id,
            "job_link": current_url,
            "job_title": title_from_page or fallback_title,
            "company": company_from_page or fallback_company,
            "location": location_from_page,
            "salary": salary_snippet,
            "page_title": page_title,
        }

    def medical_keyword_match(self) -> str | None:
        def normalize_text(value: str) -> str:
            value = value.lower()
            value = re.sub(r"\s+", " ", value)
            return value.strip()

        benefit_phrases = {
            "medical insurance",
            "health insurance",
            "dental insurance",
            "vision insurance",
            "disability insurance",
            "paid maternity leave",
            "paid paternity leave",
            "commuter benefits",
            "pension plan",
            "401(k)",
            "featured benefits",
            "benefits package",
        }

        try:
            title = normalize_text(self.bot.browser.title or "")
            for kw in self.bot.medical_related_keywords:
                if kw in title:
                    return kw
        except Exception:
            pass

        try:
            soup = BeautifulSoup(self.bot.browser.page_source or "", "lxml")
            description_node = soup.select_one(".show-more-less-html__markup")
            description_text = normalize_text(
                description_node.get_text(" ", strip=True) if description_node else ""
            )
            if not description_text:
                return None

            for phrase in benefit_phrases:
                description_text = description_text.replace(phrase, " ")
            description_text = normalize_text(description_text)

            for kw in self.bot.medical_related_keywords:
                if kw not in description_text:
                    continue
                for match in re.finditer(re.escape(kw), description_text):
                    left = max(0, match.start() - 30)
                    right = min(len(description_text), match.end() + 50)
                    snippet = description_text[left:right]
                    if "insurance" in snippet or "benefit" in snippet:
                        continue
                    return kw
        except Exception:
            pass
        return None
