from port_ocean.core.handlers.port_app_config.base import BasePortAppConfigWithContext
from port_ocean.models.port_app_config import PortAppConfig


class HttpPortAppConfig(BasePortAppConfigWithContext):
    async def get_port_app_config(self) -> PortAppConfig:
        integration_response = await self.context.port_client.get_integration(
            self.context.config.integration.identifier
        )
        return PortAppConfig.parse_obj(integration_response["config"])
