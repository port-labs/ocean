import asyncio
from typing import Any, Optional, AsyncGenerator, Dict
from loguru import logger
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError, Response
from helpers.gitlab_rate_limiter import GitLabRateLimiter
import yaml
from datetime import datetime, timezone




PAGE_SIZE = 100
CLIENT_TIMEOUT = 60


class GitlabHandler:
    def __init__(self, private_token: str, config_file: str, base_url: str = "https://gitlab.com/api/v4/"):
        self.base_url = base_url
        self.auth_header = {"PRIVATE-TOKEN": private_token}
        self.client = http_async_client
        self.client.timeout = CLIENT_TIMEOUT
        self.client.headers.update(self.auth_header)
        self.rate_limiter = GitLabRateLimiter()
        self.retries = 3
        self.base_delay = 1
        self.config = self.load_config(config_file)


    def load_config(self, config_file: str) -> Dict[str, Any]:
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)


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
                if e.response.status_code == 401:
                    logger.error(f"Unauthorized access to {url}. Please check your GitLab token.")
                    raise
                elif e.response.status_code == 429:
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

    async def _fetch_additional_data(self, resource: str, item: Dict[str, Any]) -> Dict[str, Any]:
       additional_data = self.config.get(resource, {}).get('additional_data', [])


       # If additional_data is empty, return the item without adding anything
       if not additional_data:
           return item


       additional_tasks = []
       for data_type in additional_data:
           additional_endpoint = f"{resource}/{item['id']}/{data_type}"
           additional_tasks.append(self._send_api_request(additional_endpoint))


       additional_results = await asyncio.gather(*additional_tasks, return_exceptions=True)


       for data_type, result in zip(additional_data, additional_results):
           if isinstance(result, Exception):
               logger.error(f"Failed to fetch additional data '{data_type}' for item {item['id']}: {str(result)}")
           else:
               item[data_type] = result


       return item


    async def get_paginated_resources(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        params = params or {}
        params.update(self.config.get(resource, {}).get('params', {}))
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


            # Fetch additional data concurrently for all items on the page
            enhanced_items = await asyncio.gather(
                *[self._fetch_additional_data(resource, item) for item in response]
            )


            yield enhanced_items


            if len(response) < PAGE_SIZE:
                logger.debug(f"Last page reached for resource '{resource}', no more data.")
                break


            params["page"] += 1


    async def get_single_resource(
        self, resource_kind: str, resource_id: str
    ) -> Dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._send_api_request(f"{resource_kind}/{resource_id}")
