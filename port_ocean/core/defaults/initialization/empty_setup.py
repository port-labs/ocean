"""Empty setup - creates only the integration mapping without blueprints or resources."""

from loguru import logger

from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import CreatePortResourcesOrigin


class EmptySetup(BaseSetup):
    """Setup that creates only integration mapping without creating any blueprints or resources."""

    @property
    def _port_resources_origin(self) -> CreatePortResourcesOrigin:
        return CreatePortResourcesOrigin.Empty

    @property
    def _default_mapping(self) -> PortAppConfig:
        return PortAppConfig(resources=[])

    async def _setup(self) -> None:
        """Initialize integration with empty mapping only."""

        logger.info("Starting empty setup - creating integration mapping only")

        empty_config = PortAppConfig(resources=[])
        await self._initialize_required_integration_settings(
            default_mapping=empty_config,
        )
