from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from azure_integration.foundry.helpers.responses_catalog import (
    FoundryUsage,
    conversation_id_from_response,
)

_FAILED_STATUSES = frozenset({"failed", "cancelled", "incomplete"})


def dashboard_webhook_endpoints_url(account_base: str) -> str:
    return f"{account_base}/openai/v1/dashboard/webhook_endpoints"


class FoundryResponseBody(BaseModel):
    """Responses API body fields needed for invoke run completion."""

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    usage: FoundryUsage | None = None
    conversation_id: str | None = None
    conversationId: str | None = None
    conversation: Any = None
    output: list[Any] | None = None

    def assistant_text(self) -> str | None:
        if not self.output:
            return None
        parts: list[str] = []
        for item in self.output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") in {"output_text", "text"}
                    and block.get("text")
                ):
                    parts.append(str(block["text"]))
        return "\n".join(parts) if parts else None

    def success_override(self) -> bool | None:
        if self.status in _FAILED_STATUSES:
            return False
        if self.status == "completed":
            return True
        return None

    def slim_run_output(
        self,
        *,
        response_id: str,
        prior_conversation_id: str | None = None,
    ) -> dict[str, Any]:
        slim: dict[str, Any] = {"responseId": response_id}
        conversation_id = (
            conversation_id_from_response(self.model_dump(exclude_none=True))
            or prior_conversation_id
        )
        if conversation_id:
            slim["conversationId"] = conversation_id
        if self.usage is not None:
            slim.update(self.usage.run_output_fields())
        text = self.assistant_text()
        if text:
            slim["answer"] = text
        return slim

    @classmethod
    def invoke_run_output(
        cls,
        *,
        response_id: str,
        display_body: dict[str, Any] | None,
        prior_conversation_id: str | None = None,
    ) -> tuple[dict[str, Any], bool | None]:
        """Build slim Port run output + optional success override from GET body."""
        fallback: dict[str, Any] = {"responseId": response_id}
        if prior_conversation_id:
            fallback["conversationId"] = prior_conversation_id
        if not isinstance(display_body, dict):
            return fallback, None
        try:
            body = cls.model_validate(display_body)
        except ValidationError:
            return fallback, None
        return (
            body.slim_run_output(
                response_id=response_id,
                prior_conversation_id=prior_conversation_id,
            ),
            body.success_override(),
        )
