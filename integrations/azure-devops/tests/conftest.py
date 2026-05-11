from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

TEST_INTEGRATION_CONFIG: Dict[str, Any] = {
    "organization_url": "https://dev.azure.com/test-org",
    "personal_access_token": "test-pat",
    "organization_urls": None,
    "client_id": None,
    "client_secret": None,
    "tenant_id": None,
    "webhook_secret": "test-secret",
    "webhook_auth_username": "port",
    "is_projects_limited": False,
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize the Port Ocean context for tests.

    Idempotent: re-uses the existing context if already initialized.
    Resets ``ocean.integration_config`` to ``TEST_INTEGRATION_CONFIG`` on
    every test so that one test's mutations to integration_config
    (e.g. flipping to Service Principal mode) don't leak into the next.
    """
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.is_saas = MagicMock(return_value=False)
        mock_ocean_app.config.integration.config = dict(TEST_INTEGRATION_CONFIG)
        mock_ocean_app.config.client_timeout = 60
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://baseurl.com"
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    for key, value in TEST_INTEGRATION_CONFIG.items():
        ocean.integration_config[key] = value


@pytest.fixture
def mock_context(mock_ocean_context: None) -> PortOceanContext:
    return ocean


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def mock_event_context() -> Generator[None, None, None]:
    mock_port_app_config = PortAppConfig(resources=[])

    mock_context = EventContext(
        event_type="WEBHOOK",
        attributes={
            "azure_devops_client": MagicMock(),
            "port_app_config": mock_port_app_config,
        },
    )

    _event_context_stack.push(mock_context)
    yield
    _event_context_stack.pop()


@pytest.fixture
def push_config() -> ResourceConfig:
    return ResourceConfig(
        kind="repository",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".repository.id",
                    title=".repository.name",
                    blueprint='"repository"',
                    properties={
                        "url": ".repository.url",
                        "defaultBranch": ".repository.defaultBranch",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def pull_request_config() -> ResourceConfig:
    return ResourceConfig(
        kind="pull_request",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".pullRequestId",
                    title=".title",
                    blueprint='"pull_request"',
                    properties={
                        "url": ".url",
                        "status": ".status",
                    },
                    relations={},
                )
            )
        ),
    )
