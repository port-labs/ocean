from typing import Any, Optional, List, AsyncGenerator
from loguru import logger
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError

PAGE_SIZE = 100
CLIENT_TIMEOUT = 60

class GitlabHandler:
    def __init__(self, private_token: str):
        self.api_url = "https://gitlab.com/api/v4/"
        self.auth_header = {"PRIVATE-TOKEN": private_token}
        self.client = http_async_client
        self.client.timeout = CLIENT_TIMEOUT
        self.client.headers.update(self.auth_header)

    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send a request to the GitLab API."""
        url = f"{self.api_url}{endpoint}"
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            logger.error(
                f"HTTP error for URL: {url} - Status code: {e.response.status_code} - Response: {e.response.text}"
            )
            raise

    async def get_paginated_resources(
        self,
        resource: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch all paginated data from the GitLab API."""
        if params is None:
            params = {}
        params["per_page"] = PAGE_SIZE
        params["page"] = 1

        while True:
            response = await self._send_api_request(resource, params=params)
            for item in response:
                yield item

            if 'X-Next-Page' not in response.headers or not response.headers['X-Next-Page']:
                break

            # params["page"] = int(response.headers['X-Next-Page'])

    async def get_single_resource(
        self, resource_kind: str, resource_id: str
    ) -> dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._send_api_request(f"{resource_kind}/{resource_id}")

    async def fetch_groups(self) -> AsyncGenerator[dict, None]:
        """Fetch GitLab groups using an async generator."""
        async for group in self.get_paginated_resources("groups"):
            yield {
                "identifier": group["id"],
                "title": group["name"],
                "blueprint": "gitlabGroup",
                "properties": {
                    "visibility": group["visibility"],
                    "url": group["web_url"],
                    "description": group.get("description", "")
                }
            }

    async def fetch_projects(self) -> AsyncGenerator[dict, None]:
        """Fetch GitLab projects using an async generator."""
        async for project in self.get_paginated_resources("projects"):
            yield {
                "identifier": project["id"],
                "title": project["name"],
                "blueprint": "gitlabProject",
                "properties": {
                    "url": project["web_url"],
                    "description": project.get("description", ""),
                    "language": project.get("language", ""),
                    "namespace": project["namespace"]["full_path"],
                    "fullPath": project["path_with_namespace"],
                    "defaultBranch": project.get("default_branch", "")
                },
                "relations": {
                    "group": {
                        "target": project["namespace"]["id"],
                        "blueprint": "gitlabGroup"
                    }
                }
            }

    async def fetch_merge_requests(self) -> AsyncGenerator[dict, None]:
        """Fetch GitLab merge requests using an async generator."""
        async for mr in self.get_paginated_resources("merge_requests"):
            yield {
                "identifier": mr["id"],
                "title": mr["title"],
                "blueprint": "gitlabMergeRequest",
                "properties": {
                    "creator": mr["author"]["username"],
                    "status": mr["state"],
                    "createdAt": mr["created_at"],
                    "updatedAt": mr.get("updated_at", ""),
                    "mergedAt": mr.get("merged_at", ""),
                    "link": mr["web_url"],
                    "reviewers": [reviewer["username"] for reviewer in mr.get("reviewers", [])]
                },
                "relations": {
                    "service": {
                        "target": mr["project_id"],
                        "blueprint": "project"
                    }
                }
            }

    async def fetch_issues(self) -> AsyncGenerator[dict, None]:
        """Fetch GitLab issues using an async generator."""
        async for issue in self.get_paginated_resources("issues"):
            yield {
                "identifier": issue["id"],
                "title": issue["title"],
                "blueprint": "gitlabIssue",
                "properties": {
                    "link": issue["web_url"],
                    "description": issue.get("description", ""),
                    "createdAt": issue["created_at"],
                    "closedAt": issue.get("closed_at", ""),
                    "updatedAt": issue.get("updated_at", ""),
                    "creator": issue["author"]["username"],
                    "status": issue["state"],
                    "labels": issue.get("labels", [])
                },
                "relations": {
                    "service": {
                        "target": issue["project_id"],
                        "blueprint": "project"
                    }
                }
            }
