from abc import abstractmethod
from typing import Any

from loguru import logger
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.clients.client_factory import (
    create_arm_deployments_client,
    create_foundry_client,
)
from azure_integration.foundry.discovery import resolve_project_by_endpoint
from azure_integration.foundry.helpers.catalog_sync import (
    catalog_delete_stub,
    register_catalog_rows,
    unregister_catalog_rows,
)
from azure_integration.foundry.helpers.scope import (
    get_project_endpoint,
    project_endpoint_context,
)
from azure_integration.foundry.kinds import ObjectKind


def _project_endpoint_from_run(run: IntegrationRun) -> str:
    props = run.execution_properties or {}
    endpoint = props.get("projectEndpoint")
    if isinstance(endpoint, str) and endpoint.strip():
        return endpoint.rstrip("/")
    raise ActionExecutionError(
        "projectEndpoint is required on Foundry actions (Foundry project data-plane URL)"
    )


class AbstractFoundryExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_foundry_client()
        self.arm_deployments = create_arm_deployments_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0

    async def execute(self, run: IntegrationRun) -> None:
        endpoint = _project_endpoint_from_run(run)
        project_arm_id: str | None = None
        try:
            project_arm_id = (
                await resolve_project_by_endpoint(endpoint)
            ).project_arm_id
        except ValueError:
            logger.warning(
                f"No discovered Foundry project for endpoint {endpoint}; "
                "catalog upserts may miss foundryProject relation"
            )
        with project_endpoint_context(endpoint, project_arm_id=project_arm_id):
            await self.execute_foundry(run)

    @abstractmethod
    async def execute_foundry(self, run: IntegrationRun) -> None:
        raise NotImplementedError

    @property
    def project_endpoint(self) -> str:
        return get_project_endpoint()

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        await register_catalog_rows(kind, [raw], run)

    async def unregister_by_identifier(
        self, kind: str, identifier: str, run: IntegrationRun
    ) -> None:
        await unregister_catalog_rows(
            kind, [catalog_delete_stub(kind, identifier)], run
        )

    async def sync_agent_catalog(self, agent_id: str, run: IntegrationRun) -> None:
        """Fetch agent from Foundry and upsert catalog without waiting for resync."""
        agent_payload = await self.client.send_api_request(
            self.client.build_url(self.project_endpoint, f"agents/{agent_id}"),
        )
        if not isinstance(agent_payload, dict) or not agent_payload:
            logger.warning(f"Could not load agent {agent_id} for catalog sync")
            return

        await self.register_entity(ObjectKind.AGENT, agent_payload, run)
