from aws.core.exporters.codepipeline.pipeline.models import SinglePipelineRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "codepipeline.amazonaws.com"


def _pipeline_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:codepipeline:{context.region}:{context.account_id}:"
        f"{context.identifier}"
    )


def _extract_pipeline_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if isinstance(request_parameters, dict):
        pipeline_name = request_parameters.get("name")
        if isinstance(pipeline_name, str):
            return pipeline_name

        pipeline = request_parameters.get("pipeline")
        if isinstance(pipeline, dict):
            nested_name = pipeline.get("name")
            if isinstance(nested_name, str):
                return nested_name

    response_elements = detail.get("responseElements")
    if isinstance(response_elements, dict):
        pipeline = response_elements.get("pipeline")
        if isinstance(pipeline, dict):
            nested_name = pipeline.get("name")
            if isinstance(nested_name, str):
                return nested_name

    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SinglePipelineRequest:
    return SinglePipelineRequest(
        pipeline_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "Name": context.identifier,
        "PipelineArn": _pipeline_arn(context),
    }


CODEPIPELINE_PIPELINE_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreatePipeline": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_pipeline_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdatePipeline": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_pipeline_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeletePipeline": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_pipeline_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
