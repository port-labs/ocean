# client.py

from typing import Any, Optional, Dict, List, AsyncGenerator, MutableMapping
import time
import asyncio
import httpx
from loguru import logger

RETRYABLE_ERROR_CODES = [500, 503]


class GitlabClient:
    def __init__(self, token: str, base_url: str, app_host: str):
        self.token = token
        self.base_url = base_url
        self.http_client = httpx.AsyncClient()
        self.app_host = app_host

        self._groups_cache: Optional[List[Dict[str, Any]]] = None

    @property
    def api_auth_header(self) -> Dict[str, Any]:
        return {"Authorization": f"Bearer {self.token}"}

    def _is_retryable_status_code(self, status_code: Optional[int]) -> bool:
        return status_code in [429, *RETRYABLE_ERROR_CODES]


    def _calculate_wait_time(self, retries: int, headers: Optional[MutableMapping[str, str]] = None) -> float:
        """
        Calculates the wait time before retrying a request.
        For rate limits (HTTP 429), it respects the `Retry-After` or `RateLimit-Reset` headers.
        Otherwise, it uses exponential backoff.
        """
        wait_time = 2**retries * 0.1  # Exponential backoff base time

        # https://docs.gitlab.com/ee/administration/settings/user_and_ip_rate_limits.html#response-headers
        if headers:
            if "Retry-After" in headers:
                wait_time = int(headers["Retry-After"])
            elif "RateLimit-Reset" in headers:
                wait_time = int(headers["RateLimit-Reset"]) - time.time()

        return max(wait_time, 0.1)  # Ensure the wait time is at least 0.1 seconds


    async def _handle_retry_logic(
        self,
        status_code: Optional[int],
        headers: Optional[Dict[str, Any]],
        retries: int = 0,
        max_retries: int = 5,
    ) -> bool:
        """
        Handles the retry logic based on the status code and retry count.
        - If the status code is retryable (rate limit or transient error), it calculates the wait time.
        - Waits for the calculated time before allowing the retry.
        - Stops retrying if the maximum retry count is exceeded.
        """
        if not self._is_retryable_status_code(status_code) or retries >= max_retries:
            return False

        wait_time = self._calculate_wait_time(retries, headers)
        retries += 1

        logger.info(f"Retrying after {wait_time} seconds (attempt {retries})...")
        await asyncio.sleep(wait_time)

        return True

    async def _get_single_resource(
        self, url: str, query_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        retries = 0
        while True:
            try:
                response = await self.http_client.get(
                    url=url, params=query_params, headers=self.api_auth_header
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                headers = e.response.headers
                status_code = e.response.status_code

                if not await handle_retry_logic(status_code, headers, retries):
                    logger.error(f"HTTP error: {status_code}, {e.response.text}")
                    raise
                retries += 1

    async def _get_paginated_resource(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        params = params or {}
        params.setdefault("per_page", 100)

        while url:
            try:
                response = await self.http_client.get(
                    url, params=params, headers=self.api_auth_header
                )
                response.raise_for_status()
                data = response.json()
                yield data
                if 'next' in response.links:
                    url = response.links['next']['url']
                    params = None  # Parameters are already in the URL
                else:
                    url = None
            except httpx.HTTPStatusError as e:
                headers = e.response.headers
                status_code = e.response.status_code
                logger.error(f"HTTP error: {status_code}, {e.response.text}")
                raise

    async def get_groups(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        url = f"{self.base_url}/groups"
        params = {"owned": True, "per_page": 100}
        async for group_list in self._get_paginated_resource(url, params):
            yield group_list

    async def get_projects(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/projects"
        params = {"owned": True, "per_page": 100}
        semaphore = asyncio.Semaphore(10)  # Adjust concurrency limit as needed

        async for project_list in self._get_paginated_resource(url, params):
            # Fetch languages concurrently for each project in the current page
            tasks = [
                self._fetch_project_languages_with_semaphore(project, semaphore)
                for project in project_list
            ]
            await asyncio.gather(*tasks)
            yield project_list

    async def _fetch_project_languages_with_semaphore(self, project: Dict[str, Any], semaphore: asyncio.Semaphore):
        async with semaphore:
            try:
                languages = await self.get_project_languages(project['id'])
                project['language'] = ', '.join(languages.keys())
            except Exception as e:
                logger.error(f"Error fetching languages for project {project['id']}: {e}")
                project['language'] = {}


    async def get_project_languages(self, project_id: int) -> Dict[str, float]:
        url = f"{self.base_url}/projects/{project_id}/languages"
        retries = 0
        while True:
            try:
                response = await self.http_client.get(url, headers=self.api_auth_header)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                headers = e.response.headers
                status_code = e.response.status_code

                if not await handle_retry_logic(status_code, headers, retries):
                    logger.error(f"HTTP error: {status_code}, {e.response.text}")
                    raise
                retries += 1

    async def get_merge_requests(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        url = f"{self.base_url}/merge_requests"
        params = {"owned": True, "per_page": 100}
        async for mr_list in self._get_paginated_resource(url, params):
            yield mr_list

    async def get_issues(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        url = f"{self.base_url}/issues"
        params = {"owned": True, "per_page": 100}
        async for issue_list in self._get_paginated_resource(url, params):
            yield issue_list

    async def _get_group_hooks(self, group_id: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/groups/{group_id}/hooks"
        response = await self.http_client.get(
            url, headers=self.api_auth_header
        )
        response.raise_for_status()
        return response.json()

    async def create_group_webhook(self, group_id: int, webhook_url: str):
        url = f"{self.base_url}/groups/{group_id}/hooks"
        webhook_url = f"{self.app_host}/integration/webhook"

        data = {
            "url": webhook_url,
            "issues_events": True,
            "merge_requests_events": True,
            "push_events": True,
        }

        try:
            # Check if the webhook already exists
            existing_hooks = await self._get_group_hooks(group_id)
            if any(hook["url"] == webhook_url for hook in existing_hooks):
                logger.info(f"Webhook already exists for group {group_id}")
                return

            response = await self.http_client.post(
                url, headers=self.api_auth_header, json=data
            )
            response.raise_for_status()
            logger.info(f"Created webhook for group {group_id}")
        except Exception as e:
            logger.error(f"Failed to create webhook for group {group_id}: {e}")
            raise
