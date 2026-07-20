from typing import Any
from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class PortOriginSetup(BaseSetup):
    """Setup that creates resources with defaults provisioned by Port."""

    @property
    def _default_mapping(self) -> PortAppConfig | None:
        return None

    async def _setup(self, current_config: dict[str, Any] | None) -> None:
        """Initialize integration with resources provisioned by Port."""

        await self.port_client.poll_integration_until_default_provisioning_is_complete()
