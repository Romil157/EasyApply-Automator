"""Defines configuration container schemas used by the bot."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RunConfig:
    """Wrapper holding config parameters dictionary and results filename."""
    parameters: dict[str, Any]
    results_filename: str

