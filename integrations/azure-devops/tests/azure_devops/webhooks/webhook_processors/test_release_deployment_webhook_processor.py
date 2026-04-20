import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor import (
    ReleaseDeploymentWebhookProcessor,
)
from azure_devops.webhooks.events import ReleaseDeploymentEvents
from azure_devops.client.azure_devops_client import RELEASE_PUBLISHER_ID


@pytest.fixture
def deployment_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> ReleaseDeploymentWebhookProcessor:
    mock_client = MagicMock()
    mock_client.get_release_deployment = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return ReleaseDeploymentWebhookProcessor(event)


@pytest.mark.asyncio
async def test_deployment_get_matching_kinds(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await deployment_processor.get_matching_kinds(event)
    assert kinds == ["release-deployment"]


@pytest.mark.asyncio
async def test_deployment_should_process_event_completed(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await deployment_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_deployment_should_process_event_started(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseDeploymentEvents.DEPLOYMENT_STARTED,
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await deployment_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_deployment_should_process_event_invalid_publisher(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
            "publisherId": "wrong-publisher",
        },
        headers={},
    )
    assert await deployment_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_deployment_should_process_event_invalid_type(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "invalid.event",
            "publisherId": RELEASE_PUBLISHER_ID,
        },
        headers={},
    )
    assert await deployment_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_deployment_validate_payload_completed(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "deployment": {
                "release": {"id": 10},
                "definitionEnvironmentId": 3,
            }
        },
    }
    assert await deployment_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_deployment_validate_payload_started(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_STARTED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "environment": {
                "releaseId": 10,
                "definitionEnvironmentId": 5,
            }
        },
    }
    assert await deployment_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_deployment_validate_payload_missing_project(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {},
        "resource": {
            "deployment": {
                "release": {"id": 10},
                "releaseEnvironment": {"id": 5},
            }
        },
    }
    assert await deployment_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_deployment_validate_payload_missing_deployment_and_environment(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {},
    }
    assert await deployment_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_deployment_validate_payload_completed_missing_release_id(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "deployment": {
                "definitionEnvironmentId": 3,
            }
        },
    }
    assert await deployment_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_deployment_validate_payload_completed_missing_definition_environment_id(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "deployment": {
                "release": {"id": 10},
            }
        },
    }
    assert await deployment_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_deployment_validate_payload_started_missing_release_id(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_STARTED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "environment": {
                "definitionEnvironmentId": 5,
            }
        },
    }
    assert await deployment_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_deployment_validate_payload_started_missing_definition_environment_id(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {
        "eventType": ReleaseDeploymentEvents.DEPLOYMENT_STARTED,
        "publisherId": RELEASE_PUBLISHER_ID,
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "environment": {
                "releaseId": 10,
            }
        },
    }
    assert await deployment_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_deployment_handle_event_completed_success(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release_deployment = AsyncMock(
        return_value={"id": 99, "deploymentStatus": "succeeded"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "deployment": {
                "release": {"id": 10},
                "releaseEnvironment": {"id": 5},
                "definitionEnvironmentId": 3,
            }
        },
    }

    result = await deployment_processor.handle_event(payload, MagicMock())

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 99
    assert len(result.deleted_raw_results) == 0
    mock_client.get_release_deployment.assert_called_once_with("project-123", 10, 3)


@pytest.mark.asyncio
async def test_deployment_handle_event_started_success(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release_deployment = AsyncMock(
        return_value={"id": 99, "deploymentStatus": "inProgress"}
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "environment": {
                "releaseId": 10,
                "definitionEnvironmentId": 5,
            }
        },
    }

    result = await deployment_processor.handle_event(payload, MagicMock())

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 99
    assert len(result.deleted_raw_results) == 0
    mock_client.get_release_deployment.assert_called_once_with("project-123", 10, 5)


@pytest.mark.asyncio
async def test_deployment_handle_event_not_found(
    deployment_processor: ReleaseDeploymentWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_release_deployment = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "resourceContainers": {"project": {"id": "project-123"}},
        "resource": {
            "deployment": {
                "release": {"id": 10},
                "releaseEnvironment": {"id": 5},
                "definitionEnvironmentId": 3,
            }
        },
    }

    result = await deployment_processor.handle_event(payload, MagicMock())

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
