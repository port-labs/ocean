from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, ValidationError

from factory_ai.actions.abstract_action_input import AbstractFactoryActionInput
from factory_ai.actions.exceptions import InvalidActionParametersError
from factory_ai.core.models import FactoryModel


class _ExecuteDroidBase(AbstractFactoryActionInput):
    prompt: str = Field(min_length=1)


class _NewSessionExecuteDroidInputs(_ExecuteDroidBase):
    """Shared options for targets that create a new session."""

    model: str | None = Field(default=None, min_length=1)
    reasoningEffort: (
        Literal[
            "none",
            "dynamic",
            "off",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ]
        | None
    ) = None

    def _new_session_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if self.model:
            options["model"] = self.model
        if self.reasoningEffort:
            options["reasoningEffort"] = self.reasoningEffort
        return options


class ExecuteDroidEnvironmentInputs(_NewSessionExecuteDroidInputs):
    targetKind: Literal["environment"]
    environmentId: str = Field(min_length=1)

    def to_request_body(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "target": {
                "kind": "environment",
                "environmentId": self.environmentId,
            },
            **self._new_session_options(),
        }


class ExecuteDroidComputerInputs(_NewSessionExecuteDroidInputs):
    targetKind: Literal["computer"]
    computerId: str = Field(min_length=1)

    def to_request_body(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "target": {"kind": "computer", "computerId": self.computerId},
            **self._new_session_options(),
        }


class ExecuteDroidSessionInputs(_ExecuteDroidBase):
    """Follow-up on an existing session; model/reasoningEffort do not apply."""

    targetKind: Literal["session"]
    sessionId: str = Field(min_length=1)

    def to_request_body(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "target": {"kind": "session", "sessionId": self.sessionId},
        }


ExecuteDroidInputs = Annotated[
    ExecuteDroidEnvironmentInputs
    | ExecuteDroidComputerInputs
    | ExecuteDroidSessionInputs,
    Field(discriminator="targetKind"),
]

_EXECUTE_DROID_INPUTS_ADAPTER: TypeAdapter[ExecuteDroidInputs] = TypeAdapter(
    ExecuteDroidInputs
)


def parse_execute_droid_inputs(
    execution_properties: dict[str, Any],
) -> ExecuteDroidInputs:
    """Validate execution properties into the model for ``targetKind``."""
    try:
        return _EXECUTE_DROID_INPUTS_ADAPTER.validate_python(execution_properties)
    except ValidationError as error:
        raise InvalidActionParametersError(
            AbstractFactoryActionInput._format_validation_error(error)
        ) from error


class ExecuteDroidResponse(FactoryModel):
    """202 Accepted body from ``POST /api/v0/droid/execute``."""

    session_id: str = Field(alias="sessionId", min_length=1)
    computer_id: str = Field(alias="computerId", min_length=1)
    message_id: str = Field(alias="messageId", min_length=1)
