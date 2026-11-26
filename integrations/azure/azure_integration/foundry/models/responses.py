from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from azure_integration.foundry.helpers.utils import parse_foundry_timestamp
from azure_integration.foundry.models.base import FoundryModel

# Terminal Foundry response.* events → success for invoke completion.
TERMINAL_EVENTS: dict[str, bool] = {
    "response.completed": True,
    "response.failed": False,
    "response.cancelled": False,
    "response.incomplete": False,
}

_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "incomplete", "canceled"}
)


class ResponseConversationRef(FoundryModel):
    """Nested ``conversation`` on Responses list/get rows."""

    id: str


class Usage(FoundryModel):
    # Responses API usage; all optional — Foundry omits zeros / partials.
    total_tokens: int | None = Field(default=None, alias="totalTokens")
    input_tokens: int | None = Field(default=None, alias="inputTokens")
    output_tokens: int | None = Field(default=None, alias="outputTokens")
    input_tokens_details: Any = Field(default=None, alias="inputTokensDetails")
    output_tokens_details: Any = Field(default=None, alias="outputTokensDetails")


class Response(FoundryModel):
    """Foundry Responses API resource (GET /responses/{id}, SSE terminal payload)."""

    id: str | None = None
    status: str | None = None
    created_at: int | float | str | None = Field(default=None, alias="createdAt")
    completed_at: int | float | str | None = Field(default=None, alias="completedAt")
    updated_at: int | float | str | None = Field(default=None, alias="updatedAt")
    usage: Usage | None = None
    conversation: ResponseConversationRef | str | None = None
    conversation_id: str | None = Field(default=None, alias="conversationId")
    output: Any = None
    error: Any = None

    def is_in_progress(self) -> bool:
        if not self.status:
            return True
        return self.status.casefold() not in _TERMINAL_STATUSES

    def resolved_conversation_id(self) -> str | None:
        conv = self.conversation
        if isinstance(conv, ResponseConversationRef):
            return conv.id
        if isinstance(conv, str) and conv.strip():
            return conv.strip()
        if self.conversation_id and self.conversation_id.strip():
            return self.conversation_id.strip()
        return None

    def active_duration_seconds(self) -> int:
        start = parse_foundry_timestamp(self.created_at)
        if start is None:
            return 0
        end = (
            parse_foundry_timestamp(self.completed_at)
            or parse_foundry_timestamp(self.updated_at)
            or start
        )
        return max(0, int((end - start).total_seconds()))

    def created_at_datetime(self) -> datetime | None:
        return parse_foundry_timestamp(self.created_at)

    def failure_message(self) -> str | None:
        if isinstance(self.error, dict):
            message = self.error.get("message") or self.error.get("code")
            return str(message) if message else None
        if self.error is not None:
            return str(self.error)
        return None

    def run_output(self, *, response_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"responseId": response_id}
        if self.conversation_id:
            result["conversationId"] = self.conversation_id
        if self.usage:
            result.update(self.usage.model_dump())
        if answer := self._answer():
            result["answer"] = answer
        return result

    def _answer(self) -> str:
        texts: list[str] = []
        for item in self.output or []:
            if not isinstance(item, dict):
                continue
            for part in item.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    if text := part.get("text"):
                        texts.append(text)
        return "\n".join(texts)


class ResponsesSseEvent(BaseModel):
    """SSE envelope around a Foundry ``Response`` (or a partial one mid-stream)."""

    model_config = ConfigDict(extra="ignore")

    type: str
    text: str | None = None
    message: str | None = None
    error: Any = None
    response: Response | None = None

    @classmethod
    def parse_payload(cls, payload: str) -> ResponsesSseEvent | None:
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(raw, dict):
            return None
        try:
            return cls.model_validate(raw)
        except ValidationError:
            return None

    @property
    def response_id(self) -> str | None:
        return self.response.id if self.response else None

    @property
    def is_terminal(self) -> bool:
        return self.type in TERMINAL_EVENTS

    @property
    def error_message(self) -> str | None:
        if self.type == "error":
            message = self.message or self.error
            return str(message) if message else None
        error = self.response.error if self.response else None
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            return str(message) if message else None
        return None

    def log_message(self) -> str | None:
        if self.type == "response.output_text.delta":
            return None
        if self.type == "response.output_text.done":
            return (self.text or "").strip() or None
        if err := self.error_message:
            return f"Error: {err}"
        return None
