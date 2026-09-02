"""Service that records HTML debugging snapshots, page source logs, and troubleshooting traces."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .base import ServiceBase


class DiagnosticsService(ServiceBase):
    """Logs browser page states, HTML screenshots, and stack traces when applying fails."""

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
                self.bot.debug_root / f"first_job_{self.sanitize_for_path(str(job_id))}_{ts}"
            )
            self.bot.current_job_debug_dir.mkdir(parents=True, exist_ok=True)
            self.bot.current_job_first_try_dir = self.bot.current_job_debug_dir / "first_try"
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
            self.bot.log_event("debug_trace_started", mode="normal_job", job_id=str(job_id), debug_dir=None, first_try_dir=None, html_capture=False)

    def finish_job_debug_trace(self) -> None:
        mode = "first_job" if self.bot.current_job_debug_dir is not None else "normal_job"
        self.bot.log_event(
            "debug_trace_finished",
            mode=mode,
            job_id=self.bot.current_job_id,
            debug_dir=str(self.bot.current_job_debug_dir) if self.bot.current_job_debug_dir else None,
            html_capture=bool(self.bot.current_job_debug_dir),
        )
        if self.bot.current_job_debug_dir is not None:
            self.bot.first_job_debug_done = True

        self.bot.current_job_id = None
        self.bot.current_job_debug_dir = None
        self.bot.current_job_first_try_dir = None
        self.bot.current_job_debug_step = 0
        self.bot.current_job_failure_count = 0

    def dump_debug_html(self, tag: str, force_dir: Path | None = None, extra: dict | None = None) -> None:
        target_dir = force_dir or self.bot.current_job_first_try_dir
        if target_dir is None:
            return
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            self.bot.current_job_debug_step += 1
            prefix = f"{self.bot.current_job_debug_step:03d}"
            filename = f"{prefix}_{self.sanitize_for_path(tag)}.html"
            (target_dir / filename).write_text(self.bot.browser.page_source or "", encoding="utf-8")
            meta = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "tag": tag,
                "job_id": self.bot.current_job_id,
                "url": self.bot.browser.current_url,
                "title": self.bot.browser.title,
                "progress": self.bot._get_easy_apply_progress(),
                **(extra or {}),
            }
            (target_dir / f"{prefix}_{self.sanitize_for_path(tag)}.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            self.bot.log_event("debug_dump_error", tag=tag, error=str(exc))

    def dump_failure_snapshot(self, reason: str, force_failed_root: bool = False) -> None:
        reason_safe = self.sanitize_for_path(reason)
        if self.bot.current_job_debug_dir is not None and not force_failed_root:
            self.bot.current_job_failure_count += 1
            failure_dir = self.bot.current_job_debug_dir / f"failed_{self.bot.current_job_failure_count:04d}"
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            job_id = self.sanitize_for_path(str(self.bot.current_job_id or "unknown_job"))
            job_debug_dir = self.bot.debug_failed_root / f"job_{job_id}_{ts}"
            job_debug_dir.mkdir(parents=True, exist_ok=True)
            failure_dir = job_debug_dir / "failed_0001"

        failure_dir.mkdir(parents=True, exist_ok=True)
        self.dump_debug_html(f"failure_{reason_safe}", force_dir=failure_dir, extra={"failure_reason": reason})
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
            (failure_dir / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        self.bot.log_event("debug_failure_snapshot", reason=reason, job_id=self.bot.current_job_id, debug_dir=str(failure_dir))

    def extract_job_metadata(self, job_id: str | None = None) -> dict:
        page_title = self.bot.browser.title or ""
        current_url = self.bot.browser.current_url or ""
        soup = BeautifulSoup(self.bot.browser.page_source or "", "lxml")

        def first_text(selectors: list[str]) -> str | None:
            for sel in selectors:
                node = soup.select_one(sel)
                if node:
                    text = node.get_text(" ", strip=True)
                    if text:
                        return text
            return None

        title_from_page = first_text([
            "h1", ".top-card-layout__title", ".jobs-unified-top-card__job-title",
            ".job-details-jobs-unified-top-card__job-title", "h1.t-24", "a[data-view-name='job-title']",
        ])
        if title_from_page and title_from_page.strip().lower() in ("linkedin", "jobs", "feed"):
            title_from_page = None

        company_from_page = first_text([
            ".topcard__org-name-link", ".jobs-unified-top-card__company-name",
            ".job-details-jobs-unified-top-card__company-name", "a[data-tracking-control-name='public_jobs_topcard-org-name']",
            ".jobs-unified-top-card__primary-description a", "a[href*='/company/']",
        ])
        location_from_page = first_text([
            ".topcard__flavor--bullet", ".jobs-unified-top-card__bullet",
            ".jobs-unified-top-card__workplace-type", ".job-details-jobs-unified-top-card__bullet",
        ])

        def normalize_salary(val: str) -> str:
            return re.sub(r"\s+", " ", val).strip(" ,;:-")

        def extract_salary_from_text(text: str, require_context: bool = True) -> str | None:
            if not text:
                return None
            cleaned = re.sub(r"\s+", " ", text).strip()
            pat = r"([$₹£€]\s?\d{1,3}(?:[,\.]\d{2,3})*(?:\.\d+)?(?:\s?[kKlLcC]r?)?(?:\s?-\s?[$₹£€]?\s?\d{1,3}(?:[,\.]\d{2,3})*(?:\.\d+)?(?:\s?[kKlLcC]r?)?)?\s*(?:/\s*(?:yr|year|hr|hour|mo|month|wk|week|pm|pa)|per\s+(?:year|hour|month|week)|a\s+(?:year|hour|month|week))?)"
            m = re.search(pat, cleaned, flags=re.IGNORECASE)
            if m:
                match_text = m.group(1).strip()
                if not require_context:
                    return normalize_salary(match_text)
                has_symbol = any(sym in match_text for sym in ("$", "₹", "£", "€"))
                has_period = bool(re.search(r"/\s*(?:yr|year|hr|hour|mo|month|wk|week|pm|pa)|per\s+|a\s+(?:year|month|hour)", match_text, flags=re.IGNORECASE))
                has_k = bool(re.search(r"\d+\s?[kKlLcC]r?", match_text))
                if has_symbol and (has_period or has_k or "-" in match_text):
                    return normalize_salary(match_text)
            return None

        salary_snippet = None
        try:
            for s in soup.find_all("script", type=re.compile(r"ld\+json", re.I)):
                payload = s.string or s.text or ""
                if payload:
                    data = json.loads(payload)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and isinstance(item.get("baseSalary"), dict):
                            bs = item["baseSalary"]
                            curr = bs.get("currency") or "$"
                            val_obj = bs.get("value")
                            if isinstance(val_obj, dict):
                                min_v, max_v, v = val_obj.get("minValue"), val_obj.get("maxValue"), val_obj.get("value")
                                unit = f"/{str(val_obj.get('unitText', '')).lower()}" if val_obj.get("unitText") else ""
                                if min_v is not None and max_v is not None:
                                    salary_snippet = normalize_salary(f"{curr}{min_v}-{curr}{max_v} {unit}")
                                elif v is not None:
                                    salary_snippet = normalize_salary(f"{curr}{v} {unit}")
                        if salary_snippet:
                            break
                if salary_snippet:
                    break
        except Exception:
            pass

        if not salary_snippet:
            for sel in (".jobs-unified-top-card__job-insight", ".job-details-jobs-unified-top-card__job-insight", ".jobs-description__content"):
                node = soup.select_one(sel)
                if node:
                    salary_snippet = extract_salary_from_text(node.get_text(" ", strip=True), require_context=True)
                    if salary_snippet:
                        break

        derived_job_id = job_id
        if not derived_job_id:
            m = re.search(r"/jobs/view/(\d+)", current_url)
            if m:
                derived_job_id = m.group(1)

        title_parts = [p.strip() for p in page_title.split(" | ")] if page_title else []
        if title_parts and title_parts[-1].lower() == "linkedin":
            title_parts = title_parts[:-1]

        if len(title_parts) >= 2:
            fallback_company, fallback_title = title_parts[-1], " | ".join(title_parts[:-1])
        elif len(title_parts) == 1:
            fallback_company, fallback_title = None, title_parts[0]
        else:
            fallback_company, fallback_title = None, None

        return {
            "job_id": derived_job_id,
            "job_link": current_url,
            "job_title": title_from_page or fallback_title or "Unknown Role",
            "company": company_from_page or fallback_company or "Unknown Company",
            "location": location_from_page,
            "salary": salary_snippet,
            "page_title": page_title,
        }

    def medical_keyword_match(self) -> str | None:
        def norm(val: str) -> str:
            return re.sub(r"\s+", " ", (val or "").lower()).strip()

        benefit_phrases = (
            "medical insurance", "health insurance", "dental insurance", "vision insurance",
            "disability insurance", "paid maternity leave", "paid paternity leave",
            "commuter benefits", "pension plan", "401(k)", "featured benefits", "benefits package",
        )

        try:
            title = norm(self.bot.browser.title or "")
            for kw in self.bot.medical_related_keywords:
                if kw in title:
                    return kw
        except Exception:
            pass

        try:
            soup = BeautifulSoup(self.bot.browser.page_source or "", "lxml")
            node = soup.select_one(".show-more-less-html__markup")
            desc = norm(node.get_text(" ", strip=True) if node else "")
            if desc:
                for phrase in benefit_phrases:
                    desc = desc.replace(phrase, " ")
                desc = norm(desc)
                for kw in self.bot.medical_related_keywords:
                    if kw in desc:
                        for match in re.finditer(re.escape(kw), desc):
                            snippet = desc[max(0, match.start() - 30):min(len(desc), match.end() + 50)]
                            if "insurance" not in snippet and "benefit" not in snippet:
                                return kw
        except Exception:
            pass
        return None
