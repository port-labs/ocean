from typing import Any, Type

from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.core.defaults.common import Defaults, get_port_integration_defaults
from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.exceptions.port_defaults import DefaultsProvisionFailed


class PortOriginSetup(BaseSetup):
    """Setup that creates resources with defaults provisioned by Port.

    Falls back to local defaults from .port/resources/ when provisioning fails.
    """

    def __init__(
        self,
        port_client: PortClient,
        integration_config: IntegrationConfiguration,
        config_class: Type[PortAppConfig],
    ):
        super().__init__(port_client, integration_config, config_class)
        defaults: Defaults | None = get_port_integration_defaults(
            config_class, integration_config.resources_path
        )

        if defaults is None:
            defaults = Defaults(port_app_config=PortAppConfig(resources=[]))

        self._defaults: Defaults = defaults

    @property
    def _default_mapping(self) -> PortAppConfig | None:
        return self._defaults.port_app_config

    async def _setup(self, current_config: dict[str, Any] | None) -> None:
        """Initialize integration with resources provisioned by Port.

        Falls back to patching the integration with local defaults
        if Port provisioning fails and the config is still empty.
        """
        try:
            await self.port_client.poll_integration_until_default_provisioning_is_complete()
        except DefaultsProvisionFailed:
            logger.warning(
                "Port provisioning failed to populate integration config, "
                "falling back to local defaults from .port/resources/"
            )
            if not current_config and self._default_mapping:
                await self.port_client.patch_integration(
                    port_app_config=self._default_mapping,
                )
