import asyncio
import time
from typing import Any, AsyncGenerator, Dict, Optional, Tuple, List

import httpx
from port_ocean.utils import http_async_client
from loguru import logger

ENDPOINT_TEMPLATES = {
    "teams":         "/orgs/{org}/teams/{team_slug}",
    "workflows":     "/repos/{owner}/{repo}/actions/workflows",
    "repository":    "/repos/{owner}/{repo}",
    "issue":         "/repos/{owner}/{repo}/issues/{issue_number}",
    "pull_request":  "/repos/{owner}/{repo}/pulls/{pull_number}",
    "workflow_run":  "/repos/{owner}/{repo}/actions/runs/{run_id}",
    "commit":        "/repos/{owner}/{repo}/commits/{commit_sha}",
    "org_repos":     "/orgs/{org}/repos",
    "pull_requests": "/repos/{owner}/{repo}/pulls",
    "issues":        "/repos/{owner}/{repo}/issues",
    "teamsFull":      "/orgs/{org}/teams"
}

class GitHubClient:
    def __init__(
        self,
        token: str,
        org: str,
        base_url: Optional[str] = None,
        max_retries: int = 3
    ) -> None:
        self.token = token
        self.org = org
        self.base_url = base_url or "https://api.github.com"
        self.client = http_async_client
        self.client.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        })
        self.max_concurrent_requests = 10
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.max_retries = max_retries

    @staticmethod
    def _handle_rate_limit(response: httpx.Response) -> float:
        """Return how many seconds to wait if rate-limited, else 0.0."""
        if response.status_code in (429, 403) and "X-RateLimit-Remaining" in response.headers:
            remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
            if remaining == 0:
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait_time = max(reset_time - int(time.time()), 1)
                logger.warning(f"Rate limit reached. Waiting {wait_time}s before retrying.")
                return wait_time
        return 0.0

    async def _send_api_request(
        self,
        method: str,
        url: str,
        query_params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        attempt: int = 1
    ) -> Tuple[List[Dict[str, Any]], httpx.Response]:
        """
        Send an HTTP request, returning (parsed_json_as_list, raw_response).
        If the JSON is actually a dict, we convert it to a single-item list so we keep a consistent type.
        """
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=json_data,
                )

            wait_time = self._handle_rate_limit(response)
            if wait_time > 0:
                if attempt < self.max_retries:
                    logger.warning(f"Rate-limited {wait_time:.1f}s; retry {attempt}/{self.max_retries} => {method} {url}")
                    await asyncio.sleep(wait_time)
                    return await self._send_api_request(method, url, query_params, json_data, attempt + 1)
                else:
                    logger.error(f"Exceeded max retries (rate-limit) => {method} {url}")
                    response.raise_for_status()

            response.raise_for_status()
            json_result = response.json()
            if isinstance(json_result, list):
                return json_result, response
            elif isinstance(json_result, dict):
                # Convert dict to single-item list
                return [json_result], response
            else:
                # Unexpected type - log & treat as empty
                logger.debug(f"Unexpected JSON type: {type(json_result)} => returning empty list")
                return [], response

        except httpx.HTTPError as exc:
            logger.error(f"HTTP request error (attempt {attempt}) => {method} {url}: {str(exc)}")
            if attempt < self.max_retries:
                logger.warning(f"Retrying (attempt {attempt + 1} of {self.max_retries})")
                return await self._send_api_request(method, url, query_params, json_data, attempt + 1)
            raise

    async def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Yields an entire page of data (always a list[dict]) each iteration,
        using 'Link' headers for pagination.
        """
        url = f"{self.base_url}{endpoint}"

        while url:
            page_list, resp = await self._send_api_request("GET", url, query_params=params)
            yield page_list

            # Attempt to parse next page from Link header
            link_header = resp.headers.get("Link", "")
            url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    url_segment = part.split(";")[0].strip()
                    url = url_segment.strip("<>")
                    break

    async def fetch_resource(
        self,
        resource_type: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields single dictionaries at each iteration.
        - We call get_paginated(...), which yields list[dict] for each page.
        - We then yield each dict individually.
        This allows "async for item in client.fetch_resource(...): item.get('name')"
        """
        if resource_type not in ENDPOINT_TEMPLATES:
            logger.error(f"Unknown resource type: {resource_type}")
            return

        endpoint_template = ENDPOINT_TEMPLATES[resource_type]
        endpoint = endpoint_template.format(**kwargs)

        try:
            async for page_list in self.get_paginated(endpoint):
                # page_list is a list[dict], yield each dict
                for item_dict in page_list:
                    yield item_dict
        except httpx.HTTPError as exc:
            logger.warning(f"Failed to fetch {resource_type} => {kwargs}: {str(exc)}")
            return
