import json
from typing import Any

import httpx
from port_ocean.core.models import IntegrationRun

# https://docs.github.com/en/rest/issues/issues#update-an-issue
EDITABLE_ISSUE_STRING_FIELDS = ("title", "body", "state")
VALID_ISSUE_STATE_REASONS = frozenset({"completed", "not_planned", "reopened"})


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


def validate_issue_state_reason(state_reason: str) -> None:
    if state_reason not in VALID_ISSUE_STATE_REASONS:
        raise ValueError(
            f"stateReason must be one of: {', '.join(sorted(VALID_ISSUE_STATE_REASONS))}"
        )


def build_issue_patch_body(
    run: IntegrationRun,
) -> dict[str, str | list[str]]:
    patch_body: dict[str, str | list[str]] = {}
    for key in EDITABLE_ISSUE_STRING_FIELDS:
        value = run.execution_properties.get(key)
        if value is not None:
            patch_body[key] = value
    labels = run.execution_properties.get("labels")
    if labels is not None:
        patch_body["labels"] = labels
    assignees = run.execution_properties.get("assignees")
    if assignees is not None:
        patch_body["assignees"] = assignees
    state_reason = run.execution_properties.get("stateReason")
    if state_reason is not None:
        validate_issue_state_reason(state_reason)
        patch_body["state_reason"] = state_reason
    elif patch_body.get("state") == "closed":
        patch_body["state_reason"] = "completed"
    return patch_body
