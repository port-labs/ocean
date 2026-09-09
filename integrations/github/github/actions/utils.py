import json
from typing import Any

import httpx


def build_external_id(workflow_run: dict[str, Any]) -> str:
    return f'gh_{workflow_run["repository"]["owner"]["id"]}_{workflow_run["repository"]["id"]}_{workflow_run["id"]}'


def extract_error_message(response: httpx.Response) -> str:
    """Pull the most useful message out of a GitHub error response.

    GitHub usually answers with ``{"message": ...}``, but proxies and gateways
    can return HTML or plain text, so neither valid JSON nor a dict is
    guaranteed.
    """
    try:
        body = response.json()
    except ValueError:
        body = None

    if isinstance(body, dict):
        message = body.get("message")
        if message:
            return message if isinstance(message, str) else json.dumps(message)

    return response.text.strip() or f"HTTP {response.status_code}"
