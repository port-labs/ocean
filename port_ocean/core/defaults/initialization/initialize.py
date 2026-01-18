from typing import Type

from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import ocean
from port_ocean.core.defaults.initialization import InitializationFactory
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import IntegrationFeatureFlag
from port_ocean.utils.misc import run_async_in_new_event_loop


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

    setup_cls = InitializationFactory.create_setup(
        integration_config,
        is_integration_provision_enabled,
        has_provision_feature_flag,
    )

    await setup_cls.setup(config_class)


def initialize_defaults(
    config_class: Type[PortAppConfig], integration_config: IntegrationConfiguration
) -> None:
    """Entry point for initializing Port defaults.

    Args:
        config_class: The Port app config class
        integration_config: Integration configuration settings
    """
    run_async_in_new_event_loop(_initialize_defaults(config_class, integration_config))
