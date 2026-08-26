from aws.core.exporters.eks.cluster.models import SingleEksClusterRequest
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
        f"arn:{partition}:eks:{context.region}:{context.account_id}:"
        f"cluster/{context.identifier}"
    )


def _extract_cluster_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    for key in ("name", "clusterName"):
        identifier = request_parameters.get(key)
        if isinstance(identifier, str):
            return identifier
    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleEksClusterRequest:
    return SingleEksClusterRequest(
        cluster_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "Arn": _cluster_arn(context),
        "Name": context.identifier,
    }


EKS_CLUSTER_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateCluster": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cluster_name,
            event_source="eks.amazonaws.com",
        ),
        "UpdateClusterConfig": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cluster_name,
            event_source="eks.amazonaws.com",
        ),
        "UpdateClusterVersion": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cluster_name,
            event_source="eks.amazonaws.com",
        ),
        "DeleteCluster": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_cluster_name,
            event_source="eks.amazonaws.com",
        ),
    },
)
