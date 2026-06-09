import pytest
from typing import Any, Generator
from unittest.mock import MagicMock, PropertyMock, patch

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_client import PORT_AUTH_HEADER_NAME
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)


class MockWebhookProcessor(BaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[Any]:
        return []

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: dict[str, Any], resource_config: Any) -> Any:
        return None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True


@pytest.fixture
def processor() -> MockWebhookProcessor:
    mock_event = WebhookEvent(trace_id="test", payload={}, headers={})
    return MockWebhookProcessor(mock_event)


@pytest.fixture
def mock_integration_config_with_secret() -> Generator[dict[str, str], None, None]:
    config = {"datadog_service_dependency_env": "prod", "webhook_secret": "test_token"}
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture
def mock_integration_config_without_secret() -> Generator[dict[str, str], None, None]:
    config = {"datadog_service_dependency_env": "prod"}
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.mark.asyncio
async def test_authenticate_with_valid_custom_auth_header(
    processor: MockWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    headers = {PORT_AUTH_HEADER_NAME: "test_token"}
    assert await processor.authenticate({}, headers) is True


@pytest.mark.asyncio
async def test_authenticate_without_webhook_secret_no_auth_header(
    processor: MockWebhookProcessor,
    mock_integration_config_without_secret: Generator[dict[str, str], None, None],
) -> None:
    assert await processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_authenticate_without_webhook_secret_with_auth_header(
    processor: MockWebhookProcessor,
    mock_integration_config_without_secret: Generator[dict[str, str], None, None],
) -> None:
    headers = {PORT_AUTH_HEADER_NAME: "test_token"}
    # When no secret is configured, authentication is disabled: all requests pass.
    assert await processor.authenticate({}, headers) is True


@pytest.mark.asyncio
async def test_authenticate_with_invalid_secret(
    processor: MockWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    headers = {PORT_AUTH_HEADER_NAME: "wrong_token"}
    assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_with_missing_custom_header(
    processor: MockWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    assert await processor.authenticate({}, {}) is False


@pytest.mark.asyncio
async def test_authenticate_with_case_insensitive_custom_header(
    processor: MockWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    headers = {PORT_AUTH_HEADER_NAME.lower(): "test_token"}
    assert await processor.authenticate({}, headers) is True


def test_extract_org_id_returns_str_or_none() -> None:
    assert BaseWebhookProcessor._extract_org_id({"org_id": 12345}) == "12345"
    assert BaseWebhookProcessor._extract_org_id({"org_id": "abc"}) == "abc"
    assert BaseWebhookProcessor._extract_org_id({}) is None


def test_get_client_for_payload_delegates_to_manager(
    processor: MockWebhookProcessor,
    mock_client_manager: MagicMock,
) -> None:
    # The processor extracts the org id and hands resolution to the client manager.
    resolved = processor._get_client_for_payload({"org_id": 222})

    mock_client_manager.get_client_for_org.assert_called_once_with("222")
    assert resolved is mock_client_manager.get_client_for_org.return_value
