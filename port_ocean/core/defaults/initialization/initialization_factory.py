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

        if origin == CreatePortResourcesOrigin.Empty:
            logger.info("Creating empty setup")
            return EmptySetup(
                ocean.port_client, integration_config, has_provision_feature_flag
            )
        elif origin == CreatePortResourcesOrigin.Port:
            logger.info("Creating Port origin setup for provisioned defaults")
            return PortOriginSetup(
                ocean.port_client, integration_config, has_provision_feature_flag
            )
        else:  # Ocean
            logger.info("Creating Ocean origin setup for Ocean-managed resources")
            return OceanOriginSetup(
                ocean.port_client, integration_config, has_provision_feature_flag
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

        # Explicitly set to Empty
        if origin == CreatePortResourcesOrigin.Empty:
            return CreatePortResourcesOrigin.Empty

        # Explicitly set to Ocean
        if origin == CreatePortResourcesOrigin.Ocean:
            return CreatePortResourcesOrigin.Ocean

        # Explicitly set to Port - validate provision support
        if origin == CreatePortResourcesOrigin.Port:
            if is_integration_provision_enabled and has_provision_feature_flag:
                logger.info("Port origin: provision is enabled")
                return CreatePortResourcesOrigin.Port
            else:
                logger.warning(
                    "Port origin requested but provision not supported, falling back to Ocean"
                )
                return CreatePortResourcesOrigin.Ocean

        # Not set (None) - auto-determine based on provision flags
        if not origin:
            if is_integration_provision_enabled and has_provision_feature_flag:
                logger.info("Auto-assigning Port origin (provision enabled)")
                return CreatePortResourcesOrigin.Port
            else:
                logger.info("Auto-assigning Ocean origin (provision not available)")
                return CreatePortResourcesOrigin.Ocean

        return CreatePortResourcesOrigin.Ocean
