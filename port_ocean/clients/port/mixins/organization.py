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
    ):
        self.auth = auth
        self.client = client

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
        response = await self._get_organization_feature_flags()
        handle_port_status_code(response, should_raise, should_log)
        return response.json().get("organization", {}).get("featureFlags", [])
