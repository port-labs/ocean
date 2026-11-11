from claude_managed_agents.integration import ClaudeManagedAgentsPortAppConfig
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class ClaudeManagedAgentsIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClaudeManagedAgentsPortAppConfig
