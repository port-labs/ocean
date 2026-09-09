from aws.core.exporters.codedeploy.deployment_group.models import (
    SingleCodeDeployDeploymentGroupRequest,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "codedeploy.amazonaws.com"
DEPLOYMENT_GROUP_IDENTIFIER_SEPARATOR = "/"


def _parse_deployment_group_identifier(identifier: str) -> tuple[str, str] | None:
    application_name, separator, deployment_group_name = identifier.partition(
        DEPLOYMENT_GROUP_IDENTIFIER_SEPARATOR
    )
    if not separator or not application_name or not deployment_group_name:
        return None
    return application_name, deployment_group_name


def _extract_deployment_group_identifier(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    application_name = request_parameters.get("applicationName")
    deployment_group_name = request_parameters.get("deploymentGroupName")
    if not isinstance(application_name, str) or not isinstance(
        deployment_group_name, str
    ):
        return None

    return (
        f"{application_name}{DEPLOYMENT_GROUP_IDENTIFIER_SEPARATOR}"
        f"{deployment_group_name}"
    )


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleCodeDeployDeploymentGroupRequest:
    parsed = _parse_deployment_group_identifier(context.identifier)
    if parsed is None:
        raise ValueError(
            "Invalid CodeDeploy deployment group identifier: " f"{context.identifier}"
        )

    application_name, deployment_group_name = parsed
    return SingleCodeDeployDeploymentGroupRequest(
        application_name=application_name,
        deployment_group_name=deployment_group_name,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    parsed = _parse_deployment_group_identifier(context.identifier)
    if parsed is None:
        return {}

    application_name, deployment_group_name = parsed
    return {
        "ApplicationName": application_name,
        "DeploymentGroupName": deployment_group_name,
    }


CODEDEPLOY_DEPLOYMENT_GROUP_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateDeploymentGroup": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_deployment_group_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
