from aws.core.exporters.codedeploy.deployment.models import (
    SingleCodeDeployDeploymentRequest,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "codedeploy.amazonaws.com"


def _extract_deployment_id_from_create(detail: CloudTrailDetail) -> str | None:
    response_elements = detail.get("responseElements")
    if not isinstance(response_elements, dict):
        return None

    deployment_id = response_elements.get("deploymentId")
    return deployment_id if isinstance(deployment_id, str) else None


def _extract_deployment_id_from_stop(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters")
    if not isinstance(request_parameters, dict):
        return None

    deployment_id = request_parameters.get("deploymentId")
    return deployment_id if isinstance(deployment_id, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleCodeDeployDeploymentRequest:
    return SingleCodeDeployDeploymentRequest(
        deployment_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "DeploymentId": context.identifier,
    }


CODEDEPLOY_DEPLOYMENT_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateDeployment": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_deployment_id_from_create,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "StopDeployment": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_deployment_id_from_stop,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
