"""
HTTP Server Integration Class

Defines the integration class that uses custom configuration models.
"""

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from http_server.overrides import HttpServerPortAppConfig


class HttpServerIntegration(BaseIntegration):
    """HTTP Server integration with custom configuration"""
    
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = HttpServerPortAppConfig
