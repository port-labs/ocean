from typing import Any, TYPE_CHECKING, Optional

import httpx
from loguru import logger
from starlette import status

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_status_code

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class IntegrationClientMixin:
    def __init__(
        self,
        integration_identifier: str,
        auth: PortAuthentication,
        client: httpx.AsyncClient,
    ):
        self.integration_identifier = integration_identifier
        self.auth = auth
        self.client = client

    async def _get_current_integration(self) -> httpx.Response:
        logger.info(f"Fetching integration with id: {self.integration_identifier}")
        response = await self.client.get(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=await self.auth.headers(),
        )
        return response

    async def get_current_integration(self) -> dict[str, Any]:
        response = await self._get_current_integration()
        handle_status_code(response)
        return response.json()["integration"]

    async def create_integration(
        self,
        _type: str,
        changelog_destination: dict[str, Any],
        port_app_config: Optional["PortAppConfig"] = None,
    ) -> None:
        logger.info(f"Creating integration with id: {self.integration_identifier}")
        headers = await self.auth.headers()
        json = {
            "installationId": self.integration_identifier,
            "installationAppType": _type,
            "changelogDestination": changelog_destination,
            "config": {},
        }
        if port_app_config:
            json["config"] = port_app_config.to_request()
        response = await self.client.post(
            f"{self.auth.api_url}/integration", headers=headers, json=json
        )
        handle_status_code(response)

    async def patch_integration(
        self,
        _type: str | None = None,
        changelog_destination: dict[str, Any] | None = None,
        port_app_config: Optional["PortAppConfig"] = None,
    ) -> None:
        logger.info(f"Updating integration with id: {self.integration_identifier}")
        headers = await self.auth.headers()
        json = {}
        if _type:
            json["installationAppType"] = _type
        if changelog_destination:
            json["changelogDestination"] = changelog_destination
        if port_app_config:
            json["config"] = port_app_config.to_request()

        response = await self.client.patch(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=headers,
            json=json,
        )
        handle_status_code(response)

    async def initialize_integration(
        self,
        _type: str,
        changelog_destination: dict[str, Any],
        port_app_config: Optional["PortAppConfig"] = None,
    ) -> None:
        logger.info(f"Initiating integration with id: {self.integration_identifier}")
        response = await self._get_current_integration()
        if response.status_code == status.HTTP_404_NOT_FOUND:
            await self.create_integration(_type, changelog_destination, port_app_config)
        else:
            handle_status_code(response)

            integration = response.json()["integration"]
            logger.info("Checking for diff in integration configuration")
            if (
                integration["changelogDestination"] != changelog_destination
                or integration["installationAppType"] != _type
            ):
                await self.patch_integration(
                    _type, changelog_destination, port_app_config
                )

        logger.info(
            f"Integration with id: {self.integration_identifier} successfully registered"
        )
