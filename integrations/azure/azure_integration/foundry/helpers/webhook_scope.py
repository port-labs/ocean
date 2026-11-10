from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def account_base_url_from_project_endpoint(project_endpoint: str) -> str:
    """Strip ``/api/projects/...`` to the Foundry account host base."""
    parsed = urlparse(project_endpoint.rstrip("/"))
    path = parsed.path or ""
    marker = "/api/projects/"
    if marker in path:
        account_path = path.split(marker, maxsplit=1)[0]
    else:
        account_path = path
    base = f"{parsed.scheme}://{parsed.netloc}{account_path}"
    return base.rstrip("/")


def dashboard_webhook_endpoints_url(account_base: str) -> str:
    return f"{account_base}/openai/v1/dashboard/webhook_endpoints"


def build_response_external_id(response_id: str) -> str:
    return f"foundry_response_{response_id}"


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
    output = response.get("output")
    if not isinstance(output, list):
        return None
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in {"output_text", "text"} and block.get("text"):
                parts.append(str(block["text"]))
    if parts:
        return "\n".join(parts)
    return None


def usage_from_response(response: dict[str, Any]) -> dict[str, int | None]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {}
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
    total = usage.get("total_tokens")
    result: dict[str, int | None] = {}
    if input_tokens is not None:
        result["inputTokens"] = int(input_tokens)
    if output_tokens is not None:
        result["outputTokens"] = int(output_tokens)
    if total is not None:
        result["totalTokens"] = int(total)
    elif (
        result.get("inputTokens") is not None and result.get("outputTokens") is not None
    ):
        result["totalTokens"] = int(result["inputTokens"] or 0) + int(
            result["outputTokens"] or 0
        )
    return result
