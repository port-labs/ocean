from aws.core.exporters.rds.db_cluster.models import SingleDbClusterRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "rds.amazonaws.com"


def _db_cluster_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:rds:{context.region}:{context.account_id}:cluster:"
        f"{context.identifier}"
    )


def _extract_db_cluster_identifier(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    identifier = request_parameters.get("dbClusterIdentifier")
    if isinstance(identifier, str):
        return identifier
    identifier = request_parameters.get("dBClusterIdentifier")
    return identifier if isinstance(identifier, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleDbClusterRequest:
    return SingleDbClusterRequest(
        db_cluster_identifier=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "DBClusterArn": _db_cluster_arn(context),
        "DBClusterIdentifier": context.identifier,
    }


RDS_DB_CLUSTER_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateDBCluster": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_db_cluster_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "ModifyDBCluster": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_db_cluster_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteDBCluster": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_db_cluster_identifier,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
