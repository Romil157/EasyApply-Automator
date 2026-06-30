from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from easy_apply_automator.observability.logger import log


def load_recent_applied_ids(filename: str, days: int = 2) -> list[str] | None:
    file_path = Path(filename)
    if not file_path.exists():
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, list):
            return None

        threshold = datetime.now() - timedelta(days=days)
        job_ids: list[str] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            ts = item.get("timestamp")
            job_id = item.get("job_id")
            if not ts or not job_id:
                continue
            parsed_ts = None
            try:
                parsed_ts = datetime.fromisoformat(str(ts))
            except Exception:
                try:
                    parsed_ts = datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
            if parsed_ts > threshold:
                job_ids.append(str(job_id))
        log.info(f"{len(job_ids)} jobIDs found")
        return job_ids
    except Exception as exc:
        log.info(f"{exc}   jobIDs could not be loaded from JSON {filename}")
        return None


class ResultsRepository:
    def __init__(self, filename: str) -> None:
        self.filename = str(Path(filename).expanduser())
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        output_path = Path(self.filename)

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
