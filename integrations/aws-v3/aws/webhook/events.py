"""Static dispatch tables for AWS live events.

This module owns the *data* used by `aws.webhook.routing.event_router.EventRouter`
to map an EventBridge envelope to a `(kind, action)` pair. There is no logic
here — only constants and an enum — so routing stays a thin lookup and new
kinds are a one-line table entry.

Two shapes of EventBridge events are routed:

1. Service-native events (e.g. ``EC2 Instance State-change Notification``).
   These have a stable, dedicated ``detail-type`` and are mapped via
   :data:`DETAIL_TYPE_TO_KIND`.

2. CloudTrail-via-EventBridge events. These all carry the literal
   ``detail-type == "AWS API Call via CloudTrail"`` and are disambiguated by
   ``detail.eventName`` via :data:`CLOUDTRAIL_EVENT_NAME_TO_KIND`.

EC2 instance state-changes additionally need to map the AWS lifecycle state
(``running`` / ``terminated`` / …) to an UPSERT or DELETE; see
:data:`EC2_STATE_TO_ACTION`.

CloudTrail event names map directly to UPSERT or DELETE via
:data:`CLOUDTRAIL_EVENT_NAME_TO_ACTION`.
"""

from enum import StrEnum

from aws.core.helpers.types import ObjectKind


class EventAction(StrEnum):
    """Whether an event implies an upsert or a delete in the Port catalog."""

    UPSERT = "upsert"
    DELETE = "delete"


CLOUDTRAIL_DETAIL_TYPE: str = "AWS API Call via CloudTrail"
"""The literal `detail-type` carried by every CT-via-EB event."""


DETAIL_TYPE_TO_KIND: dict[str, ObjectKind] = {
    # EC2 service-native events
    "EC2 Instance State-change Notification": ObjectKind.EC2_INSTANCE,
    # ECS service-native events
    "ECS Service Action": ObjectKind.ECS_SERVICE,
    "ECS Deployment State Change": ObjectKind.ECS_SERVICE,
}


CLOUDTRAIL_EVENT_NAME_TO_KIND: dict[str, ObjectKind] = {
    # Lambda CloudTrail (via EventBridge)
    "CreateFunction20150331": ObjectKind.LAMBDA_FUNCTION,
    "UpdateFunctionCode20150331": ObjectKind.LAMBDA_FUNCTION,
    "UpdateFunctionConfiguration20150331": ObjectKind.LAMBDA_FUNCTION,
    "DeleteFunction20150331": ObjectKind.LAMBDA_FUNCTION,
    # S3 CloudTrail (via EventBridge)
    "CreateBucket": ObjectKind.S3_BUCKET,
    "DeleteBucket": ObjectKind.S3_BUCKET,
    # EC2 CloudTrail (via EventBridge)
    "RunInstances": ObjectKind.EC2_INSTANCE,
    # ECS CloudTrail (via EventBridge) - deletion path
    "DeleteService": ObjectKind.ECS_SERVICE,
}


EC2_STATE_TO_ACTION: dict[str, EventAction] = {
    # UPSERT states
    "pending": EventAction.UPSERT,
    "running": EventAction.UPSERT,
    "stopping": EventAction.UPSERT,
    "stopped": EventAction.UPSERT,
    # DELETE states
    "shutting-down": EventAction.DELETE,
    "terminated": EventAction.DELETE,
}


CLOUDTRAIL_EVENT_NAME_TO_ACTION: dict[str, EventAction] = {
    # Lambda
    "CreateFunction20150331": EventAction.UPSERT,
    "UpdateFunctionCode20150331": EventAction.UPSERT,
    "UpdateFunctionConfiguration20150331": EventAction.UPSERT,
    "DeleteFunction20150331": EventAction.DELETE,
    # S3
    "CreateBucket": EventAction.UPSERT,
    "DeleteBucket": EventAction.DELETE,
    # EC2
    "RunInstances": EventAction.UPSERT,
    # ECS
    "DeleteService": EventAction.DELETE,
}
