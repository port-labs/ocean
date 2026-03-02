"""Factory for creating appropriate initialization setup based on configuration."""

from typing import Type

from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import ocean
from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.defaults.initialization.empty_setup import EmptySetup
from port_ocean.core.defaults.initialization.default_origin_setup import (
    DefaultOriginSetup,
)
from port_ocean.core.defaults.initialization.port_origin_setup import PortOriginSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import CreatePortResourcesOrigin


class InitializationFactory:
    """Factory for creating appropriate initialization strategy."""

    _SETUP_CLASSES: dict[CreatePortResourcesOrigin, Type[BaseSetup]] = {
        CreatePortResourcesOrigin.Empty: EmptySetup,
        CreatePortResourcesOrigin.Port: PortOriginSetup,
        CreatePortResourcesOrigin.Ocean: DefaultOriginSetup,
        CreatePortResourcesOrigin.Default: DefaultOriginSetup,
    }

    @staticmethod
    async def create_setup(
        origin: CreatePortResourcesOrigin,
        integration_config: IntegrationConfiguration,
        config_class: Type[PortAppConfig],
    ) -> BaseSetup:
        """Create appropriate setup based on configuration and feature flags.

        Args:
            integration_config: Integration configuration
            config_class: The Port app config class
            is_provision_enabled: Whether Port provisioning is enabled for this integration

        Returns:
            Appropriate BaseSetup instance
        """
        return InitializationFactory._SETUP_CLASSES[origin](
            port_client=ocean.port_client,
            integration_config=integration_config,
            config_class=config_class,
        )
