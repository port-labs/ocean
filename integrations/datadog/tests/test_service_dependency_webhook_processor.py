import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from webhook_processors.service_dependency_webhook_processor import ServiceDependencyWebhookProcessor
from integration import ObjectKind
from typing import Any


@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test", payload={}, headers={})


@pytest.fixture
def processor(mock_event: WebhookEvent) -> ServiceDependencyWebhookProcessor:
    return ServiceDependencyWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> Any:
    return {"kind": ObjectKind.SERVICE_DEPENDENCY}


@pytest.mark.asyncio
async def test_authenticate(
    processor: ServiceDependencyWebhookProcessor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_ocean = MagicMock()
    mock_config = MagicMock()
    mock_config.integration.config = {}
    mock_ocean.config = mock_config
    monkeypatch.setattr("port_ocean.context.ocean.ocean", mock_ocean)

    assert await processor.authenticate({}, {}) is True

    mock_config.integration.config = {"webhook_secret": "test_token"}
    headers = {"authorization": "Basic dGVzdF91c2VyOnRlc3RfdG9rZW4="}

    headers = {"authorization": "Basic dGVzdF91c2VyOndyb25nX3Rva2Vu"}
    with patch("base64.b64decode", return_value=b"test_user:wrong_token"):
        assert await processor.authenticate({}, headers) is False

    assert await processor.authenticate({}, {"authorization": "InvalidHeader"}) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: ServiceDependencyWebhookProcessor, mock_event: WebhookEvent
) -> None:
    kinds = await processor.get_matching_kinds(mock_event)
    assert kinds == [ObjectKind.SERVICE_DEPENDENCY]


@pytest.mark.asyncio
async def test_validate_payload(processor: ServiceDependencyWebhookProcessor) -> None:
    assert (
        await processor.validate_payload({"event_type": "service_dependency", "service_id": "123"})
        is True
    )

    assert await processor.validate_payload({"service_id": "123"}) is False

    assert await processor.validate_payload({"event_type": "service_dependency"}) is False


@pytest.mark.asyncio
async def test_handle_event_with_service_dependency(
    processor: ServiceDependencyWebhookProcessor, resource_config: Any
) -> None:
    test_payload = {"event_type": "service_dependency", "service_id": "123"}
    mock_service_dependency = {"id": "123", "name": "Test Service Dependency"}

    with patch("webhook_processors.service_dependency_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_service_dependency.return_value = mock_service_dependency
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_service_dependency.assert_awaited_once_with("123")
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_service_dependency
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_without_service_dependency(
    processor: ServiceDependencyWebhookProcessor, resource_config: Any
) -> None:
    test_payload = {"event_type": "service_dependency", "service_id": "123"}

    with patch("webhook_processors.service_dependency_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_service_dependency.return_value = None
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_monitor.assert_awaited_once_with("123")
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
