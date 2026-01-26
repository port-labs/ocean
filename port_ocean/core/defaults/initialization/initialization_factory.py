"""Factory for creating appropriate initialization setup based on configuration."""

from typing import Any, Type
import httpx
from loguru import logger

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
        CreatePortResourcesOrigin.Default: DefaultOriginSetup,
    }

    @staticmethod
    async def create_setup(
        integration_config: IntegrationConfiguration,
        config_class: Type[PortAppConfig],
        is_provision_enabled: bool,
    ) -> BaseSetup:
        """Create appropriate setup based on configuration and feature flags.

        Args:
            integration_config: Integration configuration
            config_class: The Port app config class
            is_provision_enabled: Whether Port provisioning is enabled for this integration

        Returns:
            Appropriate BaseSetup instance
        """
        integration = await ocean.port_client.get_current_integration(
            should_log=False,
            should_raise=False,
        )

        integration_origin: CreatePortResourcesOrigin | None = integration.get(
            "createPortResourcesOrigin", None
        )
        origin = (
            integration_origin
            if integration_origin
            else InitializationFactory._determine_origin(
                integration_config, is_provision_enabled
            )
        )

        setup_instance = InitializationFactory._SETUP_CLASSES[origin](
            port_client=ocean.port_client,
            integration_config=integration_config,
            config_class=config_class,
        )

        if not integration:
            try:
                logger.info(
                    "Integration does not exist, Creating new integration with default mapping"
                )
                integration = await ocean.port_client.create_integration(
                    integration_config.integration.type,
                    integration_config.event_listener.get_changelog_destination_details(),
                    port_app_config=setup_instance._default_mapping,
                    actions_processing_enabled=integration_config.actions_processor.enabled,
                    create_port_resources_origin=origin,
                )
            except httpx.HTTPStatusError as err:
                logger.error(
                    f"Failed to verify integration state: {err.response.text}."
                )
                raise err

        await InitializationFactory._verify_integration_configuration(
            integration_config, integration
        )
        return setup_instance

    @staticmethod
    def _determine_origin(
        integration_config: IntegrationConfiguration,
        is_provision_enabled: bool,
    ) -> CreatePortResourcesOrigin:
        """Determine resource origin based on configuration and feature flags.

        Args:
            integration_config: Integration configuration
            is_provision_enabled: Whether provision is enabled

        Returns:
            The determined CreatePortResourcesOrigin
        """
        match integration_config.create_port_resources_origin:
            case CreatePortResourcesOrigin.Empty:
                logger.info("Creating empty setup")
                return CreatePortResourcesOrigin.Empty
            case CreatePortResourcesOrigin.Ocean:
                logger.warning(
                    "The Ocean origin setup has been renamed to Default. Please use the Default origin setup."
                )
                return CreatePortResourcesOrigin.Default
            case CreatePortResourcesOrigin.Port | None:
                if is_provision_enabled:
                    logger.info("Creating Port origin setup for provisioned defaults")
                    return CreatePortResourcesOrigin.Port
                logger.warning("Provision is not supported, falling back to Default")
                return CreatePortResourcesOrigin.Default
            case _:
                logger.info("Creating Default origin setup")
                return CreatePortResourcesOrigin.Default

    @staticmethod
    async def _verify_integration_configuration(
        integration_config: IntegrationConfiguration,
        integration: dict[str, Any],
    ) -> None:
        """Verify integration configuration and update if necessary."""
        logger.info("Checking for diff in integration configuration")
        changelog_destination = (
            integration_config.event_listener.get_changelog_destination_details()
        )
        if (
            integration.get("changelogDestination") != changelog_destination
            or integration.get("installationAppType")
            != integration_config.integration.type
            or integration.get("version") != ocean.port_client.integration_version
            or integration.get("actionsProcessingEnabled")
            != integration_config.actions_processor.enabled
        ):
            await ocean.port_client.patch_integration(
                _type=integration_config.integration.type,
                changelog_destination=changelog_destination,
                actions_processing_enabled=integration_config.actions_processor.enabled,
            )
