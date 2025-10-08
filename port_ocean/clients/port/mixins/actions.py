from typing import Any
import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.core.models import (
    ActionRun,
)


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

    async def get_run_by_external_id(self, external_id: str) -> ActionRun:
        response = await self.client.get(
            f"{self.auth.api_url}/actions/runs?external_run_id={external_id}",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)
        return response.json()

    async def get_pending_runs(
        self, limit: int = 20, visibility_timeout_seconds: int = 90
    ) -> list[ActionRun]:
        response = await self.client.get(
            f"{self.auth.api_url}/actions/runs/pending",
            headers=await self.auth.headers(),
            params={
                "limit": limit,
                "visibility_timeout_seconds": visibility_timeout_seconds,
            },
        )
        handle_port_status_code(response)
        return [ActionRun.parse_obj(run) for run in response.json().get("runs", [])]

    async def patch_run(
        self,
        run_id: str,
        run: ActionRun,
    ) -> None:
        response = await self.client.patch(
            f"{self.auth.api_url}/actions/runs/{run_id}",
            headers=await self.auth.headers(),
            json=run.dict(),
        )
        handle_port_status_code(response)

    async def acknowledge_run(self, run_id: str) -> None:
        response = await self.client.patch(
            f"{self.auth.api_url}/actions/runs/{run_id}/ack",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)

    async def post_run_log(self, run_id: str, message: str) -> None:
        response = await self.client.post(
            f"{self.auth.api_url}/actions/runs/{run_id}/logs",
            headers=await self.auth.headers(),
            json={"message": message},
        )
        handle_port_status_code(response)
