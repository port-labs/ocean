import json
from collections.abc import Mapping
from typing import Any

import httpx

from github.helpers.exceptions import InvalidActionParametersException

EDIT_ISSUE_SCALAR_PROPERTY_KEYS = ("title", "body", "state")

VALID_ISSUE_CLOSE_STATE_REASONS = frozenset({"completed", "not_planned"})

DEFAULT_ISSUE_CLOSE_STATE_REASON = "completed"


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


def resolve_issue_close_state_reason(
    execution_properties: Mapping[str, Any],
    *,
    key: str = "stateReason",
    default: str = DEFAULT_ISSUE_CLOSE_STATE_REASON,
) -> str:
    state_reason = execution_properties.get(key, default)
    if state_reason not in VALID_ISSUE_CLOSE_STATE_REASONS:
        raise InvalidActionParametersException(
            "stateReason must be completed or not_planned"
        )
    return state_reason


def build_edit_issue_patch_body(
    execution_properties: Mapping[str, Any],
) -> dict[str, str | list[str]]:
    patch_body: dict[str, str | list[str]] = {}
    for key in EDIT_ISSUE_SCALAR_PROPERTY_KEYS:
        value = execution_properties.get(key)
        if value is not None:
            patch_body[key] = value
    labels = execution_properties.get("labels")
    if labels is not None:
        patch_body["labels"] = labels
    assignees = execution_properties.get("assignees")
    if assignees is not None:
        patch_body["assignees"] = assignees

    if patch_body.get("state") == "closed":
        patch_body["state_reason"] = resolve_issue_close_state_reason(
            execution_properties
        )

    if not patch_body:
        raise InvalidActionParametersException(
            "At least one field to update is required (title, body, state, labels, or assignees)"
        )

    return patch_body


def build_close_issue_patch_body(
    execution_properties: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "state": "closed",
        "state_reason": resolve_issue_close_state_reason(execution_properties),
    }
