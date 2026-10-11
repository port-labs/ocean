from gcp_core.helpers.ratelimiter.base import (
    ContainerType,
    ResourceBoundedSemaphore,
)


class CloudAssetAPI(ResourceBoundedSemaphore):
    service = "cloudasset.googleapis.com"


class PubSubAPI(ResourceBoundedSemaphore):
    service = "pubsub.googleapis.com"


class CloudResourceManagerAPI(ResourceBoundedSemaphore):
    service = "cloudresourcemanager.googleapis.com"


class SearchAllResourcesQpmPerProject(CloudAssetAPI):
    quota_id = "apiSearchAllResourcesQpmPerProject"
    container_type = ContainerType.PROJECT


class SearchAllIamPoliciesQpmPerProject(CloudAssetAPI):
    quota_id = "apiSearchAllIamPoliciesQpmPerProject"
    container_type = ContainerType.PROJECT


class ListAssetsQpmPerProject(CloudAssetAPI):
    quota_id = "apiListAssetsQpmPerProject"
    container_type = ContainerType.PROJECT
    # Documented ListAssets default is 100/minute per consumer project.
    # Keep the fallback under that quota when Cloud Quotas cannot be read.
    _default_quota = 100


class PubSubAdministratorPerMinutePerProject(PubSubAPI):
    quota_id = "administratorPerMinutePerProject"
    container_type = ContainerType.PROJECT


class ProjectGetRequestsPerMinutePerProject(CloudResourceManagerAPI):
    quota_id = "ProjectV3GetRequestsPerMinutePerProject"
    container_type = ContainerType.PROJECT
