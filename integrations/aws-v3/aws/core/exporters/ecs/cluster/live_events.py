from aws.core.exporters.ecs.cluster.models import SingleClusterRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper


def _cluster_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:ecs:{context.region}:{context.account_id}:"
        f"cluster/{context.identifier}"
    )


def _extract_cluster_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    for key in ("clusterName", "cluster"):
        identifier = request_parameters.get(key)
        if isinstance(identifier, str):
            if ":cluster/" in identifier:
                return identifier.rsplit("/", 1)[-1]
            return identifier
    return None


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
            event_source="ecs.amazonaws.com",
        ),
        "PutClusterCapacityProviders": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cluster_name,
            event_source="ecs.amazonaws.com",
        ),
        "DeleteCluster": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_cluster_name,
            event_source="ecs.amazonaws.com",
        ),
    },
)
