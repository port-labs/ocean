from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from config import GitlabPortAppConfig


class GitAppConfigHandler(APIPortAppConfig):
    CONFIG_CLASS = GitlabPortAppConfig


class GitlabIntegration(BaseIntegration):
    AppConfigHandlerClass = GitAppConfigHandler
