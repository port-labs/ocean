from __future__ import annotations

from typing import Any

from pydantic import Field

from azure_integration.foundry.models.base import FoundryModel

# Terminal Foundry response.* events → success for invoke completion.
TERMINAL_EVENTS: dict[str, bool] = {
    "response.completed": True,
    "response.failed": False,
    "response.cancelled": False,
    "response.incomplete": False,
}


class Usage(FoundryModel):
    prompt_tokens: int | None = Field(default=None, alias="promptTokens")
    completion_tokens: int | None = Field(default=None, alias="completionTokens")
    total_tokens: int | None = Field(default=None, alias="totalTokens")
    input_tokens: int | None = Field(default=None, alias="inputTokens")
    output_tokens: int | None = Field(default=None, alias="outputTokens")


class Response(FoundryModel):
    """Foundry Responses API resource (GET /responses/{id}, SSE terminal payload)."""

    status: str | None = None
    usage: Usage | None = None
    conversation_id: str | None = Field(default=None, alias="conversationId")
    output: list | None = None

    def run_output(self, *, response_id: str) -> dict[str, Any]:
        dumped = self.model_dump(exclude={"status", "output"})
        usage = dumped.pop("usage", None) or {}
        return {"responseId": response_id, **dumped, **usage}
