from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from clickup.overrides import ClickUpPortAppConfig


class ClickUpIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClickUpPortAppConfig
