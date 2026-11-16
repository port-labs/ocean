from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.webhook_processors.conversation_webhook_processor import (
    ConversationWebhookProcessor,
)


@pytest.mark.asyncio
async def test_authenticate_allows_when_no_signing_secret() -> None:
    event = MagicMock()
    event._original_request = None
    processor = ConversationWebhookProcessor(event=event)
    with patch(
        "azure_integration.foundry.webhook_processors.abstract_webhook_processor.iter_signing_secrets",
        return_value=[],
    ):
        assert await processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_authenticate_verifies_when_secret_present() -> None:
    request = MagicMock()
    request.body = AsyncMock(return_value=b'{"type":"response.completed"}')
    event = MagicMock()
    event._original_request = request
    processor = ConversationWebhookProcessor(event=event)
    with (
        patch(
            "azure_integration.foundry.webhook_processors.abstract_webhook_processor.iter_signing_secrets",
            return_value=["whsec_dGVzdA=="],
        ),
        patch(
            "azure_integration.foundry.webhook_processors.abstract_webhook_processor.verify_standard_webhook",
            side_effect=None,
        ) as verify,
    ):
        assert await processor.authenticate({}, {"webhook-id": "1"}) is True
        verify.assert_called_once()
