from gcp_core.helpers.ratelimiter.base import (
    GCPResourceRateLimiter,
    ContainerType,
)


class CloudAssetAPI(GCPResourceRateLimiter):
    service = "asset.googleapis.com"


class PubSubAPI(GCPResourceRateLimiter):
    service = "pubsub.googleapis.com"


class AdministratorPerMinutePerProjectAPI(GCPResourceRateLimiter):
    container = ContainerType.PROJECT
    quota_id = "apiAdministratorPerMinutePerProject"


class SearchAllResourcesQpmPerProject(CloudAssetAPI):
    container = ContainerType.PROJECT
    quota_id = "apiSearchAllResourcesQpmPerProject"


class PubSubAdministratorPerMinutePerProject(
    AdministratorPerMinutePerProjectAPI, PubSubAPI
): ...
