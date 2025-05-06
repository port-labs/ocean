import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from typing import Generator
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload={},
        headers={},
    )


@pytest.fixture
def mock_base_processor_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook_processors.launchdarkly_abstract_webhook_processor.LaunchDarklyClient"
    ) as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client
