from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class EmptySetup(BaseSetup):
    """Setup that creates only integration mapping without creating any blueprints or resources."""

    @property
    def _default_mapping(self) -> PortAppConfig | None:
        return self.config_class(resources=[])

    async def _setup(self) -> None:
        """Initialize integration with empty mapping only."""

        await self.port_client.patch_integration(
            port_app_config=self._default_mapping,
            are_port_resources_initialized=True,
        )
