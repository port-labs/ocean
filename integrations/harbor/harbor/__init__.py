from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class HarborIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        pass
