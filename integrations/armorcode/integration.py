from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class ObjectKind:
    PRODUCT = "product"
    SUB_PRODUCT = "sub-product"
    FINDING = "finding"


class ArmorcodeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        pass
