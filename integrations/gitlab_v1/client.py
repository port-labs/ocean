import asyncio
from typing import Any, Optional, AsyncGenerator, Dict
from loguru import logger
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError, Response
from gitlab_rate_limiter import GitLabRateLimiter
from datetime import datetime, timezone


PAGE_SIZE = 100
CLIENT_TIMEOUT = 60

class GitlabHandler:
    def __init__(self, private_token: str, base_url: str = "https://gitlab.com/api/v4/"):
        self.base_url = base_url
        self.auth_header = {"PRIVATE-TOKEN": private_token}
        self.client = http_async_client
        self.client.timeout = CLIENT_TIMEOUT
        self.client.headers.update(self.auth_header)
        self.rate_limiter = GitLabRateLimiter()
        self.retries = 3
        self.base_delay = 1


    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.retries):
            await self.rate_limiter.acquire()
            try:
                logger.debug(f"Sending {method} request to {url}")
                response = await self.client.request(
                    method,
                    url,
                    params=params,
                    json=json_data
                    )
                response.raise_for_status()
                logger.debug(f"Received response from {url}: {response.status_code}")
                self._update_rate_limit(response)
                return response.json()
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get('Retry-After', str(self.base_delay * (2 ** attempt))))
                    logger.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"HTTP error for URL: {url} - Status code: {e.response.status_code}")
                    raise
            except asyncio.TimeoutError:
                logger.error(f"Request to {url} timed out.")
                raise


        logger.error(f"Max retries ({self.retries}) exceeded for {url}")
        raise Exception("Max retries exceeded")


    def _update_rate_limit(self, response: Response):
        headers = response.headers
        self.rate_limiter.update_limits(headers)

        remaining = int(headers.get('RateLimit-Remaining', '0'))
        limit = int(headers.get('RateLimit-Limit', '0'))
        reset_time = datetime.fromtimestamp(int(headers.get('RateLimit-Reset', '0')), tz=timezone.utc)

        logger.info(f"Rate limit: {remaining}/{limit} requests remaining. Resets at {reset_time}")


    async def get_paginated_resources(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        params = params or {}
        params["per_page"] = PAGE_SIZE
        params["page"] = 1



        while True:
            logger.debug(f"Fetching page {params['page']} for resource '{resource}'")
            response = await self._send_api_request(resource, params=params)

            if not isinstance(response, list):
                logger.error(f"Expected a list response for resource '{resource}', got {type(response)}")
                break


            if not response:
                logger.debug(f"No more records to fetch for resource '{resource}'.")
                break

            for item in response:
                yield item

            if len(response) < PAGE_SIZE:
                logger.debug(f"Last page reached for resource '{resource}', no more data.")
                break


            params["page"] += 1




    async def get_single_resource(
        self, resource_kind: str, resource_id: str
    ) -> Dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._send_api_request(f"{resource_kind}/{resource_id}")


    async def fetch_groups(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch GitLab groups using an async generator."""
        async for group in self.get_paginated_resources("groups", params={"owned": False}):

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


    async def fetch_projects(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch GitLab projects using an async generator."""
        async for project in self.get_paginated_resources("projects", params={"owned": True}):
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


    async def fetch_merge_requests(self) -> AsyncGenerator[Dict[str, Any], None]:
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


    async def fetch_issues(self) -> AsyncGenerator[Dict[str, Any], None]:
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
