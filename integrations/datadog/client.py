from typing import Any, AsyncGenerator

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from loguru import logger


class CacheKeys:
    HOSTS = "hosts"
    MONITORS = "monitors"
    SLOS = "slos"


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

    async def fetch_resources(self, endpoint: str) -> dict[str, Any]:
        logger.info(f"Fetching datadog resources from endpoint {endpoint}")

        response = await self.http_client.get(
            url=f"{self.api_url}/api/v1/{endpoint}",
            headers=await self.auth_headers,
        )
        response.raise_for_status()
        return response.json()

    async def get_hosts(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.HOSTS):
            logger.info("Picking Datadog Hosts from cache")
            yield cache
            return

        result = await self.fetch_resources("hosts")

        if result.get("host_list"):
            hosts = result["host_list"]
            event.attributes.setdefault(CacheKeys.HOSTS, []).extend(hosts)
            yield hosts

        yield []

    async def get_monitors(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.MONITORS):
            logger.info("Picking Datadog Monitors from cache")
            yield cache
            return

        monitors = await self.fetch_resources("monitor")

        if monitors:
            event.attributes.setdefault(CacheKeys.MONITORS, []).extend(monitors)
            yield monitors

        yield []

    async def get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.SLOS):
            logger.info("Picking Datadog SLOs from cache")
            yield cache
            return

        result = await self.fetch_resources("slo")

        if result.get("data"):
            slos = result["data"]
            event.attributes.setdefault(CacheKeys.SLOS, []).extend(slos)
            yield slos

        yield []
