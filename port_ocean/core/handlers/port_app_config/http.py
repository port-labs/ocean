from port_ocean.core.handlers.port_app_config.base import BasePortAppConfigWithContext
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class HttpPortAppConfig(BasePortAppConfigWithContext):
    async def get_port_app_config(self) -> PortAppConfig:
        return await self.context.port_client.get_integration(
            self.context.config.integration.identifier
        )
