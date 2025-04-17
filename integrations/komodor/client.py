from typing import Optional, Any, AsyncGenerator

from loguru import logger
from port_ocean.utils import http_async_client

# The page size may differ between entities base on their potential size
DEFAULT_PAGE_SIZE = 100
SERVICES_PAGE_SIZE = 25  # The service page size is smaller due to the potential extra data in labels and annotations
RISKS_PAGE_SIZE = 50  # The risks page size is smaller due to the potential extra data in the supportingData field


class KomodorClient:
    def __init__(
        self, api_key: str, api_url: Optional[str] = "https://api.komodor.com/api/v2"
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.http_client = http_async_client
        self.http_client.headers.update(
            {
                "accept": "application/json",
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            }
        )

    async def _send_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        response = await self.http_client.request(
            url=url, params=params, json=data, method=method
        )
        response.raise_for_status()
        return response.json()

    async def get_all_services(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        current_page = 0
        while True:
            response = await self._send_request(
                url=f"{self.api_url}/services/search",
                data={
                    "kind": ["Deployment", "StatefulSet", "DaemonSet", "Rollout"],
                    "pagination": {
                        "pageSize": SERVICES_PAGE_SIZE,
                        "page": current_page,
                    },
                },
                method="POST",
            )
            yield response.get("data", {}).get("services", [])

            current_page = response.get("meta", {}).get("nextPage", None)
            if not current_page:
                logger.debug("No more service pages, breaking")
                break

    async def get_health_monitor(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        offset = 0
        while True:
            response = await self._send_request(
                url=f"{self.api_url}/health/risks",
                params={
                    "pageSize": RISKS_PAGE_SIZE,
                    "offset": offset,
                    "checkCategory": ["workload", "infrastructure"],
                    "impactGroupType": ["dynamic", "realtime"],
                },
            )
            yield response.get("violations", [])

            if not response.get("hasMoreResults"):
                logger.debug("No more health risks pages, breaking")
                break
            offset += RISKS_PAGE_SIZE
