"""Port origin setup - creates resources with defaults provisioned by Port."""

from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import CreatePortResourcesOrigin


class PortOriginSetup(BaseSetup):
    """Setup that creates resources with defaults provisioned by Port."""

    @property
    def _is_port_provisioning_enabled(self) -> bool:
        return True

    @property
    def _port_resources_origin(self) -> CreatePortResourcesOrigin:
        return CreatePortResourcesOrigin.Port

    @property
    async def _default_mapping(self) -> PortAppConfig:
        return {}

    async def _setup(self) -> None:
        """Initialize integration with resources provisioned by Port."""

        await self.port_client.poll_integration_until_default_provisioning_is_complete()
