from unittest.mock import MagicMock

import pytest

from azure_integration.foundry.webhook_processors.conversation_webhook_processor import (
    ConversationWebhookProcessor,
)


@pytest.mark.asyncio
async def test_authenticate_always_allows() -> None:
    processor = ConversationWebhookProcessor(event=MagicMock())
    assert await processor.authenticate({}, {"webhook-id": "1"}) is True
