from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.clients.client_factory import create_foundry_arm_client
from azure_integration.foundry.clients.foundry_arm_client import FoundryArmClient


class ArmDeploymentExecutor(AbstractFoundryExecutor):
    """Deploy/delete via ARM; defer on ARM remaining headers or Foundry 429."""

    def __init__(self) -> None:
        super().__init__()
        self.foundry_arm: FoundryArmClient = create_foundry_arm_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return (
            self.client.rate_limiter.is_close_to_rate_limit()
            or self.foundry_arm.rate_limiter.is_close_to_rate_limit()
        )

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return max(
            self.client.rate_limiter.seconds_until_rate_limit_reset(),
            self.foundry_arm.rate_limiter.seconds_until_rate_limit_reset(),
        )
