from unittest.mock import patch

import pytest

from harbor.webhooks.base import HarborAbstractBaseWebhookProcessor


class ConcreteProcessor(HarborAbstractBaseWebhookProcessor):
    async def validate_payload(self, payload):
        return True

    async def handle_event(self, payload, resource_config):
        pass

    async def get_matching_kinds(self, event):
        return ["test"]


class TestHarborAbstractBaseWebhookProcessor:
    @pytest.mark.asyncio
    async def test_authenticate_with_valid_secret(self):
        processor = ConcreteProcessor()

        with patch("harbor.webhooks.base.ocean") as mock_ocean:
            mock_ocean.integration_config.get.return_value = "Bearer test-secret"

            headers = {"Authorization": "Bearer test-secret"}
            result = await processor.authenticate({}, headers)

            assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_secret(self):
        processor = ConcreteProcessor()

        with patch("harbor.webhooks.base.ocean") as mock_ocean:
            mock_ocean.integration_config.get.return_value = "Bearer correct-secret"

            headers = {"Authorization": "Bearer wrong-secret"}
            result = await processor.authenticate({}, headers)

            assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_with_lowercase_authorization_header(self):
        processor = ConcreteProcessor()

        with patch("harbor.webhooks.base.ocean") as mock_ocean:
            mock_ocean.integration_config.get.return_value = "Bearer test-secret"

            headers = {"authorization": "Bearer test-secret"}
            result = await processor.authenticate({}, headers)

            assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_without_authorization_header(self):
        processor = ConcreteProcessor()

        with patch("harbor.webhooks.base.ocean") as mock_ocean:
            mock_ocean.integration_config.get.return_value = "Bearer test-secret"

            headers = {}
            result = await processor.authenticate({}, headers)

            assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_without_configured_secret(self):
        processor = ConcreteProcessor()

        with patch("harbor.webhooks.base.ocean") as mock_ocean:
            mock_ocean.integration_config.get.return_value = None

            headers = {}
            result = await processor.authenticate({}, headers)

            assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_always_returns_true(self):
        processor = ConcreteProcessor()

        from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

        event = WebhookEvent(payload={}, headers={})
        result = await processor.should_process_event(event)

        assert result is True
