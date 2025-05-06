from typing import Any, Generator
from unittest.mock import MagicMock, AsyncMock
import pytest
from integration import GitPortAppConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
    PortAppConfig,
)
from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import PortOceanContext


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
