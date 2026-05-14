import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.test_run_webhook_processor import (
    TestRunWebhookProcessor,
)
from azure_devops.webhooks.events import BuildEvents


@pytest.fixture
def test_run_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> TestRunWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_test_runs_by_build = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.test_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return TestRunWebhookProcessor(event)


@pytest.mark.asyncio
async def test_get_matching_kinds(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await test_run_processor.get_matching_kinds(event)
    assert kinds == ["test-run"]


@pytest.mark.asyncio
async def test_should_process_event_valid(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": BuildEvents.BUILD_COMPLETE,
            "publisherId": "tfs",
        },
        headers={},
    )
    assert await test_run_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_invalid_type(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "workitem.created",
            "publisherId": "tfs",
        },
        headers={},
    )
    assert await test_run_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_validate_payload_valid(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "eventType": BuildEvents.BUILD_COMPLETE,
        "publisherId": "tfs",
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"id": 456},
    }
    assert await test_run_processor.validate_payload(payload) is True


@pytest.mark.asyncio
async def test_validate_payload_missing_project(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "resourceContainers": {},
        "resource": {"id": 456},
    }
    assert await test_run_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_validate_payload_missing_build_id(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {},
    }
    assert await test_run_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_handle_event_success(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_test_runs = [
        {"id": 10, "name": "Test Run 1", "state": "Completed"},
        {"id": 11, "name": "Test Run 2", "state": "Completed"},
    ]
    mock_client = MagicMock()
    mock_client.get_test_runs_by_build = AsyncMock(return_value=mock_test_runs)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.test_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"id": 456},
    }
    resource_config = MagicMock()
    resource_config.kind = "test-run"
    resource_config.selector.code_coverage = None

    result = await test_run_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 2
    assert result.updated_raw_results[0]["id"] == 10
    assert result.updated_raw_results[1]["id"] == 11
    mock_client.get_test_runs_by_build.assert_called_once_with(
        "project-123", "456", None
    )


@pytest.mark.asyncio
async def test_handle_event_no_test_runs(
    test_run_processor: TestRunWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_test_runs_by_build = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.test_run_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {"id": 456},
    }
    resource_config = MagicMock()
    resource_config.kind = "test-run"
    resource_config.selector.code_coverage = None

    result = await test_run_processor.handle_event(payload, resource_config)

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
