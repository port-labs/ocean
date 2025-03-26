import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.repository import RepositoryWebhookProcessor
from webhook_processors.pull_request import PullRequestWebhookProcessor
from helpers.utils import ObjectKind

@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})

@pytest.fixture
def repository_webhook_processor(mock_webhook_event: WebhookEvent) -> RepositoryWebhookProcessor:
    return RepositoryWebhookProcessor(event=mock_webhook_event)

@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.REPOSITORY,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )

@pytest.mark.asyncio
class TestRepositoryWebhookProcessor:
    async def test_should_process_event_create(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "created", "repository": {}},
            headers={"X-GitHub-Event": "repository"}
        )
        result = await repository_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_delete(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "deleted", "repository": {}},
            headers={"X-GitHub-Event": "repository"}
        )
        result = await repository_webhook_processor.should_process_event(event)
        assert result is True
