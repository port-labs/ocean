from aws.core.exporters.codedeploy.application.models import (
    SingleCodeDeployApplicationRequest,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "codedeploy.amazonaws.com"


def _extract_application_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    application_name = request_parameters.get("applicationName")
    return application_name if isinstance(application_name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleCodeDeployApplicationRequest:
    return SingleCodeDeployApplicationRequest(
        application_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "ApplicationName": context.identifier,
    }


CODEDEPLOY_APPLICATION_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateApplication": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_application_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
