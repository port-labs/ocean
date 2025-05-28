import os
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean import Ocean
from port_ocean.context.event import EventContext
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.tests.helpers.ocean_app import get_integration_ocean_app

from integration import SonarQubePortAppConfig

from .fixtures import ANALYSIS, COMPONENT_PROJECTS, ISSUES, PORTFOLIOS, PURE_PROJECTS

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


@pytest.fixture
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "sonar_api_token": "token",
            "sonar_url": "https://sonarqube.com",
            "sonar_organization_id": "organization_id",
            "sonar_is_on_premise": False,
            "webhook_secret": "12345",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Fixture to mock the event context."""
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._aborted = False
    mock_event._port_app_config = SonarQubePortAppConfig

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


def app() -> Ocean:
    config = {
        "event_listener": {"type": "POLLING"},
        "integration": {
            "config": {
                "sonar_api_token": "token",
                "sonar_url": "https://sonarqube.com",
                "sonar_organization_id": "organization_id",
                "sonar_is_on_premise": False,
                "webhook_secret": "12345",
            }
        },
        "port": {
            "client_id": "bla",
            "client_secret": "bla",
        },
    }
    application = get_integration_ocean_app(INTEGRATION_PATH, config)
    return application


@pytest.fixture(scope="session")
def ocean_app() -> Ocean:
    return app()


@pytest.fixture(scope="session")
def integration_path() -> str:
    return INTEGRATION_PATH


@pytest.fixture(scope="session")
def projects() -> list[dict[str, Any]]:
    return PURE_PROJECTS


@pytest.fixture(scope="session")
def component_projects() -> list[dict[str, Any]]:
    return COMPONENT_PROJECTS


@pytest.fixture(scope="session")
def issues() -> list[dict[str, Any]]:
    return ISSUES


@pytest.fixture(scope="session")
def portfolios() -> list[dict[str, Any]]:
    return PORTFOLIOS


@pytest.fixture(scope="session")
def analysis() -> list[dict[str, Any]]:
    return ANALYSIS
