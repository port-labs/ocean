from aws.core.exporters.ses.configuration_set.models import SingleConfigurationSetRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "ses.amazonaws.com"


def _extract_configuration_set_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    name = request_parameters.get("configurationSetName")
    return name if isinstance(name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleConfigurationSetRequest:
    return SingleConfigurationSetRequest(
        configuration_set_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "ConfigurationSetName": context.identifier,
    }


_CONFIGURATION_SET_UPSERT_MAPPING = CloudTrailEventMapping(
    CloudTrailEventAction.UPSERT,
    _extract_configuration_set_name,
    event_source=CLOUDTRAIL_EVENT_SOURCE,
)

SES_CONFIGURATION_SET_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateConfigurationSet": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetDeliveryOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetReputationOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetSendingOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetTrackingOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetSuppressionOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetVdmOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "PutConfigurationSetArchivingOptions": _CONFIGURATION_SET_UPSERT_MAPPING,
        "DeleteConfigurationSet": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_configuration_set_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
