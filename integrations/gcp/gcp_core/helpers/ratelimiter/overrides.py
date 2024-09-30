from gcp_core.helpers.ratelimiter.base import (
    ContainerType,
    ResourceBoundedSemaphore,
)


class CloudAssetAPI(ResourceBoundedSemaphore):
    service = "cloudasset.googleapis.com"


class PubSubAPI(ResourceBoundedSemaphore):
    service = "pubsub.googleapis.com"


class SearchAllResourcesQpmPerProject(CloudAssetAPI):
    quota_id = "apiSearchAllResourcesQpmPerProject"
    container_type = ContainerType.PROJECT


class PubSubAdministratorPerMinutePerProject(PubSubAPI):
    quota_id = "administratorPerMinutePerProject"
    container_type = ContainerType.PROJECT
