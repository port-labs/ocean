"""Port origin setup - creates resources with defaults provisioned by Port."""

from typing import Type

from loguru import logger

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
        return PortAppConfig(resources=[])

    async def initialize(self, config_class: Type[PortAppConfig]) -> None:
        """Initialize integration with resources provisioned by Port."""
        logger.info(
            "Starting Port origin setup - resources will be provisioned by Port"
        )

        await self._initialize_required_integration_settings()
        logger.info(
            "Port origin setup completed - resources provisioning delegated to Port"
        )
