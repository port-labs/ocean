from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.clients.arm_deployments_client import (
    ArmDeploymentsClient,
)
from azure_integration.foundry.clients.client_factory import (
    create_arm_deployments_client,
)


class ArmDeploymentExecutor(AbstractFoundryExecutor):
    """Deploy/delete via ARM; defer on ARM remaining headers or Foundry 429."""

    def __init__(self) -> None:
        super().__init__()
        self.arm_deployments: ArmDeploymentsClient = create_arm_deployments_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return (
            self.client.rate_limiter.is_close_to_rate_limit()
            or self.arm_deployments.rate_limiter.is_close_to_rate_limit()
        )

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return max(
            self.client.rate_limiter.seconds_until_rate_limit_reset(),
            self.arm_deployments.rate_limiter.seconds_until_rate_limit_reset(),
        )
