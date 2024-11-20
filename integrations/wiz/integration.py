from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers import APIPortAppConfig

from overrides import WizPortAppConfig


class WizIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = WizPortAppConfig
