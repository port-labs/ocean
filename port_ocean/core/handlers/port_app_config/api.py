from loguru import logger

from port_ocean.core.handlers.port_app_config.base import BasePortAppConfigWithContext
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class APIPortAppConfig(BasePortAppConfigWithContext):
    async def get_port_app_config(self) -> PortAppConfig:
        logger.info("Fetching port app config")
        integration = await self.context.port_client.get_integration(
            self.context.config.integration.identifier
        )

        return PortAppConfig.parse_obj(integration["config"])
