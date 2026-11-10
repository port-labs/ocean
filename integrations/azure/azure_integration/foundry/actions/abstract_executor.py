from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.clients.arm_deployments_client import (
    ArmDeploymentsClient,
)
from azure_integration.foundry.clients.client_factory import (
    create_arm_deployments_client,
    create_foundry_client,
)
from azure_integration.foundry.helpers.utils import enrich_with_project
from azure_integration.foundry.kinds import ObjectKind


class AbstractFoundryExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_foundry_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        """Defer a new run when a prior Foundry response showed the quota nearly exhausted."""
        return self.client.rate_limiter.is_close_to_rate_limit()

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return self.client.rate_limiter.seconds_until_rate_limit_reset()

    async def register_entity(
        self,
        kind: str,
        raw: dict[str, Any],
        run: IntegrationRun,
        *,
        project_endpoint: str,
    ) -> None:
        """Best-effort catalog upsert; failures are logged and never fail the action."""
        try:
            enriched = enrich_with_project(raw, project_endpoint=project_endpoint)
            await ocean.register_raw(kind, [enriched])
        except Exception as error:
            message = f"Failed to upsert {kind} into the catalog (continuing): {error}"
            logger.warning(message)
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )

    async def unregister_by_identifier(
        self,
        kind: str,
        identifier: str,
        run: IntegrationRun,
        *,
        project_endpoint: str,
    ) -> None:
        """Best-effort catalog delete; failures are logged and never fail the action."""
        try:
            stub = enrich_with_project(
                {"id": identifier, "name": identifier},
                project_endpoint=project_endpoint,
            )
            await ocean.unregister_raw(kind, [stub])
        except Exception as error:
            message = f"Failed to delete {kind} from the catalog (continuing): {error}"
            logger.warning(message)
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )

    async def sync_agent_catalog(
        self, agent_id: str, run: IntegrationRun, *, project_endpoint: str
    ) -> None:
        """Fetch agent from Foundry and upsert catalog without waiting for resync."""
        agent_payload = await self.client.send_api_request(
            self.client.build_url(project_endpoint, f"agents/{agent_id}"),
        )
        if not isinstance(agent_payload, dict) or not agent_payload:
            logger.warning(f"Could not load agent {agent_id} for catalog sync")
            return

        await self.register_entity(
            ObjectKind.AGENT, agent_payload, run, project_endpoint=project_endpoint
        )


class ArmDeploymentExecutor(AbstractFoundryExecutor):
    """Deploy and delete model deployments go through Azure Resource Manager."""

    def __init__(self) -> None:
        super().__init__()
        self.arm_deployments: ArmDeploymentsClient = create_arm_deployments_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return (
            await super().is_close_to_rate_limit(run)
            or self.arm_deployments.rate_limiter.is_close_to_rate_limit()
        )

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return max(
            await super().get_remaining_seconds_until_rate_limit(run),
            self.arm_deployments.rate_limiter.seconds_until_rate_limit_reset(),
        )
