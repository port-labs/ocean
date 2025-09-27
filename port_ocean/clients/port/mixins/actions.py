import random
from typing import Any
import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.core.models import (
    ActionRun,
    RunStatus,
    Action,
    IntegrationInvocationPayload,
    InvocationType,
)
from port_ocean.context.ocean import ocean


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

    async def get_action(self, action_id: str) -> Action:
        response = await self.client.get(
            f"{self.auth.api_url}/actions/{action_id}",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)
        return response.json()

    async def get_run(self, run_id: str) -> ActionRun:
        response = await self.client.get(
            f"{self.auth.api_url}/runs/{run_id}",
            headers=await self.auth.headers(),
        )
        handle_port_status_code(response)
        return response.json()

    async def get_pending_runs(self, limit: int = 50) -> list[ActionRun]:
        mock_actions = [
            "dispatch_workflow",
            "create_issue",
            "create_pull_request",
        ]
        mock_actions_payloads = {
            "dispatch_workflow": {
                "repo": "test",
                "workflow": "test.yml",
                "reportWorkflowStatus": True,
                "workflowInputs": {"param1": "value1", "param2": 1},
            },
            "create_issue": {"title": "test", "body": "test"},
            "create_pull_request": {"title": "test", "body": "test"},
        }
        num_runs = random.randint(2, ocean.config.execution_agent.max_runs_per_poll)
        return [
            ActionRun(
                id=str(i),
                status=RunStatus.IN_PROGRESS,
                action=Action(
                    id=f"action_{i}",
                    name=f"test_action_{i}",
                    description=f"Test action {i}",
                ),
                payload=IntegrationInvocationPayload(
                    type=InvocationType.OCEAN,
                    installationId=ocean.config.integration.identifier,
                    action=mock_actions[i % len(mock_actions)],
                    oceanExecution=mock_actions_payloads[
                        mock_actions[i % len(mock_actions)]
                    ],
                ),
            )
            for i in range(num_runs)
        ]

    async def patch_run(self, run_id: str, run: dict[str, Any]) -> None:
        response = await self.client.patch(
            f"{self.auth.api_url}/runs/{run_id}",
            headers=await self.auth.headers(),
            json=run,
        )
        handle_port_status_code(response)
