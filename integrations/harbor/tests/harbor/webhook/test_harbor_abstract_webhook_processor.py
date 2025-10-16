"""Tests for Harbor webhook abstract processor."""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock, patch

from harbor.webhook.harbor_abstract_webhook_processor import (
    HarborAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class ConcreteWebhookProcessor(HarborAbstractWebhookProcessor):
    """Concrete implementation for testing."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test-kind"]

    async def handle_event(self, payload: Dict[str, Any], resource_config: ResourceConfig) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True


class TestHarborAbstractWebhookProcessor:
    """Test HarborAbstractWebhookProcessor."""

    @pytest.fixture
    def mock_webhook_event(self) -> WebhookEvent:
        """Create mock webhook event."""
        return WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")

    @pytest.fixture
    def processor(self, mock_webhook_event: WebhookEvent) -> ConcreteWebhookProcessor:
        """Create processor instance."""
        return ConcreteWebhookProcessor(mock_webhook_event)

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_secret(self, processor: ConcreteWebhookProcessor) -> None:
        """Test authentication with valid secret."""
        payload: Dict[str, Any] = {"type": "PUSH_ARTIFACT"}
        headers: Dict[str, str] = {"authorization": "test-secret"}

        with patch(
            "harbor.webhook.harbor_abstract_webhook_processor.ocean"
        ) as mock_ocean:
            mock_integration_config = MagicMock()
            mock_integration_config.get.return_value = "test-secret"
            mock_ocean.integration_config = mock_integration_config

            result = await processor.authenticate(payload, headers)
            assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_secret(self, processor: ConcreteWebhookProcessor) -> None:
        """Test authentication with invalid secret."""
        payload: Dict[str, Any] = {"type": "PUSH_ARTIFACT"}
        headers: Dict[str, str] = {"authorization": "wrong-secret"}

        with patch(
            "harbor.webhook.harbor_abstract_webhook_processor.ocean"
        ) as mock_ocean:
            mock_integration_config = MagicMock()
            mock_integration_config.get.return_value = "test-secret"
            mock_ocean.integration_config = mock_integration_config

            result = await processor.authenticate(payload, headers)
            assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_missing_header(self, processor: ConcreteWebhookProcessor) -> None:
        """Test authentication with missing authorization header."""
        payload: Dict[str, Any] = {"type": "PUSH_ARTIFACT"}
        headers: Dict[str, str] = {}

        with patch(
            "harbor.webhook.harbor_abstract_webhook_processor.ocean"
        ) as mock_ocean:
            mock_integration_config = MagicMock()
            mock_integration_config.get.return_value = "test-secret"
            mock_ocean.integration_config = mock_integration_config

            result = await processor.authenticate(payload, headers)
            assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event(self, processor: ConcreteWebhookProcessor) -> None:
        """Test should_process_event always returns True."""
        mock_event = MagicMock()
        result = await processor.should_process_event(mock_event)
        assert result is True
