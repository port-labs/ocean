from aws.core.exporters.memorydb.user.models import SingleMemoryDbUserRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

MEMORYDB_CLOUDTRAIL_EVENT_SOURCE = "memorydb.amazonaws.com"


def _user_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:memorydb:{context.region}:{context.account_id}:"
        f"user/{context.identifier}"
    )


def _extract_user_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    if not isinstance(request_parameters, dict):
        return None

    user_name = request_parameters.get("userName")
    return user_name if isinstance(user_name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleMemoryDbUserRequest:
    return SingleMemoryDbUserRequest(
        user_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "ARN": _user_arn(context),
        "Name": context.identifier,
    }


MEMORYDB_USER_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateUser": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_user_name,
            event_source=MEMORYDB_CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateUser": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_user_name,
            event_source=MEMORYDB_CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteUser": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_user_name,
            event_source=MEMORYDB_CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
