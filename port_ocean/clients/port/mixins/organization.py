import time
from typing import List

import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code


class OrganizationClientMixin:
    def __init__(
        self,
        auth: PortAuthentication,
        client: httpx.AsyncClient,
        feature_flags_cache_ttl_seconds: float = 300.0,
    ):
        self.auth = auth
        self.client = client
        self._feature_flags_cache_ttl = feature_flags_cache_ttl_seconds
        self._feature_flags_cache: list[str] | None = None
        self._feature_flags_cached_at: float | None = None

    async def _get_organization_feature_flags(self) -> httpx.Response:
        logger.info("Fetching organization feature flags")

        response = await self.client.get(
            f"{self.auth.api_url}/organization",
            headers=await self.auth.headers(),
        )
        return response

    async def get_organization_feature_flags(
        self, should_raise: bool = True, should_log: bool = True
    ) -> List[str]:
        now = time.monotonic()
        if (
            self._feature_flags_cache is not None
            and self._feature_flags_cached_at is not None
            and now - self._feature_flags_cached_at < self._feature_flags_cache_ttl
        ):
            return self._feature_flags_cache

        response = await self._get_organization_feature_flags()
        handle_port_status_code(response, should_raise, should_log)
        flags: list[str] = (
            response.json().get("organization", {}).get("featureFlags", [])
        )
        self._feature_flags_cache = flags
        self._feature_flags_cached_at = now
        return flags
