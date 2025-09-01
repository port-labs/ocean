import typing
from typing import Any, Optional

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils import http_async_client

from integration import CloudCostResourceConfig, OpencostResourceConfig
from utils import IgnoredError


class OpenCostClient:
    def __init__(self, app_host: str):
        self.app_host = app_host
        self.http_client = http_async_client

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=401,
            message="Unauthorized access to endpoint — authentication required or token invalid",
            type="UNAUTHORIZED",
        ),
        IgnoredError(
            status=403,
            message="Forbidden access to endpoint — insufficient permissions",
            type="FORBIDDEN",
        ),
        IgnoredError(
            status=404,
            message="Resource not found at endpoint",
        ),
    ]

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
        ignored_errors: Optional[list[IgnoredError]] = None,
    ) -> bool:
        """Check if the error should be ignored based on status code."""
        all_ignored_errors = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS
        status_code = error.response.status_code

        for ignored_error in all_ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Failed to fetch resources at {resource} due to {ignored_error.message}"
                )
                return True
        return False

    async def send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[list[IgnoredError]] = None,
    ) -> dict[str, Any]:
        """Send API request with error handling and optional ignored errors."""
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if self._should_ignore_error(e, url, ignored_errors):
                return {}

            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for endpoint '{url}': {str(e)}")
            raise

    async def get_cost_allocation(self) -> list[dict[str, Any]]:
        """Calls the OpenCost allocation endpoint to return data for cost and usage
        https://www.opencost.io/docs/integrations/api
        """
        selector = typing.cast(OpencostResourceConfig, event.resource_config).selector
        params: dict[str, str] = {
            "window": selector.window,
        }
        if selector.aggregate:
            params["aggregate"] = selector.aggregate
        if selector.step:
            params["step"] = selector.step
        if selector.resolution:
            params["resolution"] = selector.resolution

        response = await self.send_api_request(
            url=f"{self.app_host}/allocation/compute",
            params=params,
        )

        return response["data"] if response else []

    async def get_cloudcost(self) -> list[dict[str, dict[str, dict[str, Any]]]]:
        """
        Retrieves cloud cost data from cloud providers by reading cost
        and usage reports.
        Docs: https://www.opencost.io/docs/integrations/api#cloud-costs-api
        """
        selector = typing.cast(CloudCostResourceConfig, event.resource_config).selector
        params: dict[str, str] = {
            "window": selector.window,
        }
        if selector.aggregate:
            params["aggregate"] = selector.aggregate
        if selector.accumulate:
            params["accumulate"] = selector.accumulate
        if selector.filter:
            params["filter"] = selector.filter

        response = await self.send_api_request(
            url=f"{self.app_host}/cloudCost",
            params=params,
        )
        return response["data"]["sets"] if response else []
