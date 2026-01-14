"""Factory for creating appropriate initialization setup based on configuration."""

from loguru import logger

from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import ocean
from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.defaults.initialization.empty_setup import EmptySetup
from port_ocean.core.defaults.initialization.ocean_origin_setup import OceanOriginSetup
from port_ocean.core.defaults.initialization.port_origin_setup import PortOriginSetup
from port_ocean.core.models import CreatePortResourcesOrigin


class InitializationFactory:
    """Factory for creating appropriate initialization strategy."""

    _SETUP_CLASSES = {
        CreatePortResourcesOrigin.Empty: EmptySetup,
        CreatePortResourcesOrigin.Port: PortOriginSetup,
        CreatePortResourcesOrigin.Ocean: OceanOriginSetup,
    }

    @staticmethod
    def create_setup(
        integration_config: IntegrationConfiguration,
        is_integration_provision_enabled: bool,
        has_provision_feature_flag: bool,
    ) -> BaseSetup:
        """Create appropriate setup based on configuration and feature flags.

        Args:
            integration_config: Integration configuration
            is_integration_provision_enabled: Whether provision is enabled for this integration
            has_provision_feature_flag: Whether organization has provision feature flag

        Returns:
            Appropriate BaseSetup instance
        """
        origin = InitializationFactory._determine_origin(
            integration_config,
            is_integration_provision_enabled,
            has_provision_feature_flag,
        )

        return InitializationFactory._SETUP_CLASSES[origin](
            port_client=ocean.port_client,
            integration_config=integration_config,
        )

    @staticmethod
    def _determine_origin(
        integration_config: IntegrationConfiguration,
        is_integration_provision_enabled: bool,
        has_provision_feature_flag: bool,
    ) -> CreatePortResourcesOrigin:
        """Determine resource origin based on configuration and feature flags.

        Args:
            integration_config: Integration configuration
            is_integration_provision_enabled: Whether provision is enabled
            has_provision_feature_flag: Whether organization has provision feature flag

        Returns:
            The determined CreatePortResourcesOrigin
        """
        origin = integration_config.create_port_resources_origin
        is_provision_available = (
            is_integration_provision_enabled and has_provision_feature_flag
        )

        match origin:
            case CreatePortResourcesOrigin.Empty:
                logger.info("Creating empty setup")
                return CreatePortResourcesOrigin.Empty
            case CreatePortResourcesOrigin.Ocean:
                logger.info("Creating Ocean origin setup")
                return CreatePortResourcesOrigin.Ocean
            case CreatePortResourcesOrigin.Port | None:
                if is_provision_available:
                    logger.info("Creating Port origin setup for provisioned defaults")
                    return CreatePortResourcesOrigin.Port
                logger.warning(
                    "Port origin requested but provision not supported, falling back to Ocean"
                )
                return CreatePortResourcesOrigin.Ocean
