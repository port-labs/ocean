from typing import Any, Dict, Generator
import pytest
from unittest.mock import AsyncMock, patch

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from webhook_processors.issue_processor import IssueWebhookProcessor
from kinds import ObjectKind


@pytest.fixture
def issue_processor(mock_webhook_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def valid_issue_payload() -> Dict[str, Any]:
    return {
        "type": "Issue",
        "data": {
            "identifier": "ABC-123",
            "title": "Test Issue",
            "description": "Test Description",
        },
    }


@pytest.fixture
def invalid_issue_payload() -> Dict[str, Any]:
    return {
        "type": "Issue",
        "data": {
            "title": "Test Issue",  # Missing identifier
            "description": "Test Description",
        },
    }


@pytest.fixture
def non_issue_payload() -> Dict[str, Any]:
    return {"type": "IssueLabel", "data": {"id": "label-123", "name": "Test Label"}}


@pytest.fixture
def mock_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.ISSUE,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".identifier",
                    title=".title",
                    blueprint='"linearIssue"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch("webhook_processors.issue_processor.LinearClient") as mock:
        client = AsyncMock()
        mock.from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestIssueWebhookProcessor:

    @pytest.mark.asyncio
    async def test_should_process_event_valid_payload(
        self,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=valid_issue_payload, headers={})
        should_process = await issue_processor.should_process_event(event)
        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_process_event_invalid_payload(
        self,
        issue_processor: IssueWebhookProcessor,
        invalid_issue_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=invalid_issue_payload, headers={})
        should_process = await issue_processor.should_process_event(event)
        assert should_process is False

    @pytest.mark.asyncio
    async def test_should_process_event_non_issue_payload(
        self, issue_processor: IssueWebhookProcessor, non_issue_payload: dict[str, Any]
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=non_issue_payload, headers={})
        should_process = await issue_processor.should_process_event(event)
        assert should_process is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=valid_issue_payload, headers={})
        kinds = await issue_processor.get_matching_kinds(event)
        assert kinds == ["issue"]

    @pytest.mark.asyncio
    @patch("linear.client.LinearClient.from_ocean_configuration")
    async def test_handle_event_success(
        self,
        mock_client: AsyncMock,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: dict[str, Any],
        mock_resource_config: ResourceConfig,
    ) -> None:
        # Mock response data
        mock_issue_data = {
            "id": "issue-123",
            "identifier": "ABC-123",
            "title": "Test Issue",
            "description": "Test Description",
        }
        mock_client.get_single_issue.return_value = mock_issue_data

        # Process the event
        result = await issue_processor.handle_event(
            valid_issue_payload, mock_resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_issue_data
        assert len(result.deleted_raw_results) == 0

        mock_client.get_single_issue.assert_called_once_with("ABC-123")
