from typing import Any, Dict

from loguru import logger

from port_ocean.core.handlers.port_app_config.base import BasePortAppConfig


class APIPortAppConfig(BasePortAppConfig):
    async def _get_port_app_config(self) -> Dict[str, Any]:
        logger.info("Fetching port app config")
        integration = await self.context.port_client.get_integration(
            self.context.config.integration.identifier
        )
        return integration["config"]
