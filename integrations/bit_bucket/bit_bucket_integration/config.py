import os
import logging
from dotenv import load_dotenv
from types import SimpleNamespace

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ConfigWrapper:
    """Encapsulates configuration settings for the Bitbucket integration."""

    def __init__(self):
        self.integration = SimpleNamespace(
            identifier="bitbucket",
            bitbucket=self._load_bitbucket_config()
        )

    def _load_bitbucket_config(self) -> SimpleNamespace:
        """Loads Bitbucket-related configuration with validation."""
        workspace = os.getenv("BITBUCKET_WORKSPACE")
        username = os.getenv("BITBUCKET_USERNAME")
        app_password = os.getenv("BITBUCKET_APP_PASSWORD")

        if not workspace:
            logger.warning("BITBUCKET_WORKSPACE is not set.")
        if not username:
            logger.warning("BITBUCKET_USERNAME is not set.")
        if not app_password:
            logger.warning("BITBUCKET_APP_PASSWORD is not set.")

        return SimpleNamespace(
            workspace=workspace,
            username=username,
            app_password=app_password
        )

    def get(self):
        """Provides access to the config object."""
        return self.integration

# Global Config Instance
CONFIG = ConfigWrapper()