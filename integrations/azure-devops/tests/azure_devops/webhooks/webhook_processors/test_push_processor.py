from typing import Any, Dict, Generator
import pytest
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
)
from azure_devops.webhooks.webhook_processors.push_processor import PushWebhookProcessor
from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def push_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PushWebhookProcessor:
    mock_client = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.push_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PushWebhookProcessor(event)


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


@pytest.mark.asyncio
async def test_push_should_process_event(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {"url": "http://example.com"},
        },
        headers={},
    )
    assert await push_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await push_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_push_get_matching_kinds(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await push_processor.get_matching_kinds(event)
    assert "repository" in kinds
    assert "file" in kinds


@pytest.mark.asyncio
async def test_push_validate_payload(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload: Dict[str, Any] = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {"url": "http://example.com"},
    }
    assert await push_processor.validate_payload(valid_payload) is True

    invalid_payload: Dict[str, Any] = {"missing": "fields"}
    assert await push_processor.validate_payload(invalid_payload) is False
