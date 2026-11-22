from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from azure_integration.foundry.models.base import FoundryModel

# Terminal Foundry response.* events → success for invoke completion.
TERMINAL_EVENTS: dict[str, bool] = {
    "response.completed": True,
    "response.failed": False,
    "response.cancelled": False,
    "response.incomplete": False,
}


class Usage(FoundryModel):
    # Responses API usage; all optional — Foundry omits zeros / partials.
    total_tokens: int | None = Field(default=None, alias="totalTokens")
    input_tokens: int | None = Field(default=None, alias="inputTokens")
    output_tokens: int | None = Field(default=None, alias="outputTokens")


class Response(FoundryModel):
    """Foundry Responses API resource (GET /responses/{id}, SSE terminal payload)."""

    # Only fields we read. status/output/etc. stay via extra="allow".
    id: str | None = None
    usage: Usage | None = None
    conversation_id: str | None = Field(default=None, alias="conversationId")
    error: Any = None

    def run_output(self, *, response_id: str) -> dict[str, Any]:
        # Flatten usage onto the run output (Port expects top-level *Tokens).
        return {
            "responseId": response_id,
            **self.model_dump(exclude={"error", "id", "usage"}),
            **(self.usage.model_dump() if self.usage else {}),
        }


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
