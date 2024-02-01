from typing import Any, AsyncGenerator

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from loguru import logger

MAX_PAGE_SIZE = 50


class CacheKeys:
    HOSTS = "_cache_hosts"
    MONITORS = "_cache_monitors"
    SLOS = "_cache_slos"


class DatadogClient:
    def __init__(self, dd_api_url: str, dd_api_key: str, dd_app_key: str):
        self.api_url = dd_api_url
        self.dd_api_key = dd_api_key
        self.dd_app_key = dd_app_key

        self.http_client = http_async_client

    @property
    async def auth_headers(self) -> dict[str, Any]:
        return {
            "DD-API-KEY": self.dd_api_key,
            "DD-APPLICATION-KEY": self.dd_app_key,
            "Content-Type": "application/json",
        }

    async def fetch_resources(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        logger.info(f"Fetching datadog resources from endpoint {endpoint}")

        response = await self.http_client.get(
            url=f"{self.api_url}/api/v1/{endpoint}",
            headers=await self.auth_headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_hosts(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.HOSTS):
            logger.info("Picking Datadog Hosts from cache")
            yield cache
            return

        start = 0
        count = MAX_PAGE_SIZE

        while True:
            result = await self.fetch_resources(
                "hosts", {"start": start, "count": count}
            )

            hosts = result.get("host_list")
            if not hosts:
                break

            event.attributes.setdefault(CacheKeys.HOSTS, []).extend(hosts)
            yield hosts
            start += count

    async def get_monitors(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.MONITORS):
            logger.info("Picking Datadog Monitors from cache")
            yield cache
            return

        page = 0
        page_size = MAX_PAGE_SIZE

        while True:
            monitors = await self.fetch_resources(
                "monitor", {"page": page, "page_size": page_size}
            )

            if not monitors:
                break

            event.attributes.setdefault(CacheKeys.MONITORS, []).extend(monitors)
            yield monitors
            page += 1

    async def get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Asynchronously fetches Datadog SLOs (Service Level Objectives).

        This method retrieves SLOs from Datadog, handling pagination to ensure
        all SLOs are fetched. If the SLOs are available in the cache, it retrieves
        them from the cache.

        Yields:
            List[Dict[str, Any]]: A list of dictionaries representing Datadog SLOs.

        Returns:
            AsyncGenerator: An asynchronous generator yielding lists of SLOs.

        Example:
            async for slo_batch in your_instance.get_slos():
                process_slo_batch(slo_batch)
        """
        if cache := event.attributes.get(CacheKeys.SLOS):
            logger.info("Picking Datadog SLOs from cache")
            yield cache
            return

        offset = 0
        limit = MAX_PAGE_SIZE

        while True:
            result = await self.fetch_resources(
                "slo", {"limit": limit, "offset": offset}
            )

            slos = result.get("data")
            if not slos:
                break

            event.attributes.setdefault(CacheKeys.SLOS, []).extend(slos)
            yield slos
            offset += limit
