import json
from collections.abc import Mapping
from typing import Any

import httpx

from github.helpers.exceptions import InvalidActionParametersException

# https://docs.github.com/en/rest/issues/issues#update-an-issue
EDIT_ISSUE_SCALAR_PROPERTY_KEYS = ("title", "body")

VALID_CLOSE_REASONS = frozenset({"completed", "not_planned", "duplicate"})

DEFAULT_CLOSE_REASON = "completed"


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


def build_create_issue_body(
    execution_properties: Mapping[str, Any],
) -> dict[str, str | int | list[str]]:
    issue_body: dict[str, str | int | list[str]] = {
        "title": execution_properties["title"]
    }
    body = execution_properties.get("body")
    if body:
        issue_body["body"] = body
    labels = execution_properties.get("labels")
    if labels:
        issue_body["labels"] = labels
    assignees = execution_properties.get("assignees")
    if assignees:
        issue_body["assignees"] = assignees
    milestone = execution_properties.get("milestone")
    if milestone is not None:
        issue_body["milestone"] = milestone
    return issue_body


def resolve_close_reason(
    execution_properties: Mapping[str, Any],
) -> str:
    state_reason = execution_properties.get("stateReason", DEFAULT_CLOSE_REASON)
    if state_reason not in VALID_CLOSE_REASONS:
        raise InvalidActionParametersException(
            f"stateReason must be one of: {', '.join(sorted(VALID_CLOSE_REASONS))}"
        )
    return state_reason


def build_edit_issue_patch_body(
    execution_properties: Mapping[str, Any],
) -> dict[str, str | int | list[str] | None]:
    patch_body: dict[str, str | int | list[str] | None] = {}
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
    if "milestone" in execution_properties:
        patch_body["milestone"] = execution_properties["milestone"]

    if not patch_body:
        raise InvalidActionParametersException(
            "At least one field to update is required (title, body, labels, assignees, or milestone)"
        )

    return patch_body


def build_close_issue_patch_body(
    execution_properties: Mapping[str, Any],
) -> dict[str, str | int]:
    state_reason = resolve_close_reason(execution_properties)
    json_data: dict[str, str | int] = {
        "state": "closed",
        "state_reason": state_reason,
    }

    if state_reason == "duplicate":
        duplicate_issue_id = execution_properties.get("duplicateIssueId")
        if duplicate_issue_id is None:
            raise InvalidActionParametersException(
                "duplicateIssueId is required when stateReason is 'duplicate'"
            )
        json_data["duplicate_issue_id"] = duplicate_issue_id

    return json_data
