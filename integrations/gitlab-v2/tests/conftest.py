"""
Global pytest configuration for the integration tests
"""

from typing import Any, Generator
from unittest.mock import MagicMock, patch
import importlib

import pytest
from port_ocean.context.event import EventContext

from integration import GitlabPortAppConfig

importlib.import_module("gitlab.clients")
importlib.import_module("gitlab.clients.client_factory")

# Patch the client factory globally before any tests run
# This prevents the error during module import
client_factory_patch = patch("gitlab.clients.client_factory.create_gitlab_client")
mock_create_client = client_factory_patch.start()
mock_client = MagicMock()
mock_create_client.return_value = mock_client


@pytest.fixture(autouse=True)
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Provide port app config via event context, like resync handlers do."""
    mock_event = MagicMock(spec=EventContext)
    mock_event.port_app_config = GitlabPortAppConfig(include_authenticated_user=True)

    with (
        patch("port_ocean.context.event.event", mock_event),
        patch("gitlab.clients.utils.event", mock_event),
        patch("gitlab.clients.gitlab_client.event", mock_event),
        patch("gitlab.webhook.setup.event", mock_event),
    ):
        yield mock_event


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """Clean up patches after all tests are complete"""
    client_factory_patch.stop()
