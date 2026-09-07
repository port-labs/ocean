from aws.core.exporters.ecs.task_definition.models import SingleTaskDefinitionRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "ecs.amazonaws.com"


def _normalize_task_definition_arn(
    task_definition: str, context: LiveEventContext
) -> str:
    if task_definition.startswith("arn:"):
        return task_definition
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:ecs:{context.region}:{context.account_id}:"
        f"task-definition/{task_definition}"
    )


def _extract_task_definition_arn_from_register_response(
    detail: CloudTrailDetail,
) -> str | None:
    response_elements = detail.get("responseElements") or {}
    task_definition = response_elements.get("taskDefinition") or {}
    task_definition_arn = task_definition.get("taskDefinitionArn")
    return task_definition_arn if task_definition_arn else None


def _extract_task_definition_arn_from_deregister_request(
    detail: CloudTrailDetail,
) -> str | None:
    request_parameters = detail.get("requestParameters") or {}
    task_definition = request_parameters.get("taskDefinition")
    return task_definition if task_definition else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleTaskDefinitionRequest:
    return SingleTaskDefinitionRequest(
        task_definition_arn=_normalize_task_definition_arn(context.identifier, context),
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "TaskDefinitionArn": _normalize_task_definition_arn(
            context.identifier, context
        ),
    }


ECS_TASK_DEFINITION_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "RegisterTaskDefinition": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_task_definition_arn_from_register_response,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeregisterTaskDefinition": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_task_definition_arn_from_deregister_request,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
