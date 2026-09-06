from aws.core.exporters.ecs.cluster.models import SingleClusterRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "ecs.amazonaws.com"


def _cluster_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:ecs:{context.region}:{context.account_id}:"
        f"cluster/{context.identifier}"
    )


def _extract_cluster_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    identifier = request_parameters.get("clusterName") or request_parameters.get(
        "cluster"
    )
    if not isinstance(identifier, str):
        return None
    if ":cluster/" in identifier:
        return identifier.rsplit("/", 1)[-1]
    return identifier


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleClusterRequest:
    return SingleClusterRequest(
        cluster_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "ClusterArn": _cluster_arn(context),
        "ClusterName": context.identifier,
    }


ECS_CLUSTER_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateCluster": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cluster_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "PutClusterCapacityProviders": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cluster_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteCluster": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_cluster_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
