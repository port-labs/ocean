from typing import Any, Generator
from unittest.mock import MagicMock, AsyncMock

import pytest
from integration import GitPortAppConfig
from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

# Default org URL used across webhook processor tests.
MOCK_ORG_URL = "https://dev.azure.com/test"
# resourceContainers fragment that satisfies _extract_org_url_from_payload.
MOCK_RESOURCE_CONTAINERS_ACCOUNT = {"account": {"baseUrl": f"{MOCK_ORG_URL}/"}}


def mock_client_manager(monkeypatch: Any, mock_client: MagicMock) -> MagicMock:
    """Patch AzureDevopsClientManager.create_from_ocean_config in base_processor.

    Returns a mock manager whose get_client_for_org always returns *mock_client*.
    All webhook processor tests should use this instead of patching AzureDevopsClient.
    """
    manager = MagicMock()
    manager.get_client_for_org.return_value = mock_client
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor"
        ".AzureDevopsClientManager.create_from_ocean_config",
        lambda: manager,
    )
    return manager


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
def mock_context(monkeypatch: Any) -> PortOceanContext:
    mock_context = AsyncMock()
    mock_context.port_app_config = GitPortAppConfig()
    mock_context.is_saas.return_value = False
    mock_context.config.client_timeout = 60
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return mock_context


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
