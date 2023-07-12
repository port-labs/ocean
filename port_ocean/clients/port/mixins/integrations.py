from typing import Any

import httpx
from loguru import logger
from starlette import status

from port_ocean.clients.port.authentication import PortAuthentication


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

    async def get_current_integration(self) -> dict[str, Any]:
        logger.info(f"Fetching integration with id: {self.integration_identifier}")
        response = await self.client.get(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=await self.auth.headers(),
        )
        response.raise_for_status()
        return response.json()["integration"]

    async def create_integration(
        self, _id: str, _type: str, changelog_destination: dict[str, Any]
    ) -> None:
        logger.info(f"Creating integration with id: {_id}")
        headers = await self.auth.headers()
        json = {
            "installationId": _id,
            "installationAppType": _type,
            "changelogDestination": changelog_destination,
        }
        response = await self.client.post(
            f"{self.auth.api_url}/integration", headers=headers, json=json
        )
        response.raise_for_status()

    async def patch_integration(
        self, _id: str, _type: str, changelog_destination: dict[str, Any]
    ) -> None:
        logger.info(f"Updating integration with id: {_id}")
        headers = await self.auth.headers()
        json = {
            "installationId": _id,
            "installationAppType": _type,
            "changelogDestination": changelog_destination,
        }
        response = await self.client.patch(
            f"{self.auth.api_url}/integration/{_id}",
            headers=headers,
            json=json,
        )
        response.raise_for_status()

    async def initiate_integration(
        self, identifier: str, _type: str, changelog_destination: dict[str, Any]
    ) -> None:
        logger.info(f"Initiating integration with id: {identifier}")
        try:
            integration = await self.get_current_integration(identifier)

            logger.info("Checking for diff in integration configuration")
            if (
                integration["changelogDestination"] != changelog_destination
                or integration["installationAppType"] != _type
            ):
                await self.patch_integration(identifier, _type, changelog_destination)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                await self.create_integration(identifier, _type, changelog_destination)
                return

            logger.error(
                f"Error initiating integration with id: {identifier}, error: {e.response.text}"
            )
            raise

        logger.info(f"Integration with id: {identifier} successfully registered")
