from typing import Any

import httpx
from loguru import logger
from starlette import status

from port_ocean.clients.port.authentication import PortAuthentication


class IntegrationClientMixin:
    def __init__(self, auth: PortAuthentication):
        self.auth = auth

    async def get_integration(self, identifier: str) -> dict[str, Any]:
        logger.info(f"Fetching integration with id: {identifier}")
        async with httpx.AsyncClient() as client:
            integration = await client.get(
                f"{self.auth.api_url}/integration/{identifier}",
                headers=await self.auth.headers(),
            )
        integration.raise_for_status()
        return integration.json()["integration"]

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
        async with httpx.AsyncClient() as client:
            installation = await client.post(
                f"{self.auth.api_url}/integration", headers=headers, json=json
            )
        installation.raise_for_status()

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
        async with httpx.AsyncClient() as client:
            installation = await client.patch(
                f"{self.auth.api_url}/integration/{_id}",
                headers=headers,
                json=json,
            )
        installation.raise_for_status()

    async def initiate_integration(
        self, _id: str, _type: str, changelog_destination: dict[str, Any]
    ) -> None:
        logger.info(f"Initiating integration with id: {_id}")
        try:
            integration = await self.get_integration(_id)

            logger.info("Checking for diff in integration configuration")
            if (
                integration["changelogDestination"] != changelog_destination
                and integration["installationAppType"] == _type
            ):
                await self.patch_integration(_id, _type, changelog_destination)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_400_BAD_REQUEST:
                await self.create_integration(_id, _type, changelog_destination)
                return

            logger.error(
                f"Error initiating integration with id: {_id}, error: {e.response.text}"
            )
            raise

        logger.info(f"Integration with id: {_id} successfully registered")
