from typing import Any

from loguru import logger

from port_ocean.core.handlers.port_app_config.base import BasePortAppConfig
from port_ocean.exceptions.api import EmptyPortAppConfigError


class APIPortAppConfig(BasePortAppConfig):
    """Class for obtaining port application configuration through an API.

    This class extends the BasePortAppConfig and provides a method to fetch
    port application configuration from an API integration.
    """

    async def _get_port_app_config(self) -> dict[str, Any]:
        logger.info("Fetching port app config")
        integration = await self.context.port_client.get_current_integration()
        config = integration["config"]

        if not config:
            logger.error(
                "The integration port app config is empty. "
                f"Integration: {integration}, "
                f"Config: {config}. "
                "Please make sure to configure your port app config using Port's API."
            )
            raise EmptyPortAppConfigError()
        return config
