from aws.core.exporters.rds.db_instance.models import SingleDbInstanceRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "rds.amazonaws.com"


def _db_instance_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:rds:{context.region}:{context.account_id}:db:"
        f"{context.identifier}"
    )


def _extract_db_instance_identifier(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    identifier = request_parameters.get("dbInstanceIdentifier")
    if isinstance(identifier, str):
        return identifier
    identifier = request_parameters.get("dBInstanceIdentifier")
    return identifier if isinstance(identifier, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleDbInstanceRequest:
    return SingleDbInstanceRequest(
        db_instance_identifier=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "DBInstanceArn": _db_instance_arn(context),
        "DBInstanceIdentifier": context.identifier,
    }


RDS_DB_INSTANCE_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateDBInstance": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_db_instance_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "ModifyDBInstance": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_db_instance_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteDBInstance": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_db_instance_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
