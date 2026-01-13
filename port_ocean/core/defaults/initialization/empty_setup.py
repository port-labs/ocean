"""Empty setup - creates only the integration mapping without blueprints or resources."""

from typing import Type

from loguru import logger

from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class EmptySetup(BaseSetup):
    """Setup that creates only integration mapping without creating any blueprints or resources."""

    async def initialize(self, config_class: Type[PortAppConfig]) -> None:
        """Initialize integration with empty mapping only."""
        logger.info("Starting empty setup - creating integration mapping only")

        # Create empty config with no resources
        empty_config = PortAppConfig(resources=[])

        # Initialize integration settings with empty mapping
        await self._initialize_required_integration_settings(
            default_mapping=empty_config,
        )

        logger.info(
            "Empty setup completed - integration mapping created without resources"
        )
