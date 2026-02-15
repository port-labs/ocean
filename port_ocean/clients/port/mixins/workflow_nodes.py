from typing import Any
import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.exceptions.execution_manager import RunAlreadyAcknowledgedError

INTERNAL_WORKFLOW_CLIENT_HEADER = {"x-port-reserved-usage": "true"}


class WorkflowNodesClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client

    async def claim_pending_wf_node_runs(
        self, limit: int, visibility_timeout_ms: int
    ) -> list[WorkflowNodeRun]:
        response = await self.client.post(
            f"{self.auth.api_url}/workflows/runs/claim-pending",
            headers={**(await self.auth.headers()), **INTERNAL_WORKFLOW_CLIENT_HEADER},
            json={
                "installationId": self.auth.integration_identifier,
                "limit": limit,
                "visibilityTimeoutMs": visibility_timeout_ms,
            },
        )
        if response.is_error:
            logger.error("Error claiming pending wf_node runs", error=response.text)
            return []
        return [
            WorkflowNodeRun.parse_obj(run)
            for run in response.json().get("nodeRuns", [])
        ]

    async def acknowledge_wf_node_run(self, run_id: str) -> None:
        try:
            response = await self.client.patch(
                f"{self.auth.api_url}/workflows/runs/ack",
                headers={
                    **(await self.auth.headers()),
                    **INTERNAL_WORKFLOW_CLIENT_HEADER,
                },
                json={"nodeRunIdentifier": run_id},
            )
            handle_port_status_code(response)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise RunAlreadyAcknowledgedError()
            raise

    async def patch_wf_node_run(
        self,
        run_id: str,
        payload: dict[str, Any],
        should_raise: bool = True,
    ) -> None:
        response = await self.client.patch(
            f"{self.auth.api_url}/workflows/nodes/runs/{run_id}",
            headers=await self.auth.headers(),
            json=payload,
        )
        handle_port_status_code(response, should_raise=should_raise)
