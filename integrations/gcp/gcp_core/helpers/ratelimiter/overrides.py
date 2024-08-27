from gcp_core.helpers.ratelimiter.base import (
    GCPResourceRateLimiter,
    ContainerType,
)


class CloudAssetAPI(GCPResourceRateLimiter):
    service = "asset.googleapis.com"


class PubSubAPI(GCPResourceRateLimiter):
    service = "pubsub.googleapis.com"


class AdministratorPerMinutePerProject(GCPResourceRateLimiter):
    quota_id = "administratorPerMinutePerProject"


class SearchAllResourcesQpmPerProject(CloudAssetAPI):
    container = ContainerType.PROJECT
    quota_id = "apiSearchAllResourcesQpmPerProject"


class PubSubAdministratorPerMinutePerProject(
    AdministratorPerMinutePerProject, PubSubAPI
):
    container = ContainerType.PROJECT
