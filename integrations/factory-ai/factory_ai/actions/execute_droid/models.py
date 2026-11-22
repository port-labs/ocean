from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, ValidationError

from factory_ai.actions.abstract_action_input import AbstractFactoryActionInput
from factory_ai.actions.exceptions import InvalidActionParametersError
from factory_ai.core.models import FactoryModel, FactoryPagination


class _ExecuteDroidBase(AbstractFactoryActionInput):
    prompt: str = Field(min_length=1)
    # Port-side only; never sent to Factory's execute body.
    waitForCompletion: bool = True


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


class MessageContentBlock(FactoryModel):
    """One content block on a session message.

    Known ``type`` values include ``text``, ``image``, ``thinking``,
    ``redacted_thinking``, ``tool_use``, ``tool_result``, and ``document``.
    Unknown fields are retained via ``FactoryModel``.
    """

    type: str
    text: str | None = None
    name: str | None = None


class SessionMessage(FactoryModel):
    """Session message used for turn-completion detection and reply extraction."""

    id: str
    role: str
    content: list[MessageContentBlock] | None = None
    model_id: str | None = Field(None, alias="modelId")
    is_error: bool | None = Field(None, alias="isError")
    created_at: str | None = Field(None, alias="createdAt")

    @property
    def text(self) -> str:
        """Join ``text`` content blocks from this message."""
        if not self.content:
            return ""
        parts = [
            block.text for block in self.content if block.type == "text" and block.text
        ]
        return "\n".join(parts)

    @property
    def tool_names(self) -> list[str]:
        """Names of ``tool_use`` blocks on this message, in order."""
        if not self.content:
            return []
        return [
            block.name
            for block in self.content
            if block.type == "tool_use" and block.name
        ]


class ListSessionMessagesResponse(FactoryModel):
    """Page of session messages (Factory lists newest-first)."""

    messages: list[SessionMessage]
    pagination: FactoryPagination

    def assistant_messages_after(self, user_message_id: str) -> list[SessionMessage]:
        """Assistant messages newer than ``user_message_id``, oldest first.

        Factory lists newest-first; we collect until the user message, then
        reverse so joined text reads chronologically.
        """
        collected: list[SessionMessage] = []
        for message in self.messages:
            if message.id == user_message_id:
                break
            if message.role == "assistant":
                collected.append(message)
        collected.reverse()
        return collected

    def assistant_reply_after(self, user_message_id: str) -> dict[str, Any]:
        """Port-facing reply fields from messages after ``user_message_id``.

        Empty dict means no assistant reply yet (turn still in progress).
        """
        assistants = self.assistant_messages_after(user_message_id)
        if not assistants:
            return {}

        text_parts = [text for msg in assistants if (text := msg.text)]
        # Dedupe tool names while preserving order.
        tool_names = list(
            dict.fromkeys(name for msg in assistants for name in msg.tool_names)
        )
        return {
            "assistantMessageIds": [msg.id for msg in assistants],
            "assistantMessageId": assistants[-1].id,
            "assistantText": "\n\n".join(text_parts),
            "toolNames": tool_names,
            "modelId": assistants[-1].model_id,
            "assistantIsError": any(msg.is_error for msg in assistants),
        }
