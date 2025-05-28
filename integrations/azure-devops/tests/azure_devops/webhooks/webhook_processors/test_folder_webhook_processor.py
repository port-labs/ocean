import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)
from azure_devops.misc import Kind, AzureDevopsFolderResourceConfig


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_client = MagicMock()
    mock_client.get_commit_changes = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.folder_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return mock_client


@pytest.fixture
def folder_processor(
    event: WebhookEvent, mock_client: MagicMock
) -> FolderWebhookProcessor:
    return FolderWebhookProcessor(event)


@pytest.fixture
def mock_resource_config() -> MagicMock:
    config = MagicMock(spec=AzureDevopsFolderResourceConfig)

    selector = MagicMock()

    test_repo_mapping = MagicMock()
    test_repo_mapping.name = "test-repo"

    folder_patterns = [
        MagicMock(
            path="/test/*",
            repos=[test_repo_mapping],
        ),
        MagicMock(
            path="/other/*",
            repos=[MagicMock(name="other-repo")],
        ),
    ]

    selector.folders = folder_patterns
    config.selector = selector

    return config


@pytest.mark.asyncio
async def test_folder_should_process_event(
    folder_processor: FolderWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {"url": "http://example.com"},
        },
        headers={},
    )
    assert await folder_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await folder_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_folder_get_matching_kinds(
    folder_processor: FolderWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await folder_processor.get_matching_kinds(event)
    assert Kind.FOLDER in kinds


@pytest.mark.asyncio
async def test_folder_pattern_matching(
    folder_processor: FolderWebhookProcessor,
) -> None:
    patterns = ["/test/*", "/other/*"]
    assert folder_processor._matches_folder_pattern("/test/folder", patterns) is True
    assert folder_processor._matches_folder_pattern("/other/folder", patterns) is True
    assert folder_processor._matches_folder_pattern("/wrong/folder", patterns) is False
    assert (
        folder_processor._matches_folder_pattern("/test/folder/subfolder", patterns)
        is False
    )


@pytest.mark.asyncio
async def test_folder_handle_event_with_unconfigured_repo(
    folder_processor: FolderWebhookProcessor,
    mock_event_context: None,
    mock_resource_config: MagicMock,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "repo-123",
                    "name": "unconfigured-repo",
                    "project": {"id": "proj-123", "name": "test-project"},
                },
                "refUpdates": [
                    {
                        "name": "refs/heads/main",
                        "newObjectId": "new-commit",
                    }
                ],
            },
        },
        headers={},
    )

    result = await folder_processor.handle_event(event.payload, mock_resource_config)
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_folder_handle_event(
    folder_processor: FolderWebhookProcessor,
    mock_event_context: None,
    mock_resource_config: MagicMock,
    mock_client: MagicMock,
) -> None:
    mock_client.get_commit_changes.return_value = {
        "changes": [
            {
                "item": {
                    "path": "/test/folder",
                    "url": "http://example.com/folder",
                    "isFolder": True,
                    "objectId": "123",
                },
                "changeType": "add",
            }
        ]
    }

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "repo-123",
                    "name": "test-repo",
                    "project": {"id": "proj-123", "name": "test-project"},
                },
                "refUpdates": [
                    {
                        "name": "refs/heads/main",
                        "newObjectId": "new-commit",
                    }
                ],
            },
        },
        headers={},
    )

    result = await folder_processor.handle_event(event.payload, mock_resource_config)

    assert len(result.updated_raw_results) == 1
    folder_entity = result.updated_raw_results[0]
    assert folder_entity["kind"] == Kind.FOLDER
    assert folder_entity["__repository"]["name"] == "test-repo"
    assert folder_entity["__branch"] == "main"
    assert folder_entity["__pattern"] == "/test/folder"
    assert folder_entity["objectId"] == "123"
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_folder_handle_event_with_deleted_folder(
    folder_processor: FolderWebhookProcessor,
    mock_event_context: None,
    mock_resource_config: MagicMock,
    mock_client: MagicMock,
) -> None:
    mock_client.get_commit_changes.return_value = {
        "changes": [
            {
                "item": {
                    "path": "/test/folder",
                    "url": "http://example.com/folder",
                    "isFolder": True,
                    "objectId": "123",
                },
                "changeType": "delete",
            }
        ]
    }

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "repo-123",
                    "name": "test-repo",
                    "project": {"id": "proj-123", "name": "test-project"},
                },
                "refUpdates": [
                    {
                        "name": "refs/heads/main",
                        "newObjectId": "new-commit",
                    }
                ],
            },
        },
        headers={},
    )

    result = await folder_processor.handle_event(event.payload, mock_resource_config)

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    folder_entity = result.deleted_raw_results[0]
    assert folder_entity["kind"] == Kind.FOLDER
    assert folder_entity["__repository"]["name"] == "test-repo"
    assert folder_entity["__branch"] == "main"
    assert folder_entity["__pattern"] == "/test/folder"
    assert folder_entity["objectId"] == "123"


@pytest.mark.asyncio
async def test_folder_handle_event_with_non_matching_pattern(
    folder_processor: FolderWebhookProcessor,
    mock_event_context: None,
    mock_resource_config: MagicMock,
    mock_client: MagicMock,
) -> None:
    mock_client.get_commit_changes.return_value = {
        "changes": [
            {
                "item": {
                    "path": "/wrong/folder",
                    "url": "http://example.com/folder",
                    "isFolder": True,
                    "objectId": "123",
                },
                "changeType": "add",
            }
        ]
    }

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "repo-123",
                    "name": "test-repo",
                    "project": {"id": "proj-123", "name": "test-project"},
                },
                "refUpdates": [
                    {
                        "name": "refs/heads/main",
                        "newObjectId": "new-commit",
                    }
                ],
            },
        },
        headers={},
    )

    result = await folder_processor.handle_event(event.payload, mock_resource_config)

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
