"""Data storage repository module for loading and appending job application results."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from easy_apply_automator.observability.logger import log


def load_recent_applied_ids(filename: str, days: int = 2) -> list[str] | None:
    """Loads job IDs from JSON file(s) that were applied within the specified number of days."""
    files_to_check: list[Path] = []
    file_path = Path(filename)
    if file_path.exists():
        files_to_check.append(file_path)

    results_dir = Path("results")
    if results_dir.exists():
        for candidate in results_dir.glob("**/*.json"):
            if candidate not in files_to_check:
                files_to_check.append(candidate)

    if not files_to_check:
        return None

    threshold = datetime.now() - timedelta(days=days)
    job_ids: list[str] = []
    seen_ids: set[str] = set()

    for target_file in files_to_check:
        try:
            with open(target_file, encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, list):
                continue
            for record in payload:
                if not isinstance(record, dict):
                    continue
                job_id = record.get("job_id")
                if not job_id:
                    continue
                job_id_str = str(job_id)
                if job_id_str in seen_ids:
                    continue
                res = record.get("result")
                reason = str(record.get("reason") or "")
                is_definitive = bool(res) or reason in (
                    "already_applied",
                    "submitted",
                    "title_blacklisted",
                    "medical_related_title",
                    "database_related_title",
                    "not_relevant",
                    "no_easy_apply_button",
                    "blacklisted_title",
                    "blacklisted_company",
                )
                if not is_definitive:
                    continue
                ts = record.get("timestamp")
                if not ts:
                    continue
                parsed_ts = None
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                ):
                    try:
                        parsed_ts = datetime.strptime(str(ts), fmt)
                        break
                    except Exception:
                        continue
                if parsed_ts is None:
                    try:
                        parsed_ts = datetime.fromisoformat(str(ts))
                    except Exception:
                        continue
                if parsed_ts and parsed_ts > threshold:
                    seen_ids.add(job_id_str)
                    job_ids.append(job_id_str)
        except Exception as exc:
            log.debug(f"Error reading applied IDs from {target_file}: {exc}")

    log.info(f"{len(job_ids)} recent applied jobIDs loaded")
    return job_ids


class ResultsRepository:
    """Manages reading and appending job application statistics to a local JSON file."""

    def __init__(self, filename: str) -> None:
        self.filename = str(Path(filename).expanduser())
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        output_path = Path(self.filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        existing: list[Any] = []
        if output_path.exists():
            with open(output_path, encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    existing = loaded

        existing.append(record)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        # Write to a CSV file (Excel-compatible UTF-8 with BOM)
        import csv

        csv_path = output_path.with_suffix(".csv")
        if existing:
            keys = []
            for r in existing:
                for k in r.keys():
                    if k not in keys:
                        keys.append(k)
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as csv_f:
                writer = csv.DictWriter(csv_f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(existing)

        # Generate HTML report in both the dated directory and root results directory
        try:
            from easy_apply_automator.observability.reporter import generate_html_report

            html_path = output_path.with_suffix(".html")
            generate_html_report(html_path, existing)

            date_latest_path = output_path.parent / "report_latest.html"
            generate_html_report(date_latest_path, existing)

            generate_html_report("results/report_latest.html", existing)
        except Exception as exc:
            log.debug(f"Failed to generate HTML report: {exc}")
