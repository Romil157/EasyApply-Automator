from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .logger import log


class EventLogger:
    def __init__(self, events_filename: str) -> None:
        self.events_filename = str(Path(events_filename).expanduser())
        Path(self.events_filename).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _short_value(value: Any) -> str:
        text = str(value)
        if len(text) > 80:
            return text[:77] + "..."
        return text

    def _format_event_line(self, event: str, fields: dict[str, Any]) -> str:
        preferred_order = [
            "job_id",
            "position",
            "location",
            "step",
            "loop",
            "progress",
            "progress_before",
            "progress_after",
            "status",
            "reason",
            "mode",
            "success",
            "ready",
            "attempted",
            "result",
            "elapsed_seconds",
            "minutes_left",
        ]
        used = set()
        parts: list[str] = []
        for key in preferred_order:
            if key in fields:
                parts.append(f"{key}={self._short_value(fields[key])}")
                used.add(key)
        for key in sorted(fields.keys()):
            if key in used:
                continue
            parts.append(f"{key}={self._short_value(fields[key])}")
        tail = " | ".join(parts)
        return f"event={event}" + (f" | {tail}" if tail else "")

    def log_event(self, event: str, **fields: Any) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        log.info(self._format_event_line(event, fields))
        try:
            with open(self.events_filename, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.error(f"Failed to persist JSON event log: {exc}")
