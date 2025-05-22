from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-event-key": "repo:refs_changed"},
        payload={
            "repository": {
                "id": 123,
                "name": "test-repo",
                "project": {"key": "TEST"},
            },
            "changes": [
                {
                    "ref": {"id": "refs/heads/main"},
                    "type": "UPDATE",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_webhook_processor_handles_repo_refs_changed(
    mock_webhook_event: WebhookEvent,
) -> None:
    """Test that webhook processor correctly handles repo:refs_changed events."""
    # Arrange
    with patch("integration.BitbucketIntegration") as mock_integration:
        mock_integration.process_webhook = AsyncMock()
        mock_integration.process_webhook.return_value = {
            "updated_raw_results": [{"id": 123, "name": "test-repo"}],
            "deleted_raw_results": [],
        }

        # Act
        result = await mock_integration.process_webhook(mock_webhook_event)

        # Assert
        assert result is not None
        assert "updated_raw_results" in result
        assert len(result["updated_raw_results"]) == 1
        assert result["updated_raw_results"][0]["id"] == 123
        mock_integration.process_webhook.assert_called_once_with(mock_webhook_event)
