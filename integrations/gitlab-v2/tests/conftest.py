"""
Global pytest configuration for the integration tests
"""

from unittest.mock import MagicMock, patch
from typing import Any

# Patch the client factory globally before any tests run
# This prevents the error during module import
client_factory_patch = patch("gitlab.clients.client_factory.create_gitlab_client")
mock_create_client = client_factory_patch.start()
mock_client = MagicMock()
mock_create_client.return_value = mock_client


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """Clean up patches after all tests are complete"""
    client_factory_patch.stop()
