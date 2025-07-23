from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class ObjectKind:
    REPOSITORY = "repositories"
    ISSUES = "issues"


class AikidoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        pass
