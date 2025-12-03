# ============================================================================
# Integration Class - Entry point for the Harbor integration
# ============================================================================


from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from harbor.config.app_config import HarborPortAppConfig

class HarborIntegration(BaseIntegration):
    """Harbor Integration for Ocean.

    This integration enables Port customers to ingest Harbor resources including:
    - Projects: Container image projects and their configurations
    - Users: Harbor user accounts and permissions
    - Repositories: Container image repositories within projects
    - Artifacts: Container images and their associated metadata

    The integration supports flexible filtering and configuration options
    through the selector classes defined above.
    """

    class AppConfigHandlerClass(APIPortAppConfig):
        """Configuration handler for the Harbor integration."""

        CONFIG_CLASS = HarborPortAppConfig
