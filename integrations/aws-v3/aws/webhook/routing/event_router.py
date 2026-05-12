"""Translate an EventBridge envelope to one or more routing decisions.

The router is intentionally pure: it receives a `dict` (the EB envelope) and
returns a `RoutingDecision` (or list, for multi-id CloudTrail events such as
`RunInstances`), or `None` if the event is unsupported. No I/O, no async, no
side effects. Easy to unit test; keeps `should_process_event` light.

Lookups are driven by the static dispatch tables in `aws.webhook.events`.
"""

from typing import Any, Optional, Union

from pydantic import BaseModel

from aws.core.helpers.types import ObjectKind
from aws.webhook.events import (
    CLOUDTRAIL_DETAIL_TYPE,
    CLOUDTRAIL_EVENT_NAME_TO_ACTION,
    CLOUDTRAIL_EVENT_NAME_TO_KIND,
    DETAIL_TYPE_TO_KIND,
    EC2_STATE_TO_ACTION,
    EventAction,
)


class RoutingDecision(BaseModel):
    """A single (kind, action, identifier) tuple derived from one EB event.

    `identifier` is whatever a per-kind processor will pass to its
    `_build_single_request(...)`. For most kinds this is a string; for
    `RunInstances` the router emits one decision per instance ID, so the
    *processor* never has to handle a list.
    """

    kind: ObjectKind
    action: EventAction
    identifier: str

    class Config:
        frozen = True


class EventRouter:
    """Stateless classifier from EB envelope to `RoutingDecision`s.

    Implemented as a class (rather than a free function) to leave room for
    dependency-injection of alternate dispatch tables in tests, without
    needing to monkey-patch module-level dicts.
    """

    def classify(
        self, payload: dict[str, Any]
    ) -> Optional[Union[RoutingDecision, list[RoutingDecision]]]:
        """Map an EventBridge envelope to one or more routing decisions.

        Returns:
            * A single ``RoutingDecision`` for the common one-resource-per-event
              case (state-change notifications, CT-via-EB
              ``CreateBucket``, ``UpdateFunctionCode*``, ``DeleteService`` …).
            * A ``list[RoutingDecision]`` for CT-via-EB events that reference
              multiple resources in one envelope (notably ``RunInstances``).
            * ``None`` when no supported kind matches; callers must log and
              discard.

        This is a pure normalization boundary. It does not validate webhook
        authenticity, does not call AWS APIs, and does not depend on Ocean. It
        operates solely on the EventBridge envelope shape and the static tables
        in `aws.webhook.events`.
        """
        detail_type = payload.get("detail-type")
        detail = payload.get("detail")
        if not isinstance(detail, dict):
            return None

        # Service-native events (EC2/ECS).
        if isinstance(detail_type, str) and detail_type in DETAIL_TYPE_TO_KIND:
            kind = DETAIL_TYPE_TO_KIND[detail_type]

            if kind == ObjectKind.EC2_INSTANCE:
                identifier = detail.get("instance-id")
                state = detail.get("state")
                if not isinstance(identifier, str) or not isinstance(state, str):
                    return None
                action = EC2_STATE_TO_ACTION.get(state)
                if action is None:
                    return None
                return RoutingDecision(kind=kind, action=action, identifier=identifier)

            if kind == ObjectKind.ECS_SERVICE:
                resources = payload.get("resources")
                if not isinstance(resources, list) or not resources:
                    return None
                identifier = resources[0]
                if not isinstance(identifier, str):
                    return None
                return RoutingDecision(
                    kind=kind, action=EventAction.UPSERT, identifier=identifier
                )

            return None

        # CloudTrail-via-EventBridge events (Lambda/S3 + delete-style ECS + RunInstances).
        if detail_type != CLOUDTRAIL_DETAIL_TYPE:
            return None

        event_name = detail.get("eventName")
        if not isinstance(event_name, str):
            return None
        ct_kind = CLOUDTRAIL_EVENT_NAME_TO_KIND.get(event_name)
        ct_action = CLOUDTRAIL_EVENT_NAME_TO_ACTION.get(event_name)
        if ct_kind is None or ct_action is None:
            return None
        kind = ct_kind
        action = ct_action

        if event_name == "RunInstances":
            response_elements = detail.get("responseElements")
            if not isinstance(response_elements, dict):
                return None
            instances_set = response_elements.get("instancesSet")
            if not isinstance(instances_set, dict):
                return None
            items = instances_set.get("items")
            if not isinstance(items, list) or not items:
                return None

            decisions: list[RoutingDecision] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                instance_id = item.get("instanceId")
                if isinstance(instance_id, str):
                    decisions.append(
                        RoutingDecision(
                            kind=kind, action=action, identifier=instance_id
                        )
                    )
            return decisions or None

        request_parameters = detail.get("requestParameters")
        if not isinstance(request_parameters, dict):
            return None

        if kind == ObjectKind.LAMBDA_FUNCTION:
            identifier = request_parameters.get("functionName")
        elif kind == ObjectKind.S3_BUCKET:
            identifier = request_parameters.get("bucketName")
        elif kind == ObjectKind.ECS_SERVICE:
            service_name = request_parameters.get("service")
            cluster_raw = request_parameters.get("cluster")
            if not isinstance(service_name, str) or not service_name:
                return None
            if not isinstance(cluster_raw, str) or not cluster_raw:
                return None
            # `cluster` may be a short name or a full cluster ARN.
            cluster_marker = ":cluster/"
            if cluster_marker in cluster_raw:
                cluster_name = cluster_raw.split(cluster_marker, 1)[1]
            else:
                cluster_name = cluster_raw
            identifier = f"{cluster_name}/{service_name}"
        else:
            return None

        if not isinstance(identifier, str) or not identifier:
            return None
        return RoutingDecision(kind=kind, action=action, identifier=identifier)
