from typing import Any

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_status_code
from port_ocean.core.models import Blueprint


class BlueprintClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client

    async def get_blueprint(self, identifier: str) -> Blueprint:
        logger.info(f"Fetching blueprint with id: {identifier}")
        response = await self.client.get(
            f"{self.auth.api_url}/blueprints/{identifier}",
            headers=await self.auth.headers(),
        )
        handle_status_code(response)
        return Blueprint.parse_obj(response.json()["blueprint"])

    async def create_blueprint(self, raw_blueprint: dict[str, Any]) -> None:
        logger.info(f"Creating blueprint with id: {raw_blueprint.get('identifier')}")
        headers = await self.auth.headers()
        response = await self.client.post(
            f"{self.auth.api_url}/blueprints", headers=headers, json=raw_blueprint
        )
        handle_status_code(response)
        if response.is_success:
            return response.json()["blueprint"]

    async def patch_blueprint(
        self, identifier: str, raw_blueprint: dict[str, Any]
    ) -> None:
        logger.info(f"Patching blueprint with id: {identifier}")
        headers = await self.auth.headers()
        response = await self.client.patch(
            f"{self.auth.api_url}/blueprints/{identifier}",
            headers=headers,
            json=raw_blueprint,
        )
        handle_status_code(response)

    async def delete_blueprint(
        self, identifier: str, should_raise: bool = False
    ) -> None:
        logger.info(f"Deleting blueprint with id: {identifier}")
        headers = await self.auth.headers()
        response = await self.client.delete(
            f"{self.auth.api_url}/blueprints/{identifier}",
            headers=headers,
        )
        handle_status_code(response, should_raise)

    async def create_action(
        self, blueprint_identifier: str, action: dict[str, Any]
    ) -> None:
        logger.info(f"Creating action: {action}")
        response = await self.client.post(
            f"{self.auth.api_url}/blueprints/{blueprint_identifier}/actions",
            json=action,
            headers=await self.auth.headers(),
        )

        handle_status_code(response)

    async def create_scorecard(
        self,
        blueprint_identifier: str,
        scorecard: dict[str, Any],
    ) -> None:
        logger.info(f"Creating scorecard: {scorecard}")
        response = await self.client.post(
            f"{self.auth.api_url}/blueprints/{blueprint_identifier}/scorecards",
            json=scorecard,
            headers=await self.auth.headers(),
        )

        handle_status_code(response)
