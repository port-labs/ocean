from __future__ import annotations

from typing import Literal

from pydantic import Field

from factory_ai.actions.abstract_action_input import AbstractFactoryActionInput
from factory_ai.core.models import FactoryModel

SessionExecutionStatus = Literal["idle", "pending", "running"]


class InterruptSessionInputs(AbstractFactoryActionInput):
    sessionId: str = Field(min_length=1)


class InterruptSessionResponse(FactoryModel):
    """``POST /api/v0/sessions/{sessionId}/interrupt`` response body."""

    status: SessionExecutionStatus
