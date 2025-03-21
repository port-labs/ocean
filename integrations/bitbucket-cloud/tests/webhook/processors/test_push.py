import pytest
from unittest.mock import MagicMock, patch
from typing import Any
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook.webhook_client import BitbucketWebhookClient


with patch("initialize_client.init_webhook_client") as mock_init_client:
    from bitbucket_cloud.webhook.processors.push import PushWebhookProcessor


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def push_webhook_processor(
    webhook_client_mock: BitbucketWebhookClient, event: WebhookEvent
) -> PushWebhookProcessor:
    """Create a PushWebhookProcessor with mocked webhook client."""
    push_webhook_processor = PushWebhookProcessor(event)
    push_webhook_processor._webhook_client = webhook_client_mock
    return push_webhook_processor


class TestPushWebhookProcessor:
    @pytest.mark.parametrize(
        "event_key, expected",
        [
            ("repo:push", True),
            ("repo:created", False),
            ("pullrequest:created", False),
            ("invalid:event", False),
        ],
    )
    @pytest.mark.asyncio
    async def test_should_process_event(
        self,
        push_webhook_processor: PushWebhookProcessor,
        event_key: str,
        expected: bool,
    ) -> None:
        """Test that should_process_event correctly identifies valid push events."""
        event = WebhookEvent(
            trace_id="test-trace-id", headers={"x-event-key": event_key}, payload={}
        )
        result = await push_webhook_processor.should_process_event(event)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, push_webhook_processor: PushWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the REPOSITORY kind."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-event-key": "repo:push"},
            payload={},
        )
        result = await push_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.REPOSITORY]

    @pytest.mark.asyncio
    async def test_handle_event(
        self,
        push_webhook_processor: PushWebhookProcessor,
        webhook_client_mock: MagicMock,
    ) -> None:
        """Test handling a push event."""
        # Arrange
        payload = {
            "repository": {"name": "test-repo"},
            "push": {
                "changes": [
                    {
                        "new": {"target": {"hash": "new-hash"}},
                        "old": {"target": {"hash": "old-hash"}},
                        "ref": {"name": "main"},
                    }
                ]
            },
        }
        resource_config = MagicMock()

        # Mock process_diff_stats
        with (
            patch(
                "bitbucket_cloud.gitops.commit_processor.process_diff_stats",
                return_value=([], [{"test": "entity"}]),
            ),
            patch("port_ocean.context.event._get_event_context") as mock_event_context,
            patch("port_ocean.context.ocean.ocean.update_diff") as mock_update_diff,
        ):
            # Mock event context
            mock_event_context.return_value.port_app_config.branch = None
            mock_event_context.return_value.port_app_config.spec_path = ["specs/"]

            # Act
            result = await push_webhook_processor.handle_event(payload, resource_config)

            # Assert
            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 0
            assert len(result.deleted_raw_results) == 0
            mock_update_diff.assert_called_once()

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ({"repository": {}, "push": {}}, True),
            ({"repository": {}}, False),
            ({"push": {}}, False),
            ({}, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_validate_payload(
        self,
        push_webhook_processor: PushWebhookProcessor,
        payload: dict[str, Any],
        expected: bool,
    ) -> None:
        """Test payload validation with various input scenarios."""
        result = await push_webhook_processor.validate_payload(payload)
        assert result == expected
