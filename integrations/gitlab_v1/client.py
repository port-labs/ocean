from typing import Any, Optional, List
from loguru import logger
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError, Timeout


PAGE_SIZE = 100
CLIENT_TIMEOUT = 60

class GitlabHandler:
    def __init__(self, private_token: str):
        self.api_url = "https://gitlab.com/api/v4/"
        self.auth_header = {"PRIVATE-TOKEN": private_token}
        self.client: AsyncClient = http_async_client
        self.client.timeout = Timeout(CLIENT_TIMEOUT)
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
    ) -> List[dict[str, Any]]:
        """Fetch all paginated data from the GitLab API."""
        if params is None:
            params = {}
        params["per_page"] = PAGE_SIZE
        params["page"] = 1
        all_items = []
        while True:
            response = await self._send_api_request(resource, params=params)
            all_items.extend(response)
            if 'next' not in response:
                break
            params["page"] += 1
        return all_items


    async def get_single_resource(
        self, resource_kind: str, resource_id: str
    ) -> dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._send_api_request(f"{resource_kind}/{resource_id}")


    async def fetch_groups(self) -> List[dict]:
        groups = await self.get_paginated_resources("groups")
        return [
            {
                "identifier": group["id"],
                "title": group["name"],
                "blueprint": "gitlabGroup",
                "properties": {
                    "visibility": group["visibility"],
                    "url": group["web_url"],
                    "description": group.get("description", "")
                }
            } for group in groups
        ]


    async def fetch_projects(self) -> List[dict]:
        projects = await self.get_paginated_resources("projects")
        return [
            {
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
            } for project in projects
        ]


    async def fetch_merge_requests(self) -> List[dict]:
        merge_requests = await self.get_paginated_resources("merge_requests")
        return [
            {
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
            } for mr in merge_requests
        ]


    async def fetch_issues(self) -> List[dict]:
        issues = await self.get_paginated_resources("issues")
        return [
            {
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
            } for issue in issues
        ]
