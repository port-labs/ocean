from typing import Any, Optional, MutableMapping, Dict, AsyncGenerator, List
import time
import asyncio
import httpx

from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

RETRYABLE_ERROR_CODES = [500, 503]

def is_retryable_status_code(status_code: Optional[int]) -> bool:
    """
    Checks if the status code is retryable.
    Handles rate limiting (HTTP 429) and transient errors (e.g., HTTP 500, 503).
    """
    if status_code == 429:
        return True

    if status_code in RETRYABLE_ERROR_CODES:
        return True

    return False


def calculate_wait_time(retries: int, headers: Optional[MutableMapping[str, str]] = None ) -> float:
    """
    Calculates the wait time before retrying a request.
    For rate limits (HTTP 429), it respects the `Retry-After` or `RateLimit-Reset` headers.
    Otherwise, it uses exponential backoff.
    """
    wait_time = 2**retries * 0.1 # Exponential backoff base time

    # https://docs.gitlab.com/ee/administration/settings/user_and_ip_rate_limits.html#response-headers
    if headers:
        if "Retry-After" in headers:
            wait_time = int(headers["Retry-After"])
        elif "RateLimit-Reset" in headers:
            wait_time = int(headers["RateLimit-Reset"]) - time.time()

    return max(wait_time, 0.1) # Ensure the wait time is at least 0.1 seconds

async def handle_retry_logic(status_code: Optional[int], headers: Optional[MutableMapping[str, str]], retries: int = 0, max_retries: int = 5) -> bool:
    """
    Handles the retry logic based on the status code and retry count.
    - If the status code is retryable (rate limit or transient error), it calculates the wait time.
    - Waits for the calculated time before allowing the retry.
    - Stops retrying if the maximm retry count is exceeded.
    """
    if not is_retryable_status_code(status_code) or retries >= max_retries :
        return False

    wait_time = calculate_wait_time(retries, headers)
    retries += 1

    logger.info(f"Retrying after {wait_time} seconds (attempt {retries})...")
    await asyncio.sleep(wait_time)

    return True


# PaginatedData Class
class PaginatedData:
    """Asynchronous generator representing a list of remote objects, fetched page by page."""

    def __init__(
        self,
        url: str,
        query_data: Dict[str, Any],
        headers: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        self._client = http_async_client
        self._headers = headers
        self._kwargs = kwargs.copy()
        self._url = url
        self._query_data = query_data

        self._initialized = False

    async def _query(
        self, url: str, query_data: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """Async method to query the API and handle pagination headers."""
        query_data = query_data or {}
        query_data['owned'] = True
        try:
            response = await self._client.get(url, params=query_data, headers=self._headers, **kwargs)
            response.raise_for_status()

            # Parse pagination-related headers
            try:
                next_url = response.links["next"]["url"]
            except KeyError:
                next_url = None

            self._next_url = next_url

            # Parse JSON data
            self._data = response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise

    async def get_paginated_data(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Async generator to yield paginated data as a list of dictionaries."""

        if not self._initialized:
            await self._query(self._url, self._query_data, **self._kwargs)
            self._initialized = True

        while True:
            # Yield the current page of data
            yield self._data

            # If there's a next page, fetch it
            if self._next_url:
                await self._query(self._next_url, **self._kwargs)
            else:
                break


class GitlabClient:
    def __init__(self, token: str, base_url: str, app_host: str):
        self.token = token
        self.base_url = base_url
        self.http_client = http_async_client
        self.http_client.headers.update()
        self.app_host = app_host

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"Bearer {self.token}"
        }

    async def _get_single_resource(self, url: str, query_params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        retries = 0
        while True:
            try:
                response = await self.http_client.get(url=url, params=query_params, headers=self.api_auth_header)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                headers = e.response.headers
                status_code = e.response.status_code

                if not await handle_retry_logic(status_code, headers, retries):
                    logger.error(f"HTTP error: {status_code}, {e.response.text}")
                    raise
                retries += 1

    async def get_groups(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        paginated_groups = PaginatedData(
            url= f"{self.base_url}/groups",
            query_data={"per_page": 5},
            headers=self.api_auth_header
        )

        async for group_list in paginated_groups.get_paginated_data():
            yield group_list


    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch paginated projects from GitLab and return an async generator of project lists."""
        paginated_projects = PaginatedData(
            url=f"{self.base_url}/projects",
            query_data={"per_page": 5},  # You can adjust per_page as needed
            headers=self.api_auth_header  # Pass the headers for authorization
        )

        # Use async generator to yield each page of projects
        async for project_list in paginated_projects.get_paginated_data():
            yield project_list

    async def get_merge_requests(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        paginated_merge_requests = PaginatedData(
            url= f"{self.base_url}/merge_requests",
            query_data={"per_page": 5},
            headers=self.api_auth_header
        )

        async for merge_request_list in paginated_merge_requests.get_paginated_data():
            yield merge_request_list

    async def get_issues(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        paginated_issues = PaginatedData(
            url= f"{self.base_url}/issues",
            query_data={"per_page": 5},
            headers=self.api_auth_header
        )

        async for issue_list in paginated_issues.get_paginated_data():
            yield issue_list


    async def create_project_webhook(self, project_id: int):
        url = f"{self.base_url}/projects/{project_id}/hooks"
        webhook_url = f"{self.app_host}/integration/webhook"
        data = {
            "url": webhook_url,
            "issues_events": True,
            "merge_requests_events": True,
            "push_events": True,
        }
        try:
            # Check if the webhook already exists
            existing_hooks = await self._get_project_hooks(project_id)
            if any(hook['url'] == webhook_url for hook in existing_hooks):
                logger.info(f"Webhook already exists for project {project_id}")
                return

            # Create the webhook
            response = await self.http_client.post(
                url, headers=self.api_auth_header, json=data
            )
            response.raise_for_status()
            logger.info(f"Created webhook for project {project_id}")
        except Exception as e:
            logger.error(f"Failed to create webhook for project {project_id}: {e}")
            raise

    async def _get_project_hooks(self, project_id: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/projects/{project_id}/hooks"
        paginated_data = PaginatedData(
            url=url,
            query_data={"per_page": 5},
            headers=self.api_auth_header
        )
        hooks = []
        async for hook_list in paginated_data.get_paginated_data():
            hooks.extend(hook_list)
        return hooks

    async def get_single_issue(self, project_id: int, issue_iid: int):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_iid}"
        return await self._get_single_resource(url)

    async def get_single_merge_request(self, project_id: int, mr_iid: int):
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"
        return await self._get_single_resource(url)

    async def get_single_project(self, project_id: int):
        url = f"{self.base_url}/projects/{project_id}"
        return await self._get_single_resource(url)


    async def get_single_group(self, group_id: int):
        url = f"{self.base_url}/groups/{group_id}"
        return await self._get_single_resource(url)
