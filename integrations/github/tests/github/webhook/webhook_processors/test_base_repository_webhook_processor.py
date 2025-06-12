from typing import Any, Dict
from port_ocean.context.event import event_context
import pytest
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from integration import GithubPortAppConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults


class MockBaseRepositoryProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test_kind"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


@pytest.fixture
def base_repository_processor(
    mock_webhook_event: WebhookEvent,
) -> MockBaseRepositoryProcessor:
    return MockBaseRepositoryProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestBaseRepositoryWebhookProcessor:
    @pytest.mark.parametrize(
        "payload,visibility_filter,expected",
        [
            # Test with missing repository
            ({}, "all", False),
            # Test with missing repository name
            ({"repository": {}}, "all", False),
            # Test with valid repository and "all" visibility
            ({"repository": {"name": "test-repo"}}, "all", True),
            # Test with matching visibility
            (
                {"repository": {"name": "test-repo", "visibility": "private"}},
                "private",
                True,
            ),
            # Test with non-matching visibility
            (
                {"repository": {"name": "test-repo", "visibility": "public"}},
                "private",
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        base_repository_processor: MockBaseRepositoryProcessor,
        payload: Dict[str, Any],
        visibility_filter: str,
        expected: bool,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        # Mock the port_app_config
        mock_port_app_config.repository_type = visibility_filter

        async with event_context("test_event") as event:
            event.port_app_config = mock_port_app_config
            result = await base_repository_processor.validate_payload(payload)
            assert result is expected
