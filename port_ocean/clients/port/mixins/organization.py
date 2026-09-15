import time
from typing import Any, List

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
        self._organization_cache_ttl = feature_flags_cache_ttl_seconds
        self._organization_cache: dict[str, Any] | None = None
        self._organization_cached_at: float | None = None

    async def _fetch_organization(self) -> httpx.Response:
        logger.info("Fetching organization details")

        response = await self.client.get(
            f"{self.auth.api_url}/organization",
            headers=await self.auth.headers(),
        )
        return response

    async def _get_organization(
        self, should_raise: bool = True, should_log: bool = True
    ) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._organization_cache is not None
            and self._organization_cached_at is not None
            and now - self._organization_cached_at < self._organization_cache_ttl
        ):
            return self._organization_cache

        response = await self._fetch_organization()
        handle_port_status_code(response, should_raise, should_log)
        organization: dict[str, Any] = response.json().get("organization", {})
        self._organization_cache = organization
        self._organization_cached_at = now
        return organization

    async def get_organization_feature_flags(
        self, should_raise: bool = True, should_log: bool = True
    ) -> List[str]:
        organization = await self._get_organization(should_raise, should_log)
        return organization.get("featureFlags", [])

    async def is_organization_blocked(
        self, should_raise: bool = True, should_log: bool = True
    ) -> bool:
        organization = await self._get_organization(should_raise, should_log)
        return bool(organization.get("isBlocked", False))
