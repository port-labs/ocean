from aws.core.exporters.codebuild.build_run.models import SingleBuildRunRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "codebuild.amazonaws.com"


def _build_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:codebuild:{context.region}:{context.account_id}:"
        f"build/{context.identifier}"
    )


def _extract_build_id_from_start(detail: CloudTrailDetail) -> str | None:
    response_elements = detail.get("responseElements")
    if not isinstance(response_elements, dict):
        return None

    build = response_elements.get("build")
    if not isinstance(build, dict):
        return None

    build_id = build.get("id")
    return build_id if isinstance(build_id, str) else None


def _extract_build_id_from_stop(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters")
    if not isinstance(request_parameters, dict):
        return None

    build_id = request_parameters.get("id")
    return build_id if isinstance(build_id, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleBuildRunRequest:
    return SingleBuildRunRequest(
        build_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "Arn": _build_arn(context),
        "Id": context.identifier,
    }


CODEBUILD_BUILD_RUN_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "StartBuild": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_build_id_from_start,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "StopBuild": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_build_id_from_stop,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "RetryBuild": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_build_id_from_start,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
