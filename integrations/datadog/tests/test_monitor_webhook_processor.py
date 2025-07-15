import pytest
from unittest.mock import AsyncMock, patch, PropertyMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from webhook_processors.monitor_webhook_processor import MonitorWebhookProcessor
from integration import ObjectKind
from typing import Any, Generator


@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test", payload={}, headers={})


@pytest.fixture
def processor(mock_event: WebhookEvent) -> MonitorWebhookProcessor:
    return MonitorWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> Any:
    return {"kind": ObjectKind.MONITOR}


@pytest.fixture
def mock_integration_config() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config."""
    config = {"webhook_secret": "test_token"}
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.mark.asyncio
async def test_failing_authenticate(
    processor: MonitorWebhookProcessor, mock_integration_config: dict[str, str]
) -> None:
    headers = {"authorization": "Basic dGVzdF91c2VyOnRlc3RfdG9rZW4="}
    with patch("base64.b64decode", return_value=b"test_user:test_token"):
        assert await processor.authenticate({}, headers) is True

    headers = {"authorization": "Basic dGVzdF91c2VyOndyb25nX3Rva2Vu"}
    with patch("base64.b64decode", return_value=b"test_user:wrong_token"):
        assert await processor.authenticate({}, headers) is False

    assert await processor.authenticate({}, {"authorization": "InvalidHeader"}) is False


@pytest.mark.asyncio
async def test_authenticate(processor: MonitorWebhookProcessor) -> None:
    # pass authentication (no webhook secret provided)
    assert await processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: MonitorWebhookProcessor, mock_event: WebhookEvent
) -> None:
    kinds = await processor.get_matching_kinds(mock_event)
    assert kinds == [ObjectKind.MONITOR]


@pytest.mark.asyncio
async def test_validate_payload(processor: MonitorWebhookProcessor) -> None:
    assert (
        await processor.validate_payload({"event_type": "alert", "alert_id": "123"})
        is True
    )

    assert await processor.validate_payload({"alert_id": "123"}) is False

    assert await processor.validate_payload({"event_type": "alert"}) is False


@pytest.mark.asyncio
async def test_handle_event_with_monitor(
    processor: MonitorWebhookProcessor, resource_config: Any
) -> None:
    test_payload = {"event_type": "alert", "alert_id": "123"}
    mock_monitor = {"id": "123", "name": "Test Monitor"}

    with patch("webhook_processors.monitor_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_monitor.return_value = mock_monitor
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_monitor.assert_awaited_once_with("123")
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_monitor
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_without_monitor(
    processor: MonitorWebhookProcessor, resource_config: Any
) -> None:
    test_payload = {"event_type": "alert", "alert_id": "123"}

    with patch("webhook_processors.monitor_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_monitor.return_value = None
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_monitor.assert_awaited_once_with("123")
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
