from typing import Any
import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.core.models import (
    ActionRun,
)
from port_ocean.exceptions.execution_manager import RunAlreadyAcknowledgedError

INTERNAL_ACTIONS_CLIENT_HEADER = {"x-port-reserved-usage": "true"}


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

    async def claim_pending_runs(
        self, limit: int, visibility_timeout_ms: int
    ) -> list[ActionRun]:
        response = await self.client.post(
            f"{self.auth.api_url}/actions/runs/claim-pending",
            headers={**(await self.auth.headers()), **INTERNAL_ACTIONS_CLIENT_HEADER},
            json={
                "installationId": self.auth.integration_identifier,
                "limit": limit,
                "visibilityTimeoutMs": visibility_timeout_ms,
            },
        )
        if response.is_error:
            logger.error("Error claiming pending runs", error=response.text)
            return []

        return [ActionRun.parse_obj(run) for run in response.json().get("runs", [])]

    async def get_run_by_external_id(self, external_id: str) -> ActionRun | None:
        response = await self.client.get(
            f"{self.auth.api_url}/actions/runs?version=v2&external_run_id={external_id}",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)
        runs = response.json().get("runs", [])
        return None if not len(runs) else ActionRun.parse_obj(runs[0])

    async def patch_run(
        self,
        run_id: str,
        run: ActionRun | dict[str, Any],
        should_raise: bool = True,
    ) -> None:
        response = await self.client.patch(
            f"{self.auth.api_url}/actions/runs/{run_id}",
            headers=await self.auth.headers(),
            json=run.dict() if isinstance(run, ActionRun) else run,
        )
        handle_port_status_code(response, should_raise=should_raise)

    async def acknowledge_run(self, run_id: str) -> None:
        try:
            response = await self.client.patch(
                f"{self.auth.api_url}/actions/runs/ack",
                headers={
                    **(await self.auth.headers()),
                    **INTERNAL_ACTIONS_CLIENT_HEADER,
                },
                json={"runId": run_id},
            )
            handle_port_status_code(response)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise RunAlreadyAcknowledgedError()
            raise

    async def post_run_log(self, run_id: str, message: str) -> None:
        response = await self.client.post(
            f"{self.auth.api_url}/actions/runs/{run_id}/logs",
            headers=await self.auth.headers(),
            json={"message": message},
        )
        handle_port_status_code(response, should_raise=False)
