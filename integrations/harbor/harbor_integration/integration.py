"""Harbor integration"""

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from .config import HarborPortAppConfig


class HarborKind:
    """Harbor kinds"""

    PROJECT = "project"
    USER = "user"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"


class HarborIntegration(BaseIntegration):
    """Harbor integration"""

    class AppConfigHandlerClass(APIPortAppConfig):
        """Port app config handler"""

        CONFIG_CLASS = HarborPortAppConfig
