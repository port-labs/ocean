import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.release_definition_webhook_processor import (
    ReleaseDefinitionWebhookProcessor,
)
from azure_devops.webhooks.events import ReleaseEvents
from azure_devops.client.azure_devops_client import RELEASE_PUBLISHER_ID


@pytest.fixture
def definition_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> ReleaseDefinitionWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock()
    mock_client.get_release_definition = AsyncMock()
    _mgr = MagicMock()

    _mgr.get_client_for_org.return_value = mock_client

    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor.AzureDevopsClientManager.create_from_ocean_config",
        lambda: _mgr,
    )
    return ReleaseDefinitionWebhookProcessor(event)


@pytest.mark.asyncio
async def test_get_matching_kinds(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await definition_processor.get_matching_kinds(event)
    assert kinds == ["release-definition"]


@pytest.mark.asyncio
async def test_should_process_event_valid(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseEvents.RELEASE_CREATED,
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await definition_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_publisher(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseEvents.RELEASE_CREATED,
            "publisherId": "wrong-publisher",
        },
        headers={},
    )
    assert await definition_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_validate_payload_valid(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "eventType": ReleaseEvents.RELEASE_CREATED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
            "project": {"id": "project-123"},
        },
        "resource": {
            "release": {"id": 42},
            "project": {"id": "project-123", "name": "TestProject"},
        },
    }
    assert await definition_processor.validate_payload(payload) is True


@pytest.mark.asyncio
async def test_validate_payload_missing_resource_project(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
            "project": {"id": "project-123"},
        },
        "resource": {"release": {"id": 42}},
    }
    assert await definition_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_validate_payload_missing_project(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
        },
        "resource": {"release": {"id": 42}},
    }
    assert await definition_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_validate_payload_missing_release(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
            "project": {"id": "project-123"},
        },
        "resource": {},
    }
    assert await definition_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_handle_event_success(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_project = {"id": "project-123", "name": "TestProject"}
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock(
        return_value={
            "id": 42,
            "name": "Release-1",
            "releaseDefinition": {"id": 5, "name": "MyPipeline"},
            "projectReference": {"id": "project-123", "name": None},
        }
    )
    mock_client.get_release_definition = AsyncMock(
        return_value={
            "id": 5,
            "name": "MyPipeline",
            "__project": mock_project,
        }
    )
    _mgr = MagicMock()

    _mgr.get_client_for_org.return_value = mock_client

    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor.AzureDevopsClientManager.create_from_ocean_config",
        lambda: _mgr,
    )

    payload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
            "project": {"id": "project-123"},
        },
        "resource": {
            "release": {"id": 42},
            "project": mock_project,
        },
    }

    result = await definition_processor.handle_event(payload, MagicMock())

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 5
    assert result.updated_raw_results[0]["__project"] == mock_project
    mock_client.get_release.assert_called_once_with("project-123", 42)
    mock_client.get_release_definition.assert_called_once_with(
        "project-123", 5, project=mock_project
    )


@pytest.mark.asyncio
async def test_handle_event_release_not_found(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock(return_value=None)
    _mgr = MagicMock()

    _mgr.get_client_for_org.return_value = mock_client

    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor.AzureDevopsClientManager.create_from_ocean_config",
        lambda: _mgr,
    )

    payload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
            "project": {"id": "project-123"},
        },
        "resource": {
            "release": {"id": 42},
            "project": {"id": "project-123", "name": "TestProject"},
        },
    }

    result = await definition_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_definition_not_found(
    definition_processor: ReleaseDefinitionWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release = AsyncMock(
        return_value={
            "id": 42,
            "name": "Release-1",
            "releaseDefinition": {"id": 5, "name": "MyPipeline"},
            "projectReference": {"id": "project-123", "name": "TestProject"},
        }
    )
    mock_client.get_release_definition = AsyncMock(return_value=None)
    _mgr = MagicMock()

    _mgr.get_client_for_org.return_value = mock_client

    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor.AzureDevopsClientManager.create_from_ocean_config",
        lambda: _mgr,
    )

    payload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/test/"},
            "project": {"id": "project-123"},
        },
        "resource": {
            "release": {"id": 42},
            "project": {"id": "project-123", "name": "TestProject"},
        },
    }

    result = await definition_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
