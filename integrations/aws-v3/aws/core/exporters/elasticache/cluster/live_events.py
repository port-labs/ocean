from aws.core.exporters.elasticache.cluster.models import SingleCacheClusterRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "elasticache.amazonaws.com"


def _cache_cluster_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:elasticache:{context.region}:{context.account_id}:cluster:"
        f"{context.identifier}"
    )


def _extract_cache_cluster_id(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    cache_cluster_id = request_parameters.get("cacheClusterId")
    return cache_cluster_id if isinstance(cache_cluster_id, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleCacheClusterRequest:
    return SingleCacheClusterRequest(
        cache_cluster_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "ARN": _cache_cluster_arn(context),
        "CacheClusterId": context.identifier,
    }


ELASTICACHE_CLUSTER_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateCacheCluster": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cache_cluster_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "ModifyCacheCluster": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_cache_cluster_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteCacheCluster": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_cache_cluster_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
