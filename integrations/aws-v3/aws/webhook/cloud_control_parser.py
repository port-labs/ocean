"""CloudTrail parser for Cloud Control API mutations on custom kinds.

Handles ``CreateResource`` / ``UpdateResource`` / ``DeleteResource`` calls made
through the Cloud Control API. TypeNames that have a first-class ``ObjectKind``
are skipped: those kinds are kept in sync by their native service events.
"""

import re
from typing import Any

from aws_integration.overrides import AWS_CLOUD_CONTROL_TYPE_PATTERN
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    EventBridgeCloudTrailPayload,
    NormalizedEvent,
)
from aws.core.helpers.types import ObjectKind

CLOUD_CONTROL_EVENT_SOURCE = "cloudcontrolapi.amazonaws.com"

CLOUD_CONTROL_EVENT_ACTIONS: dict[str, CloudTrailEventAction] = {
    "CreateResource": CloudTrailEventAction.UPSERT,
    "UpdateResource": CloudTrailEventAction.UPSERT,
    "DeleteResource": CloudTrailEventAction.DELETE,
}

_FIRST_CLASS_KINDS: frozenset[str] = frozenset(ObjectKind)
_TYPE_NAME_RE = re.compile(AWS_CLOUD_CONTROL_TYPE_PATTERN)


def _get_str(source: Any, *keys: str) -> str | None:
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _progress_event(detail: CloudTrailDetail) -> dict[str, Any]:
    response_elements = detail.get("responseElements")
    if not isinstance(response_elements, dict):
        return {}
    progress_event = response_elements.get("progressEvent") or response_elements.get(
        "ProgressEvent"
    )
    return progress_event if isinstance(progress_event, dict) else {}


def _extract_type_name(detail: CloudTrailDetail) -> str | None:
    return _get_str(
        detail.get("requestParameters"), "typeName", "TypeName" # check this before merging
    ) or _get_str(_progress_event(detail), "typeName", "TypeName")


def _extract_identifier(detail: CloudTrailDetail) -> str | None:
    # CreateResource only knows the identifier once the handler assigns it, so it
    # may be absent from the progress event while the operation is in progress.
    return _get_str(
        detail.get("requestParameters"), "identifier", "Identifier"
    ) or _get_str(_progress_event(detail), "identifier", "Identifier")


def _resolve_custom_kind(detail: CloudTrailDetail) -> str | None:
    if detail.get("eventSource") != CLOUD_CONTROL_EVENT_SOURCE:
        return None
    if detail.get("eventName") not in CLOUD_CONTROL_EVENT_ACTIONS:
        return None

    type_name = _extract_type_name(detail)
    if type_name is None or not _TYPE_NAME_RE.match(type_name):
        return None
    if type_name in _FIRST_CLASS_KINDS:
        return None
    return type_name


def is_supported_cloud_control_event(detail: CloudTrailDetail) -> bool:
    return _resolve_custom_kind(detail) is not None


def parse_cloud_control_event(
    payload: EventBridgeCloudTrailPayload, detail: CloudTrailDetail
) -> NormalizedEvent | None:
    kind = _resolve_custom_kind(detail)
    if kind is None:
        return None

    identifier = _extract_identifier(detail)
    account_id = payload.get("account") or detail.get("recipientAccountId")
    region = payload.get("region") or detail.get("awsRegion")
    if not identifier or not account_id or not region:
        return None

    event_name = detail["eventName"]
    return NormalizedEvent(
        kind=kind,
        identifier=identifier,
        account_id=str(account_id),
        region=str(region),
        action=CLOUD_CONTROL_EVENT_ACTIONS[event_name],
        event_name=event_name,
    )
