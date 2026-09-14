from aws.core.exporters.ec2.volume.models import SingleEbsVolumeRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "ec2.amazonaws.com"


def _extract_volume_id_from_delete_request(detail: CloudTrailDetail) -> str | None:
    """DeleteVolume: requestParameters.volumeId."""
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    volume_id = request_parameters.get("volumeId")
    return volume_id if isinstance(volume_id, str) else None


def _extract_volume_id_from_modify_request(detail: CloudTrailDetail) -> str | None:
    """ModifyVolume: requestParameters.ModifyVolumeRequest.VolumeId."""
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    modify_volume_request = request_parameters.get("ModifyVolumeRequest")
    if not isinstance(modify_volume_request, dict):
        return None

    volume_id = modify_volume_request.get("VolumeId")
    return volume_id if isinstance(volume_id, str) else None


def _extract_volume_id_from_create_response(detail: CloudTrailDetail) -> str | None:
    """CreateVolume: responseElements.volumeId."""
    response_elements = detail.get("responseElements")
    if not isinstance(response_elements, dict):
        return None

    volume_id = response_elements.get("volumeId")
    return volume_id if isinstance(volume_id, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleEbsVolumeRequest:
    return SingleEbsVolumeRequest(
        volume_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "VolumeId": context.identifier,
    }


EC2_VOLUME_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateVolume": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_volume_id_from_create_response,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "ModifyVolume": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_volume_id_from_modify_request,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteVolume": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_volume_id_from_delete_request,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
