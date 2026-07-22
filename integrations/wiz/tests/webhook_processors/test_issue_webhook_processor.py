from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from integration import ObjectKind
from typing import Any

# Mocking ocean and init_client before importing the processor to handle class-level side effects
with (
    patch("port_ocean.context.ocean.ocean") as mock_ocean,
    patch("initialize_client.init_client") as mock_init_client,
):
    mock_ocean.integration_config = {"wiz_webhook_verification_token": "test-token"}
    mock_init_client.return_value = MagicMock()
    from wiz.webhook_processors.issue_webhook_processor import IssueWebhookProcessor


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def issue_processor(event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event)


@pytest.fixture
def mock_issue_resource_config() -> MagicMock:
    mock_config = MagicMock()
    mock_config.selector.max_pages = 1
    mock_config.selector.status_list = ["OPEN"]
    mock_config.selector.severity_list = ["HIGH"]
    mock_config.selector.type_list = ["TOXIC_COMBINATION"]
    return mock_config


@pytest.mark.asyncio
async def test_get_matching_kinds(issue_processor: IssueWebhookProcessor) -> None:
    assert await issue_processor.get_matching_kinds(MagicMock()) == [ObjectKind.ISSUE]


@pytest.mark.asyncio
async def test_validate_payload_success(issue_processor: IssueWebhookProcessor) -> None:
    payload = {"issue": {"id": "test-id"}}
    assert await issue_processor.validate_payload(payload) is True


@pytest.mark.asyncio
async def test_validate_payload_failure(issue_processor: IssueWebhookProcessor) -> None:
    invalid_payloads: list[dict[str, Any]] = [
        {},
        {"issue": {}},
        {"some_other_field": "some_value"},
    ]
    for payload in invalid_payloads:
        assert await issue_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_handle_event_success(
    issue_processor: IssueWebhookProcessor, mock_issue_resource_config: MagicMock
) -> None:
    payload = {"issue": {"id": "test-id"}}
    issue_details = {"id": "test-id", "name": "test-issue"}

    with patch.object(
        issue_processor._client, "get_single_issue", new_callable=AsyncMock
    ) as mock_get_single_issue:
        mock_get_single_issue.return_value = issue_details

        results = await issue_processor.handle_event(
            payload, mock_issue_resource_config
        )

        assert results.updated_raw_results == [issue_details]
        assert results.deleted_raw_results == []
        mock_get_single_issue.assert_called_once()


@pytest.mark.asyncio
async def test_handle_event_no_issue_details(
    issue_processor: IssueWebhookProcessor, mock_issue_resource_config: MagicMock
) -> None:
    payload = {"issue": {"id": "test-id"}}

    with patch.object(
        issue_processor._client, "get_single_issue", new_callable=AsyncMock
    ) as mock_get_single_issue:
        mock_get_single_issue.return_value = None

        results = await issue_processor.handle_event(
            payload, mock_issue_resource_config
        )

        assert results.updated_raw_results == []
        assert results.deleted_raw_results == []
        mock_get_single_issue.assert_called_once()
