import pytest
from unittest.mock import patch, PropertyMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors._abstract_webhook_processor import (
    _AbstractDatadogWebhookProcessor,
)
from typing import Any, Generator


class TestWebhookProcessor(_AbstractDatadogWebhookProcessor):
    """Concrete implementation for testing the abstract webhook processor."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[Any]:
        return []

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: dict[str, Any], resource_config: Any) -> Any:
        return None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True


@pytest.fixture
def processor() -> TestWebhookProcessor:
    mock_event = WebhookEvent(trace_id="test", payload={}, headers={})
    return TestWebhookProcessor(mock_event)


@pytest.fixture
def mock_integration_config_with_secret() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config with webhook secret."""
    config = {"datadog_service_dependency_env": "prod", "webhook_secret": "test_token"}
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture
def mock_integration_config_without_secret() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config without webhook secret."""
    config = {"datadog_service_dependency_env": "prod"}
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.mark.asyncio
async def test_authenticate_with_valid_auth_header(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Base64 encoded "test_user:test_token"
    headers = {"authorization": "Basic dGVzdF91c2VyOnRlc3RfdG9rZW4="}
    assert await processor.authenticate({}, headers) is True


@pytest.mark.asyncio
async def test_authenticate_without_webhook_secret_no_auth_header(
    processor: TestWebhookProcessor,
    mock_integration_config_without_secret: Generator[dict[str, str], None, None],
) -> None:
    # Allow authentication when no webhook secret and no auth header
    assert await processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_authenticate_without_webhook_secret_with_auth_header(
    processor: TestWebhookProcessor,
    mock_integration_config_without_secret: Generator[dict[str, str], None, None],
) -> None:
    # Fail authentication when no webhook secret but auth header is present
    headers = {"authorization": "Basic dGVzdF91c2VyOnRlc3RfdG9rZW4="}
    assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_with_invalid_secret(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Base64 encoded "test_user:wrong_token"
    headers = {"authorization": "Basic dGVzdF91c2VyOndyb25nX3Rva2Vu"}
    assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_with_missing_auth_header(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Fail when webhook secret is configured but no auth header
    assert await processor.authenticate({}, {}) is False


@pytest.mark.asyncio
async def test_authenticate_with_invalid_auth_format(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Test invalid authorization header format
    headers = {"authorization": "InvalidFormat"}
    assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_with_non_basic_auth(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Test non-Basic authorization type
    headers = {"authorization": "Bearer some-token"}
    assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_with_malformed_basic_auth(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Test malformed Basic Auth credentials (missing colon)
    # Base64 encoded "test_user_no_colon"
    headers = {"authorization": "Basic dGVzdF91c2VyX25vX2NvbG9u"}
    assert await processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_authenticate_with_invalid_base64(
    processor: TestWebhookProcessor,
    mock_integration_config_with_secret: Generator[dict[str, str], None, None],
) -> None:
    # Test invalid base64 encoding
    headers = {"authorization": "Basic invalid_base64!@#"}
    assert await processor.authenticate({}, headers) is False
