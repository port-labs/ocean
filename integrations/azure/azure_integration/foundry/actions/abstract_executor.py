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
        return self.client.rate_limiter.is_close_to_rate_limit()

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return self.client.rate_limiter.seconds_until_rate_limit_reset()

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        """Upsert into catalog; log failures and continue (do not fail the action)."""
        try:
            await ocean.register_raw(kind, [raw])
        except Exception as error:
            message = f"Failed to upsert {kind} into the catalog (continuing): {error}"
            logger.warning(message)
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )

    async def unregister_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        """Delete from catalog; log failures and continue (do not fail the action)."""
        try:
            await ocean.unregister_raw(kind, [raw])
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
            ObjectKind.FOUNDRY_AGENT,
            enrich_with_project(agent_payload, project_endpoint=project_endpoint),
            run,
        )


class FoundryAgentExecutor(AbstractFoundryExecutor):
    """Agent CRUD: defer only on 429. Azure does not expose remaining RPM up front."""

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return self.client.rate_limiter.hard_block_seconds() > 0

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return self.client.rate_limiter.hard_block_seconds()


class ArmDeploymentExecutor(AbstractFoundryExecutor):
    """Deploy/delete via ARM; defer on ARM remaining headers or Foundry 429."""

    def __init__(self) -> None:
        super().__init__()
        self.arm_deployments: ArmDeploymentsClient = create_arm_deployments_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        # Ignore Foundry soft headroom; ARM writes use a different pool.
        return (
            self.client.rate_limiter.hard_block_seconds() > 0
            or self.arm_deployments.rate_limiter.is_close_to_rate_limit()
        )

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return max(
            self.client.rate_limiter.hard_block_seconds(),
            self.arm_deployments.rate_limiter.seconds_until_rate_limit_reset(),
        )
