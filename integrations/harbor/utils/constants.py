from dataclasses import dataclass


HARBOUR_API_VERSION = "v2.0"
HARBOUR_API_BASE_PATH = f"/api/{HARBOUR_API_VERSION}"


MAX_CONCURRENT_REQUESTS = 10
DEFAULT_PAGE_SIZE = 25  # Harbor's default max page size
REQUEST_TIMEOUT = 2 * 60  # 2 minutes


@dataclass(frozen=True)
class HarborEndpoints:
    projects = f"{HARBOUR_API_BASE_PATH}/projects"
    users = f"{HARBOUR_API_BASE_PATH}/users"
    repositories = f"{HARBOUR_API_BASE_PATH}/projects/{{project_name}}/repositories"
    artifacts = f"{HARBOUR_API_BASE_PATH}/projects/{{project_name}}/repositories/{{repository_name}}/artifacts"


harbor_endpoints = HarborEndpoints()
