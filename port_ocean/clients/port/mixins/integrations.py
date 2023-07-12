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
            response = await client.get(
                f"{self.auth.api_url}/integration/{identifier}",
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
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
        async with httpx.AsyncClient() as client:
            response = await client.patch(
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
            integration = await self.get_integration(identifier)

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
