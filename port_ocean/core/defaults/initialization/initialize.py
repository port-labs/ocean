from typing import Any, Type

import httpx
from loguru import logger

from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import ocean
from port_ocean.core.defaults.initialization import InitializationFactory
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import CreatePortResourcesOrigin, IntegrationFeatureFlag
from port_ocean.utils.misc import run_async_in_new_event_loop


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
        or integration.get("installationAppType") != integration_config.integration.type
        or integration.get("version") != ocean.port_client.integration_version
        or integration.get("actionsProcessingEnabled")
        != integration_config.actions_processor.enabled
    ):
        await ocean.port_client.patch_integration(
            _type=integration_config.integration.type,
            changelog_destination=changelog_destination,
            actions_processing_enabled=integration_config.actions_processor.enabled,
        )


async def _initialize_defaults(
    config_class: Type[PortAppConfig], integration_config: IntegrationConfiguration
) -> None:
    """Initialize Port defaults based on integration configuration.

    Args:
        config_class: The Port app config class
        integration_config: Integration configuration settings

    Raises:
        ExceptionGroup: If resource creation fails with errors
    """
    is_integration_provision_enabled = (
        await ocean.port_client.is_integration_provision_enabled(
            integration_config.integration.type
        )
    )

    has_provision_feature_flag = IntegrationFeatureFlag.USE_PROVISIONED_DEFAULTS in (
        await ocean.port_client.get_organization_feature_flags()
    )

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
        else _determine_origin(
            integration_config,
            is_integration_provision_enabled and has_provision_feature_flag,
        )
    )

    logger.info(f"Creating setup instance for origin: {origin}")
    setup_instance = await InitializationFactory.create_setup(
        origin=origin,
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
            logger.error(f"Failed to verify integration state: {err.response.text}.")
            raise err

    await _verify_integration_configuration(integration_config, integration)
    await setup_instance.setup()


def initialize_defaults(
    config_class: Type[PortAppConfig], integration_config: IntegrationConfiguration
) -> None:
    """Entry point for initializing Port defaults.

    Args:
        config_class: The Port app config class
        integration_config: Integration configuration settings
    """
    run_async_in_new_event_loop(_initialize_defaults(config_class, integration_config))
