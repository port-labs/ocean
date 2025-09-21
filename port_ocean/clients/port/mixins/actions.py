from typing import Any
import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code


class ActionsClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client

    async def create_action(
        self, action: dict[str, Any], should_log: bool = True
    ) -> None:
        logger.info(f"Creating action: {action}")
        response = await self.client.post(
            f"{self.auth.api_url}/actions",
            json=action,
            headers=await self.auth.headers(),
        )

        handle_port_status_code(response, should_log=should_log)

    async def get_action(self, action_id: str) -> dict[str, Any]:
        response = await self.client.get(
            f"{self.auth.api_url}/actions/{action_id}",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)
        return response.json()

    async def get_run(self, run_id: str) -> dict[str, Any]:
        response = await self.client.get(
            f"{self.auth.api_url}/runs/{run_id}",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)
        return response.json()

    async def get_pending_runs(self) -> list[dict[str, Any]]:
        # response = await self.client.get(
        #     f"{self.auth.api_url}/runs/pending?installation_id={self.auth.integration_identifier}",
        #     headers=await self.auth.headers(),
        # )
        # handle_port_status_code(response)
        # return response.json()
        return [{}]

    async def patch_run(self, run_id: str, run: dict[str, Any]) -> None:
        response = await self.client.patch(
            f"{self.auth.api_url}/runs/{run_id}",
            headers=await self.auth.headers(),
            json=run,
        )
        handle_port_status_code(response)
