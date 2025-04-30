from typing import Any, Dict, Generator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from linear.utils import ObjectKind


@pytest.fixture
def issue_processor(mock_webhook_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def valid_issue_payload() -> Dict[str, Any]:
    return {
        "action": "create",
        "type": "Issue",
        "data": {
            "identifier": "ABC-123",
            "title": "Test Issue",
            "description": "Test Description",
            "team": {"name": "Test Org"},
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
    return {
        "action": "create",
        "type": "IssueLabel",
        "data": {"id": "label-123", "name": "Test Label"},
    }


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
    with patch("webhook_processors.issue_webhook_processor.LinearClient") as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestIssueWebhookProcessor:

    async def test_should_process_event_valid_event(
        self,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(
            trace_id="test",
            payload=valid_issue_payload,
            headers={"linear-event": "Issue"},
        )
        event._original_request = MagicMock()
        should_process = await issue_processor.should_process_event(event)
        assert should_process is True

    async def test_should_process_event_invalid_event(
        self,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=valid_issue_payload, headers={})
        should_process = await issue_processor.should_process_event(event)
        assert should_process is False

    async def test_should_process_event_non_issue_payload(
        self, issue_processor: IssueWebhookProcessor, non_issue_payload: dict[str, Any]
    ) -> None:

        should_process = await issue_processor.validate_payload(non_issue_payload)
        assert should_process is False

    async def test_get_matching_kinds(
        self,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=valid_issue_payload, headers={})
        kinds = await issue_processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.ISSUE]

    @pytest.mark.parametrize(
        "action, expected_results",
        [
            ("create", {"updated_count": 1, "deleted_count": 0, "client_called": True}),
            (
                "remove",
                {"updated_count": 0, "deleted_count": 1, "client_called": False},
            ),
        ],
        ids=["add_action", "remove_action"],
    )
    async def test_handle_event_success(
        self,
        mock_client: AsyncMock,
        issue_processor: IssueWebhookProcessor,
        valid_issue_payload: Dict[str, Any],
        mock_resource_config: ResourceConfig,
        action: str,
        expected_results: Dict[str, Any],
    ) -> None:
        # Mock response data
        mock_issue_data = {
            "id": "issue-123",
            "identifier": "ABC-123",
            "title": "Test Issue",
            "description": "Test Description",
        }
        mock_client.get_single_issue.return_value = mock_issue_data

        # Modify payload
        valid_issue_payload["action"] = action

        # Process the event
        result = await issue_processor.handle_event(
            valid_issue_payload, mock_resource_config
        )

        # Assert results
        assert len(result.updated_raw_results) == expected_results["updated_count"]
        assert len(result.deleted_raw_results) == expected_results["deleted_count"]

        if expected_results["client_called"]:
            mock_client.get_single_issue.assert_called_once_with("ABC-123")
            assert result.updated_raw_results[0] == mock_issue_data
        else:
            mock_client.get_single_issue.assert_not_called()
