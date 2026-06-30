from __future__ import annotations

from ._form_filler import FormFillerMixin
from ._submit_flow import SubmitFlowMixin
from .base import ServiceBase


class ApplyFlowService(FormFillerMixin, SubmitFlowMixin, ServiceBase):
    pass
