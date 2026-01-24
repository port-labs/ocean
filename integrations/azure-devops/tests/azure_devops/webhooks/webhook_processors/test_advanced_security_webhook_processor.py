import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.advanced_security_webhook_processor import (
    AdvancedSecurityWebhookProcessor,
)
from azure_devops.misc import Kind
from azure_devops.client.azure_devops_client import ADVANCED_SECURITY_PUBLISHER_ID
from integration import AzureDevopsAdvancedSecurityResourceConfig
from azure_devops.webhooks.events import AdvancedSecurityAlertEvents


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def advanced_security_processor(
    mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> AdvancedSecurityWebhookProcessor:
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.advanced_security_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return AdvancedSecurityWebhookProcessor(MagicMock(spec=WebhookEvent))


@pytest.mark.asyncio
async def test_advanced_security_get_matching_kinds(
    advanced_security_processor: AdvancedSecurityWebhookProcessor,
) -> None:
    event = MagicMock(spec=WebhookEvent)
    assert await advanced_security_processor.get_matching_kinds(event) == [
        Kind.ADVANCED_SECURITY_ALERT
    ]


@pytest.mark.asyncio
async def test_advanced_security_validate_payload(
    advanced_security_processor: AdvancedSecurityWebhookProcessor,
) -> None:
    valid_payload = {
        "eventType": AdvancedSecurityAlertEvents.SECURITY_ALERT_CREATED,
        "publisherId": ADVANCED_SECURITY_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "proj-123"}},
        "resource": {
            "repositoryUrl": "http://repo/url",
            "alertId": "alert-123",
            "state": "Active",
        },
    }
    assert await advanced_security_processor.validate_payload(valid_payload) is True

    invalid_publisher_payload = valid_payload.copy()
    invalid_publisher_payload["publisherId"] = "wrong-publisher"
    assert (
        await advanced_security_processor.validate_payload(invalid_publisher_payload)
        is False
    )

    missing_fields_payload = {
        "publisherId": ADVANCED_SECURITY_PUBLISHER_ID,
        "resource": {},
    }
    assert (
        await advanced_security_processor.validate_payload(missing_fields_payload)
        is False
    )


@pytest.mark.asyncio
async def test_advanced_security_should_process_event(
    advanced_security_processor: AdvancedSecurityWebhookProcessor,
) -> None:
    event = MagicMock(spec=WebhookEvent)
    event.payload = {"eventType": AdvancedSecurityAlertEvents.SECURITY_ALERT_CREATED}
    assert await advanced_security_processor.should_process_event(event) is True

    event.payload = {"eventType": "wrong.event"}
    assert await advanced_security_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_advanced_security_handle_event(
    advanced_security_processor: AdvancedSecurityWebhookProcessor,
    mock_client: MagicMock,
) -> None:
    # Setup
    payload = {
        "resourceContainers": {"project": {"id": "proj-123"}},
        "resource": {
            "repositoryUrl": "http://_git/repo-123",
            "alertId": "alert-123",
            "state": "Active",
        },
    }

    # Needs to match AzureDevopsAdvancedSecurityResourceConfig structure
    mock_selector = MagicMock()
    mock_selector.criteria = None

    mock_resource_config = MagicMock(spec=AzureDevopsAdvancedSecurityResourceConfig)
    mock_resource_config.selector = mock_selector

    # Mocks for client calls
    mock_client.get_single_project = AsyncMock(return_value={"id": "proj-123"})
    mock_client.get_repository = AsyncMock(return_value={"id": "repo-123"})
    mock_client.get_single_advanced_security_alert = AsyncMock(
        return_value={"id": "alert-123"}
    )
    mock_client._enrich_security_alert = MagicMock(
        return_value={"id": "alert-123", "enriched": True}
    )

    # Test execution
    result = await advanced_security_processor.handle_event(
        payload, mock_resource_config
    )

    # Assertions
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0] == {"id": "alert-123", "enriched": True}

    # Verify client calls
    mock_client.get_single_project.assert_called_with("proj-123")
    mock_client.get_repository.assert_called_with("repo-123")
    mock_client.get_single_advanced_security_alert.assert_called_with(
        "proj-123", "repo-123", "alert-123"
    )

    # Test filtering by state
    mock_selector.criteria = MagicMock()
    # Alert is "Active", so "Fixed" criteria should cause it to be skipped/deleted
    mock_selector.criteria.states = ["Fixed"]

    result_skipped = await advanced_security_processor.handle_event(
        payload, mock_resource_config
    )
    assert len(result_skipped.deleted_raw_results) == 1
    assert result_skipped.deleted_raw_results[0]["id"] == "alert-123"

    # Test not found project
    mock_client.get_single_project.return_value = None
    mock_selector.criteria = None  # Reset criteria
    result_no_proj = await advanced_security_processor.handle_event(
        payload, mock_resource_config
    )
    assert len(result_no_proj.updated_raw_results) == 0
    assert len(result_no_proj.deleted_raw_results) == 0
