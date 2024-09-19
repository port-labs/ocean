import asyncio
from typing import Any, AsyncGenerator

import httpx
from httpx import Timeout
from loguru import logger

from rate_limiter import GitLabRateLimiter
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

REQUEST_TIMEOUT: int = 60
CREATE_UPDATE_WEBHOOK_EVENTS: list[str] = [
    "open",
    "reopen",
    "update",
    "approved",
    "unapproved",
    "approval",
    "unapproval",
]
DELETE_WEBHOOK_EVENTS: list[str] = ["close", "merge"]
WEBHOOK_EVENTS_TO_TRACK: dict[str, bool] = {
    "push_events": True,
    "issues_events": True,
    "merge_requests_events": True,
}
WEBHOOK_NAME: str = "Port-Ocean-Events-Webhook"
PER_PAGE = 50


class GitlabClient:
    def __init__(self, gitlab_host: str, gitlab_token: str) -> None:
        self.gitlab_host = f"{gitlab_host}/api/v4"
        self.gitlab_token = gitlab_token
        self.client = http_async_client
        self.client.headers.update({"Authorization": f"Bearer {gitlab_token}"})
        self.client.timeout = Timeout(REQUEST_TIMEOUT)
        self.rate_limiter = GitLabRateLimiter()

    async def _make_request(
            self,
            url: str,
            method: str = "GET",
            query_params: dict[str, Any] | None = None,
            json_data: dict[str, Any] | None = None,
            headers: dict[str, Any] | None = None,
            return_with_headers: bool = False,
    ) -> Any:
        logger.info(f"Sending request to GitLab API: {method} {url}")
        try:
            # Apply rate limiting before making the request
            await self.rate_limiter.wait_for_slot()

            response = await self.client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
                headers=headers,
            )
            response.raise_for_status()

            # Update rate limits based on the response
            self.rate_limiter.update_limits(response.headers)

            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {method} {url} with query_params: {query_params}"
            )
            raise

    @staticmethod
    def _default_paginated_req_params(
            page: int = 1, per_page: int = 50, owned: bool = True
    ) -> dict[str, Any]:
        return {
            "page": page,
            "per_page": per_page,
            "owned": owned,
        }

    async def get_paginated_resources(self, kind: str, params: dict[str, Any] | None = {}) -> AsyncGenerator[
        list[dict[str, Any]], None]:
        """Fetch paginated data from the Gitlab Deploy API."""
        kind_configs = ocean.integration_config.get("gitlab_resources_config", {}).get(kind, {})
        params = {**self._default_paginated_req_params(), **kind_configs.get("params", {})}

        next_page = True

        while next_page:
            logger.info(f"Making paginated request for {kind} with params: {params}")
            url = f"{self.gitlab_host}/{kind}"
            response = await self._make_request(url=url, query_params=params)

            if kind_configs.get("data_to_enrich"):
                response = await asyncio.gather(
                    *[self._enrich_resource_kind(kind, data) for data in response]
                )

            yield response

            if len(response) < PER_PAGE:
                logger.debug(f"Last page reached for resource '{kind}', no more data.")
                break

            params["page"] += 1

        logger.info("Finished paginated request")

    async def get_single_resource(
            self, resource_kind: str, resource_id: str
    ) -> dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._make_request(f"{self.gitlab_host}/{resource_kind}/{resource_id}")

    async def _enrich_resource_kind(self, kind: str, resource_data: dict[str, Any]) -> dict[str, Any]:
        data_to_enrich = ocean.integration_config["gitlab_resources_config"].get(kind, {}).get("data_to_enrich")
        for data in data_to_enrich:
            response = await self._make_request(url=f"{self.gitlab_host}/{kind}/{int(resource_data['id'])}/{data}")
            resource_data[f"__{data}"] = response

        return resource_data

    async def create_project_webhook(
            self, webhook_host: str, project: dict[str, Any]
    ) -> None:
        payload: dict[str, Any] = {
            "id": project["id"],
            "name": f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            "url": webhook_host,
            **WEBHOOK_EVENTS_TO_TRACK,
        }

        try:
            logger.info(f"Creating hook for project {project['path_with_namespace']}")
            await self._make_request(
                url=f"{self.gitlab_host}/projects/{project['id']}/hooks",
                method="POST",
                json_data=payload,
            )
            logger.info(f"Created hook for project {project['path_with_namespace']}")
        except Exception as e:
            logger.error(
                f"Failed to create webhook for project {project['path_with_namespace']}: {e}"
            )

