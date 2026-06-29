from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


class ServiceBase:
    def __init__(self, bot: "LinkedInEasyApplyOrchestrator") -> None:
        self.bot = bot
