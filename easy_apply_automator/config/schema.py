from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RunConfig:
    parameters: dict[str, Any]
    results_filename: str
