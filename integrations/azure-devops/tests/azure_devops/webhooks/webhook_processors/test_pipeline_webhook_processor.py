import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
)
from azure_devops.webhooks.events import PipelineEvents, PushEvents
from azure_devops.misc import Kind


@pytest.fixture
def pipeline_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PipelineWebhookProcessor:
    mock_client = MagicMock()
    mock_client.send_request = AsyncMock()
    mock_client.get_commit_changes = AsyncMock()
    mock_client.enrich_pipelines_with_repository = AsyncMock()
    mock_client._organization_base_url = "https://dev.azure.com/test"
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PipelineWebhookProcessor(event)


@pytest.mark.asyncio
async def test_pipeline_get_matching_kinds(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await pipeline_processor.get_matching_kinds(event) == [Kind.PIPELINE]


@pytest.mark.asyncio
async def test_pipeline_validate_payload_build_completed(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {
            "id": 123,
            "definition": {"id": 456, "name": "Test Pipeline"},
            "project": {"id": "project-123"},
        },
    }
    assert await pipeline_processor.validate_payload(valid_payload) is True

    invalid_payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {"id": 123},
    }
    assert await pipeline_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_validate_payload_push(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": PushEvents.PUSH,
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "repo-123",
                "name": "test-repo",
                "project": {"id": "project-123"},
            },
            "refUpdates": [{"name": "refs/heads/main"}],
        },
    }
    assert await pipeline_processor.validate_payload(valid_payload) is True

    invalid_payload = {
        "eventType": PushEvents.PUSH,
        "publisherId": "tfs",
        "resource": {"repository": {"id": "repo-123"}},
    }
    assert await pipeline_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_validate_payload_invalid_event(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    invalid_payload = {"eventType": "wrong.event", "publisherId": "tfs", "resource": {}}
    assert await pipeline_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_pipeline_should_process_event_build_completed(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PipelineEvents.BUILD_COMPLETED,
            "publisherId": "tfs",
            "resource": {"id": 123, "definition": {"id": 456}},
        },
        headers={},
    )
    assert await pipeline_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_pipeline_should_process_event_push_with_yaml_changes(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_commit_changes = AsyncMock(
        return_value={
            "changes": [
                {"item": {"path": "azure-pipelines.yml"}},
            ]
        }
    )
    mock_client._organization_base_url = "https://dev.azure.com/test"
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PushEvents.PUSH,
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "repo-123",
                    "name": "test-repo",
                    "project": {"id": "project-123"},
                },
                "refUpdates": [{"newObjectId": "commit-123"}],
            },
        },
        headers={},
    )
    processor = PipelineWebhookProcessor(event)
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_pipeline_should_process_event_push_without_yaml_changes(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_commit_changes = AsyncMock(
        return_value={"changes": [{"item": {"path": "README.md"}}]}
    )
    mock_client._organization_base_url = "https://dev.azure.com/test"
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": PushEvents.PUSH,
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "repo-123",
                    "name": "test-repo",
                    "project": {"id": "project-123"},
                },
                "refUpdates": [{"newObjectId": "commit-123"}],
            },
        },
        headers={},
    )
    processor = PipelineWebhookProcessor(event)
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pipeline_handle_event_build_completed(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 456,
        "name": "Test Pipeline",
        "url": "https://dev.azure.com/test/pipeline/456",
    }
    mock_client.send_request = AsyncMock(return_value=mock_response)
    mock_client._organization_base_url = "https://dev.azure.com/test"
    mock_client.enrich_pipelines_with_repository = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {
            "id": 123,
            "definition": {"id": 456, "name": "Test Pipeline"},
            "project": {"id": "project-123"},
        },
    }
    resource_config = MagicMock()

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )
    result = await processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 456
    assert result.updated_raw_results[0]["__projectId"] == "project-123"
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_pipeline_handle_event_build_completed_with_repo_enrichment(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that repository enrichment is called when include_repo is True."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 456,
        "name": "Test Pipeline",
        "url": "https://dev.azure.com/test/pipeline/456",
    }
    mock_client.send_request = AsyncMock(return_value=mock_response)
    mock_client._organization_base_url = "https://dev.azure.com/test"
    enriched_pipeline = {
        "id": 456,
        "name": "Test Pipeline",
        "__projectId": "project-123",
        "__repository": {"id": "repo-123", "name": "test-repo"},
    }
    mock_client.enrich_pipelines_with_repository = AsyncMock(
        return_value=[enriched_pipeline]
    )
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {
            "id": 123,
            "definition": {"id": 456, "name": "Test Pipeline"},
            "project": {"id": "project-123"},
        },
    }
    resource_config = MagicMock()
    resource_config.selector = MagicMock()
    resource_config.selector.include_repo = True
    import builtins

    original_isinstance = builtins.isinstance

    def mock_isinstance(obj: object, cls: type | tuple[type, ...]) -> bool:
        if (
            hasattr(cls, "__name__")
            and cls.__name__ == "AzureDevopsPipelineResourceConfig"
        ):
            if hasattr(obj, "selector") and hasattr(obj.selector, "include_repo"):
                return True
        return original_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", mock_isinstance)

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )
    result = await processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert "__repository" in result.updated_raw_results[0]
    assert result.updated_raw_results[0]["__repository"] == {
        "id": "repo-123",
        "name": "test-repo",
    }
    mock_client.enrich_pipelines_with_repository.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_handle_event_build_completed_classic_build(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_response_pipelines = None
    mock_response_build_def = MagicMock()
    mock_response_build_def.json.return_value = {
        "id": 456,
        "name": "Classic Build Pipeline",
    }
    mock_client.send_request = AsyncMock(
        side_effect=[mock_response_pipelines, mock_response_build_def]
    )
    mock_client._organization_base_url = "https://dev.azure.com/test"
    mock_client.enrich_pipelines_with_repository = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {
            "id": 123,
            "definition": {"id": 456, "name": "Classic Build Pipeline"},
            "project": {"id": "project-123"},
        },
    }
    resource_config = MagicMock()

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )
    result = await processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == "456"
    assert result.updated_raw_results[0]["__projectId"] == "project-123"
    assert mock_client.send_request.call_count == 2


