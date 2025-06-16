from typing import Any, Dict
import pytest
from unittest.mock import AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
)
from github.webhook.webhook_processors.base_deployment_webhook_processor import (
    BaseDeploymentWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class MockBaseDeploymentProcessor(BaseDeploymentWebhookProcessor):

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test_kind"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


@pytest.fixture
def base_deployment_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> MockBaseDeploymentProcessor:
    return MockBaseDeploymentProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestBaseDeploymentWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,result",
        [
            ("deployment", True),
            ("deployment_status", True),
            ("push", False),
            ("pull_request", False),
        ],
    )
    async def test_should_process_event(
        self,
        base_deployment_webhook_processor: MockBaseDeploymentProcessor,
        github_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert (
            await base_deployment_webhook_processor._should_process_event(event)
            is result
        )

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "deployment": {
                        "id": 123,
                        "environment": "production",
                    }
                },
                True,
            ),
            (
                {
                    "deployment": {
                        "id": None,
                        "environment": None,
                    }
                },
                False,
            ),
            (
                {
                    "deployment": {
                        "id": 123,
                        "environment": None,
                    }
                },
                False,
            ),
            (
                {
                    "deployment": {
                        "id": None,
                        "environment": "production",
                    }
                },
                False,
            ),
            ({"deployment": {}}, False),  # missing required fields
            ({}, False),  # missing deployment
        ],
    )
    async def test_validate_payload(
        self,
        base_deployment_webhook_processor: MockBaseDeploymentProcessor,
        payload: Dict[str, Any],
        expected: bool,
    ) -> None:
        result = await base_deployment_webhook_processor._validate_payload(payload)
        assert result is expected
