from typing import Any

from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "ec2.amazonaws.com"


def _instance_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:ec2:{context.region}:{context.account_id}:instance/"
        f"{context.identifier}"
    )


def _extract_instance_id_from_instances_set(instances_set: Any) -> str | None:
    if not isinstance(instances_set, dict):
        return None
    items = instances_set.get("items", [])
    if not isinstance(items, list) or not items:
        return None
    first_item = items[0]
    if not isinstance(first_item, dict):
        return None
    instance_id = first_item.get("instanceId")
    return instance_id if isinstance(instance_id, str) else None


def _extract_instance_id_from_request_parameters(
    detail: CloudTrailDetail,
) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    return _extract_instance_id_from_instances_set(
        request_parameters.get("instancesSet")
    )


def _extract_run_instances_instance_id(detail: CloudTrailDetail) -> str | None:
    response_elements = detail.get("responseElements")
    if not isinstance(response_elements, dict):
        return None
    return _extract_instance_id_from_instances_set(
        response_elements.get("instancesSet")
    )


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleEC2InstanceRequest:
    return SingleEC2InstanceRequest(
        instance_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "InstanceArn": _instance_arn(context),
        "InstanceId": context.identifier,
    }


EC2_INSTANCE_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "RunInstances": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_run_instances_instance_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "TerminateInstances": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_instance_id_from_request_parameters,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
