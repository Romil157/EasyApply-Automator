"""Base service abstraction module providing bot orchestrator injection context."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


class ServiceBase:
    """Base class for all business services that require orchestrator context injection."""
    def __init__(self, bot: LinkedInEasyApplyOrchestrator) -> None:
        self.bot = bot
