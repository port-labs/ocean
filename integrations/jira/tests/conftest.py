import os
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from port_ocean import Ocean
from port_ocean.context.event import EventContext
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.tests.helpers.ocean_app import get_integration_ocean_app

from integration import JiraPortAppConfig

from .fixtures import ISSUES, PROJECTS

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


@pytest.fixture()
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "jira_host": "https://getport.atlassian.net",
            "atlassian_user_email": "jira@atlassian.net",
            "atlassian_user_token": "asdf",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture(scope="session")
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Fixture to mock the event context."""
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._aborted = False
    mock_event._port_app_config = JiraPortAppConfig

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


def app() -> Ocean:
    config = {
        "event_listener": {"type": "POLLING"},
        "integration": {
            "config": {
                "jira_host": "https://getport.atlassian.net",
                "atlassian_user_email": "jira@atlassian.net",
                "atlassian_user_token": "asdf",
            }
        },
        "port": {
            "client_id": "bla",
            "client_secret": "bla",
        },
    }
    application = get_integration_ocean_app(INTEGRATION_PATH, config)
    return application


@pytest.fixture
def ocean_app() -> Ocean:
    return app()


@pytest.fixture(scope="session")
def integration_path() -> str:
    return INTEGRATION_PATH


@pytest.fixture(scope="session")
def projects() -> list[dict[str, Any]]:
    return PROJECTS


@pytest.fixture(scope="session")
def issues() -> list[dict[str, Any]]:
    return ISSUES
