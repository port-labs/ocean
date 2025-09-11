from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

"""
Zendesk integration configuration

Following Ocean integration patterns for configuration setup.

Purpose: Define integration configuration class
Expected output: Configured integration class for Zendesk
"""


class ZendeskIntegration(BaseIntegration):
    """
    Zendesk integration class extending BaseIntegration
    
    Provides configuration handling for the Zendesk integration
    using Ocean's standard APIPortAppConfig pattern.
    """
    
    class AppConfigHandlerClass(APIPortAppConfig):
        pass