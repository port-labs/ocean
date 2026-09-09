from aws.core.exporters.codebuild.project.models import SingleCodeBuildProjectRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "codebuild.amazonaws.com"


def _project_name_from_identifier(identifier: str) -> str:
    if not identifier.startswith("arn:"):
        return identifier

    resource = identifier.rsplit(":", maxsplit=1)[-1]
    if resource.startswith("project/"):
        return resource[len("project/") :]
    return identifier


def _project_arn(context: LiveEventContext) -> str:
    identifier = _project_name_from_identifier(context.identifier)
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:codebuild:{context.region}:{context.account_id}:"
        f"project/{identifier}"
    )


def _extract_project_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    project_name = request_parameters.get("name")
    if not isinstance(project_name, str):
        return None

    return _project_name_from_identifier(project_name)


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleCodeBuildProjectRequest:
    return SingleCodeBuildProjectRequest(
        project_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    project_name = _project_name_from_identifier(context.identifier)
    return {
        "Arn": _project_arn(context),
        "Name": project_name,
    }


CODEBUILD_PROJECT_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateProject": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_project_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateProject": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_project_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteProject": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_project_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
