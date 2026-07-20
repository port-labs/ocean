from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from typing import Any
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

# Mocking ocean and init_client before importing the processor to handle class-level side effects
with (
    patch("port_ocean.context.ocean.ocean") as mock_ocean,
    patch("initialize_client.init_client") as mock_init_client,
):
    mock_ocean.integration_config = {"wiz_webhook_verification_token": "test-token"}
    mock_init_client.return_value = MagicMock()
    from wiz.webhook_processors._abstract_webhook_processor import (
        WizAbstractWebhookProcessor,
    )


class WizWebhookProcessorImpl(WizAbstractWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test-kind"]

    async def handle_event(
        self, payload: dict[str, Any], resource_config: ResourceConfig
    ) -> MagicMock:
        return MagicMock()

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        return True


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def base_processor(event: WebhookEvent) -> WizWebhookProcessorImpl:
    return WizWebhookProcessorImpl(event)


@pytest.mark.asyncio
async def test_authenticate_success(base_processor: WizWebhookProcessorImpl) -> None:
    headers = {"authorization": "Bearer test-token"}
    assert await base_processor.authenticate({}, headers) is True


@pytest.mark.asyncio
async def test_authenticate_failure_wrong_token(
    base_processor: WizWebhookProcessorImpl,
) -> None:
    headers: dict[str, Any] = {"authorization": "Bearer wrong-token"}
    with pytest.raises(HTTPException) as excinfo:
        await base_processor.authenticate({}, headers)
    assert excinfo.value.status_code == 401
    assert (
        isinstance(excinfo.value.detail, dict)
        and excinfo.value.detail["message"]
        == "Wiz webhook token verification failed, ignoring request"
    )


@pytest.mark.asyncio
async def test_authenticate_failure_no_auth(
    base_processor: WizWebhookProcessorImpl,
) -> None:
    headers: dict[str, Any] = {}
    with pytest.raises(HTTPException) as excinfo:
        await base_processor.authenticate({}, headers)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_failure_wrong_auth_type(
    base_processor: WizWebhookProcessorImpl,
) -> None:
    headers = {"authorization": "Basic some-token"}
    with pytest.raises(HTTPException) as excinfo:
        await base_processor.authenticate({}, headers)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_should_process_event(
    base_processor: WizWebhookProcessorImpl, event: WebhookEvent
) -> None:
    assert await base_processor.should_process_event(event) is True
