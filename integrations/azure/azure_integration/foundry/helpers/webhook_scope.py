from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from azure_integration.foundry.helpers.responses_catalog import FoundryUsage


def dashboard_webhook_endpoints_url(account_base: str) -> str:
    return f"{account_base}/openai/v1/dashboard/webhook_endpoints"


def response_id_from_webhook_payload(payload: dict[str, Any]) -> str | None:
    event_type = payload.get("type")
    if not isinstance(event_type, str) or not event_type.startswith("response."):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("id", "response_id", "responseId"):
            value = data.get(key)
            if value:
                return str(value)
        nested = data.get("response")
        if isinstance(nested, dict) and nested.get("id"):
            return str(nested["id"])
    return None


def extract_assistant_text_from_response(response: dict[str, Any]) -> str | None:
    # output[] content blocks vary — keep as dicts.
    output = response.get("output")
    if not isinstance(output, list):
        return None
    parts: list[str] = []
    for item in output:
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


def usage_from_response(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {}
    try:
        fields = FoundryUsage.model_validate(usage).row_fields()
    except ValidationError:
        return {}
    mapped: dict[str, int] = {}
    if "prompt_tokens" in fields:
        mapped["inputTokens"] = fields["prompt_tokens"]
    if "completion_tokens" in fields:
        mapped["outputTokens"] = fields["completion_tokens"]
    if "total_tokens" in fields:
        mapped["totalTokens"] = fields["total_tokens"]
    return mapped