@pytest.mark.asyncio
async def test_pipeline_handle_event_build_completed_missing_fields(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
) -> None:
    payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {"id": 123},
    }
    resource_config = MagicMock()

    with pytest.raises(KeyError):
        await pipeline_processor.handle_event(payload, resource_config)


@pytest.mark.asyncio
async def test_pipeline_handle_event_build_completed_not_found(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.send_request = AsyncMock(return_value=None)
    mock_client._organization_base_url = "https://dev.azure.com/test"
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {
            "id": 123,
            "definition": {"id": 456, "name": "Test Pipeline"},
            "project": {"id": "project-123"},
        },
    }
    resource_config = MagicMock()

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )
    result = await processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_pipeline_handle_event_push_yaml_change(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_commit_changes = AsyncMock(
        return_value={
            "changes": [
                {"item": {"path": "azure-pipelines.yml"}},
            ]
        }
    )
    mock_pipelines_response = MagicMock()
    mock_pipelines_response.json.return_value = {
        "value": [
            {
                "id": 789,
                "name": "YAML Pipeline",
                "repository": {"id": "repo-123"},
            }
        ]
    }
    mock_client.send_request = AsyncMock(return_value=mock_pipelines_response)
    mock_client._organization_base_url = "https://dev.azure.com/test"
    mock_client.enrich_pipelines_with_repository = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PushEvents.PUSH,
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "repo-123",
                "name": "test-repo",
                "project": {"id": "project-123"},
            },
            "refUpdates": [{"newObjectId": "commit-123"}],
        },
    }
    resource_config = MagicMock()

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )
    result = await processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == 789
    assert result.updated_raw_results[0]["__projectId"] == "project-123"


@pytest.mark.asyncio
async def test_pipeline_handle_event_push_no_pipelines(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_commit_changes = AsyncMock(
        return_value={
            "changes": [
                {"item": {"path": "azure-pipelines.yml"}},
            ]
        }
    )
    mock_pipelines_response = MagicMock()
    mock_pipelines_response.json.return_value = {"value": []}
    mock_client.send_request = AsyncMock(return_value=mock_pipelines_response)
    mock_client._organization_base_url = "https://dev.azure.com/test"
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PushEvents.PUSH,
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "repo-123",
                "name": "test-repo",
                "project": {"id": "project-123"},
            },
            "refUpdates": [{"newObjectId": "commit-123"}],
        },
    }
    resource_config = MagicMock()

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )
    result = await processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_pipeline_handle_event_exception(
    pipeline_processor: PipelineWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.send_request = AsyncMock(side_effect=Exception("API Error"))
    mock_client._organization_base_url = "https://dev.azure.com/test"
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pipeline_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )

    payload = {
        "eventType": PipelineEvents.BUILD_COMPLETED,
        "publisherId": "tfs",
        "resource": {
            "id": 123,
            "definition": {"id": 456, "name": "Test Pipeline"},
            "project": {"id": "project-123"},
        },
    }
    resource_config = MagicMock()

    processor = PipelineWebhookProcessor(
        WebhookEvent(trace_id="test", payload=payload, headers={})
    )

    # Exception should propagate since there's no exception handling in handle_event
    with pytest.raises(Exception, match="API Error"):
        await processor.handle_event(payload, resource_config)
