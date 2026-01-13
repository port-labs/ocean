"""Port origin setup - creates resources with defaults provisioned by Port."""

from typing import Type

from loguru import logger

from port_ocean.core.defaults.common import get_port_integration_defaults
from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class PortOriginSetup(BaseSetup):
    """Setup that creates resources with defaults provisioned by Port."""

    async def initialize(self, config_class: Type[PortAppConfig]) -> None:
        """Initialize integration with resources provisioned by Port."""
        logger.info(
            "Starting Port origin setup - resources will be provisioned by Port"
        )

        defaults = get_port_integration_defaults(
            config_class, self.integration_config.resources_path
        )

        # When creating in Port, send only the port app config without actual resource creation
        default_config = (
            defaults.port_app_config
            if defaults
            and defaults.port_app_config
            and self.integration_config.initialize_port_resources
            else PortAppConfig(resources=[])
        )

        await self._initialize_required_integration_settings(
            default_mapping=default_config,
        )

        logger.info(
            "Port origin setup completed - resources provisioning delegated to Port"
        )
