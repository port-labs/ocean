from aws.core.exporters.codepipeline.pipeline_execution.models import (
    SinglePipelineExecutionRequest,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "codepipeline.amazonaws.com"
PIPELINE_EXECUTION_IDENTIFIER_SEPARATOR = "/"


def _encode_pipeline_execution_identifier(
    pipeline_name: str, pipeline_execution_id: str
) -> str:
    return (
        f"{pipeline_name}{PIPELINE_EXECUTION_IDENTIFIER_SEPARATOR}"
        f"{pipeline_execution_id}"
    )


def _parse_pipeline_execution_identifier(identifier: str) -> tuple[str, str]:
    pipeline_name, pipeline_execution_id = identifier.split(
        PIPELINE_EXECUTION_IDENTIFIER_SEPARATOR, maxsplit=1
    )
    return pipeline_name, pipeline_execution_id


def _extract_pipeline_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters")
    if not isinstance(request_parameters, dict):
        return None

    pipeline_name = request_parameters.get("name")
    if isinstance(pipeline_name, str):
        return pipeline_name

    alternate_name = request_parameters.get("pipelineName")
    return alternate_name if isinstance(alternate_name, str) else None


def _extract_pipeline_execution_identifier_from_start(
    detail: CloudTrailDetail,
) -> str | None:
    pipeline_name = _extract_pipeline_name(detail)
    if pipeline_name is None:
        return None

    response_elements = detail.get("responseElements")
    if not isinstance(response_elements, dict):
        return None

    pipeline_execution_id = response_elements.get("pipelineExecutionId")
    if not isinstance(pipeline_execution_id, str):
        return None

    return _encode_pipeline_execution_identifier(pipeline_name, pipeline_execution_id)


def _extract_pipeline_execution_identifier_from_stop(
    detail: CloudTrailDetail,
) -> str | None:
    request_parameters = detail.get("requestParameters")
    if not isinstance(request_parameters, dict):
        return None

    pipeline_name = request_parameters.get("pipelineName")
    pipeline_execution_id = request_parameters.get("pipelineExecutionId")
    if not isinstance(pipeline_name, str) or not isinstance(pipeline_execution_id, str):
        return None

    return _encode_pipeline_execution_identifier(pipeline_name, pipeline_execution_id)


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SinglePipelineExecutionRequest:
    pipeline_name, pipeline_execution_id = _parse_pipeline_execution_identifier(
        context.identifier
    )
    return SinglePipelineExecutionRequest(
        pipeline_name=pipeline_name,
        pipeline_execution_id=pipeline_execution_id,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    pipeline_name, pipeline_execution_id = _parse_pipeline_execution_identifier(
        context.identifier
    )
    return {
        "PipelineName": pipeline_name,
        "PipelineExecutionId": pipeline_execution_id,
    }


CODEPIPELINE_PIPELINE_EXECUTION_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "StartPipelineExecution": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_pipeline_execution_identifier_from_start,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "StopPipelineExecution": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_pipeline_execution_identifier_from_stop,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
