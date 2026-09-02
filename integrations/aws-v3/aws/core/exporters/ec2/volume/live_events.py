from aws.core.exporters.ec2.volume.models import SingleEbsVolumeRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "ec2.amazonaws.com"


def _extract_volume_id(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if isinstance(request_parameters, dict):
        volume_id = request_parameters.get("volumeId")
        if isinstance(volume_id, str):
            return volume_id

        modify_volume_request = request_parameters.get("ModifyVolumeRequest")
        if isinstance(modify_volume_request, dict):
            modify_volume_id = modify_volume_request.get("VolumeId")
            if isinstance(modify_volume_id, str):
                return modify_volume_id

    response_elements = detail.get("responseElements")
    if isinstance(response_elements, dict):
        response_volume_id = response_elements.get("volumeId")
        if isinstance(response_volume_id, str):
            return response_volume_id

        modify_volume_response = response_elements.get("ModifyVolumeResponse")
        if isinstance(modify_volume_response, dict):
            volume_modification = modify_volume_response.get("volumeModification")
            if isinstance(volume_modification, dict):
                modification_volume_id = volume_modification.get("volumeId")
                if isinstance(modification_volume_id, str):
                    return modification_volume_id

    return None


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
            _extract_volume_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "ModifyVolume": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_volume_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteVolume": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_volume_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
