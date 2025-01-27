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


class PubSubAdministratorPerMinutePerProject(PubSubAPI):
    quota_id = "administratorPerMinutePerProject"
    container_type = ContainerType.PROJECT


class ProjectGetRequestsPerMinutePerProject(CloudResourceManagerAPI):
    quota_id = "ProjectV3GetRequestsPerMinutePerProject"
    container_type = ContainerType.PROJECT
