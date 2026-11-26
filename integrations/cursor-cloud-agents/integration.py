from cursor_cloud_agents.integration import CursorCloudAgentsPortAppConfig
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class CursorCloudAgentsIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CursorCloudAgentsPortAppConfig
