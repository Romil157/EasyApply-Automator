from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("easy_apply_automator")


class _SecondPrecisionFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%H:%M:%S")


def setup_logger(logs_dir: str | Path = "logs") -> logging.Logger:
    if log.handlers:
        return log

    log.setLevel(logging.INFO)
    log.propagate = False

    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)

    file_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_applyJobs.log")
    file_handler = logging.FileHandler(logs_path / file_name, encoding="utf-8")
    stream_handler = logging.StreamHandler()

    formatter = _SecondPrecisionFormatter("%(asctime)s | %(levelname)-5s | %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)

    return log
