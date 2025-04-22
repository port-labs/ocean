import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import RepositoryEvents
from port_ocean.ocean import Ocean
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


@pytest.fixture
def mock_azure_devops_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_client = MagicMock()
    mock_client.send_request = AsyncMock()
    mock_client.get_repository = AsyncMock()
    mock_client.get_file_by_commit = AsyncMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.file_webhook_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return mock_client


@pytest.fixture
def mock_ocean() -> Ocean:
    mock = MagicMock()
    mock.update_diff = AsyncMock()
    return mock


@pytest.fixture
def mock_event_context(monkeypatch: pytest.MonkeyPatch, mock_ocean: Ocean) -> None:
    monkeypatch.setattr("port_ocean.context.ocean", mock_ocean)
    monkeypatch.setattr("port_ocean.context.event", MagicMock())


@pytest.fixture
def mock_port_app_config() -> MagicMock:
    mock_config = MagicMock(spec=PortAppConfig)
    mock_config.spec_path = "test_path"
    mock_config.branch = "main"
    mock_config.use_default_branch = False
    return mock_config


@pytest.fixture
def file_processor(
    mock_azure_devops_client: MagicMock,
    mock_event_context: MagicMock,
    mock_port_app_config: MagicMock,
) -> FileWebhookProcessor:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={},
        headers={},
    )
    setattr(event, "port_app_config", mock_port_app_config)
    return FileWebhookProcessor(event)


@pytest.fixture
def base_file_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {"url": "http://example.com"},
        },
        headers={},
    )


@pytest.mark.asyncio
async def test_file_get_matching_kinds(file_processor: FileWebhookProcessor) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await file_processor.get_matching_kinds(event)
    assert kinds == [Kind.FILE]


@pytest.mark.asyncio
async def test_file_should_process_valid_event_type(
    file_processor: FileWebhookProcessor, base_file_event: WebhookEvent
) -> None:
    for event_type in RepositoryEvents:
        base_file_event.payload["eventType"] = event_type.value
        assert await file_processor.should_process_event(base_file_event) is True


@pytest.mark.asyncio
async def test_file_should_not_process_invalid_event_type(
    file_processor: FileWebhookProcessor, base_file_event: WebhookEvent
) -> None:
    base_file_event.payload["eventType"] = "unknown.event"
    assert await file_processor.should_process_event(base_file_event) is False


@pytest.mark.asyncio
async def test_file_process_push_updates_skips_non_default_branch(
    file_processor: FileWebhookProcessor,
    mock_azure_devops_client: MagicMock,
    mock_port_app_config: MagicMock,
) -> None:
    mock_port_app_config.use_default_branch = True
    push_data = {"resource": {"repository": {"defaultBranch": "refs/heads/main"}}}
    updates = [
        {
            "name": "refs/heads/feature",
            "oldObjectId": "old",
            "newObjectId": "new",
            "repositoryId": "repo1",
        }
    ]

    result = await file_processor._process_push_updates(
        mock_port_app_config, push_data, updates
    )
    assert result == []


@pytest.mark.asyncio
async def test_file_process_push_updates_processes_default_branch(
    file_processor: FileWebhookProcessor,
    mock_azure_devops_client: MagicMock,
    mock_port_app_config: MagicMock,
) -> None:
    mock_port_app_config.use_default_branch = True
    push_data = {"resource": {"repository": {"defaultBranch": "refs/heads/main"}}}
    updates = [
        {
            "name": "refs/heads/main",
            "oldObjectId": "old",
            "newObjectId": "new",
            "repositoryId": "repo1",
        }
    ]

    with patch.object(
        file_processor, "_handle_gitops_diff_for_ref", new_callable=AsyncMock
    ) as mock_handle:
        mock_handle.return_value = [{"kind": "test", "id": "processed"}]
        result = await file_processor._process_push_updates(
            mock_port_app_config, push_data, updates
        )
        assert result == [{"kind": "test", "id": "processed"}]
        mock_handle.assert_called_once_with(mock_port_app_config, push_data, updates[0])


@pytest.mark.asyncio
async def test_file_sync_changed_files_no_repository(
    file_processor: FileWebhookProcessor,
    mock_azure_devops_client: MagicMock,
) -> None:
    mock_azure_devops_client.get_repository.return_value = None
    result = await file_processor._sync_changed_files("repo1", "commit1")
    assert result == []
    mock_azure_devops_client.get_repository.assert_called_once_with("repo1")


@pytest.mark.asyncio
async def test_file_sync_changed_files_with_changes(
    file_processor: FileWebhookProcessor,
    mock_azure_devops_client: MagicMock,
) -> None:
    mock_azure_devops_client.get_repository.return_value = {
        "project": {"id": "proj1"},
        "id": "repo1",
    }
    mock_azure_devops_client.send_request.return_value = MagicMock(
        json=MagicMock(return_value={"changes": [{"item": {"path": "file1.txt"}}]})
    )
    mock_azure_devops_client.get_file_by_commit.return_value = b"file1 content"

    with patch.object(
        file_processor, "_build_file_entity_from_commit", new_callable=AsyncMock
    ) as mock_build:
        mock_build.return_value = {"kind": Kind.FILE, "file": {"path": "file1.txt"}}
        result = await file_processor._sync_changed_files("repo1", "commit1")
        assert result == [{"kind": Kind.FILE, "file": {"path": "file1.txt"}}]
        mock_build.assert_called_once_with(
            {"project": {"id": "proj1"}, "id": "repo1"},
            "commit1",
            {"item": {"path": "file1.txt"}},
        )


@pytest.mark.asyncio
async def test_file_build_file_entity_from_commit_success(
    file_processor: FileWebhookProcessor,
    mock_azure_devops_client: MagicMock,
) -> None:
    repo_info = {"id": "repo1", "project": {"id": "proj1"}}
    commit_id = "commit1"
    changed_file = {"item": {"path": "file.txt"}}
    mock_azure_devops_client.get_file_by_commit.return_value = b"test content"

    with patch(
        "azure_devops.webhooks.webhook_processors.file_webhook_processor.parse_file_content",
        new_callable=AsyncMock,
    ) as mock_parse:
        mock_parse.return_value = {"parsed_data": "..."}
        entity = await file_processor._build_file_entity_from_commit(
            repo_info, commit_id, changed_file
        )
        assert entity == {
            "kind": Kind.FILE,
            "file": {
                "path": "file.txt",
                "size": 12,
                "content": {"raw": "test content", "parsed": {"parsed_data": "..."}},
            },
            "repo": repo_info,
        }
        mock_azure_devops_client.get_file_by_commit.assert_called_once_with(
            "file.txt", "repo1", "commit1"
        )
        mock_parse.assert_called_once_with(b"test content")


@pytest.mark.asyncio
async def test_file_build_file_entity_from_commit_no_content(
    file_processor: FileWebhookProcessor,
    mock_azure_devops_client: MagicMock,
) -> None:
    repo_info = {"id": "repo1", "project": {"id": "proj1"}}
    commit_id = "commit1"
    changed_file = {"item": {"path": "file.txt"}}
    mock_azure_devops_client.get_file_by_commit.return_value = None
    entity = await file_processor._build_file_entity_from_commit(
        repo_info, commit_id, changed_file
    )
    assert entity is None
