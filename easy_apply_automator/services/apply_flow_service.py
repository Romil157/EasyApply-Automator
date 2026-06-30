from __future__ import annotations

from ._form_filler import FormFillerMixin
from ._submit_flow import SubmitFlowMixin
from .base import ServiceBase


class ApplyFlowService(FormFillerMixin, SubmitFlowMixin, ServiceBase):
    """Composes form filling and application submission behaviors via mixins.

    This service exposes the high-level apply flow logic. The mixins it inherits from
    (_form_filler and _submit_flow) are intentionally internal.
    """
    pass

