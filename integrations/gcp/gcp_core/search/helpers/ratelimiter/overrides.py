from gcp_core.search.helpers.ratelimiter.base import GCPResourceRateLimiter


class CloudAssetAPI(GCPResourceRateLimiter):
    service = "asset.googleapis.com"


class SearchAllResourcesQpmPerProject(CloudAssetAPI):
    container = "projects"
    quota_id = "apiSearchAllResourcesQpmPerProject"
