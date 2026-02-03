from dataclasses import dataclass


HARBOR_API_VERSION = "v2.0"
HARBOR_API_BASE_PATH = f"/api/{HARBOR_API_VERSION}"


MAX_CONCURRENT_REQUESTS = 10
DEFAULT_PAGE_SIZE = 25  # Harbor's default max page size
REQUEST_TIMEOUT = 2 * 60  # 2 minutes


@dataclass(frozen=True)
class HarborEndpoints:
    projects = f"{HARBOR_API_BASE_PATH}/projects"
    users = f"{HARBOR_API_BASE_PATH}/users"
    repositories = f"{HARBOR_API_BASE_PATH}/projects/{{project_name}}/repositories"
    artifacts = f"{HARBOR_API_BASE_PATH}/projects/{{project_name}}/repositories/{{repository_name}}/artifacts"


harbor_endpoints = HarborEndpoints()
