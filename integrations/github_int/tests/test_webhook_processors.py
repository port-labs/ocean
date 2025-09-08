import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload, EventHeaders
from webhook_processors.pull_request import PullRequestWebhookProcessor
from webhook_processors.issue import IssueWebhookProcessor
from webhook_processors.file import FileWebhookProcessor
from webhook_processors.folder import FolderWebhookProcessor

@pytest.mark.asyncio
async def test_pull_request_processor_should_process():
    processor = PullRequestWebhookProcessor()
    event = WebhookEvent(headers=EventHeaders({"X-GitHub-Event": "pull_request"}), payload=EventPayload({}))
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == ["githubPullRequest"]

@pytest.mark.asyncio
async def test_pull_request_processor_handle_event():
    processor = PullRequestWebhookProcessor()
    payload = EventPayload({"action": "opened", "pull_request": {"number": 1, "base": {"repo": {"full_name": "test/repo"}}}})
    resource_config = None  # Mock as needed
    with patch('webhook_processors.pull_request.create_client', return_value=AsyncMock()) as mock_client:
        mock_client.return_value._send_api_request.return_value = {"id": 123}
        result = await processor.handle_event(payload, resource_config)
        assert len(result.updated_raw_results) == 1

@pytest.mark.asyncio
async def test_issue_processor_should_process():
    processor = IssueWebhookProcessor()
    event = WebhookEvent(headers=EventHeaders({"X-GitHub-Event": "issues"}), payload=EventPayload({}))
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == ["githubIssue"]

@pytest.mark.asyncio
async def test_issue_processor_handle_event():
    processor = IssueWebhookProcessor()
    payload = EventPayload({"action": "opened", "issue": {"number": 1}, "repository": {"full_name": "test/repo"}})
    resource_config = None
    with patch('webhook_processors.issue.create_client', return_value=AsyncMock()) as mock_client:
        mock_client.return_value._send_api_request.return_value = {"id": 456, "number": 1}
        result = await processor.handle_event(payload, resource_config)
        assert len(result.updated_raw_results) == 1

@pytest.mark.asyncio
async def test_file_processor_should_process():
    processor = FileWebhookProcessor()
    event = WebhookEvent(headers=EventHeaders({"X-GitHub-Event": "push"}), payload=EventPayload({}))
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == ["file"]

@pytest.mark.asyncio
async def test_file_processor_handle_event():
    processor = FileWebhookProcessor()
    payload = EventPayload({
        "ref": "refs/heads/main",
        "repository": {"full_name": "test/repo", "id": 123, "default_branch": "main"},
        "commits": [{"added": ["file.py"], "modified": [], "removed": []}]
    })
    resource_config = type('MockConfig', (), {'selector': type('MockSelector', (), {'extensions': ['.py'], 'paths': None})})()
    with patch('webhook_processors.file.create_client', return_value=AsyncMock()) as mock_client:
        mock_client.return_value.get_file_content.return_value = {"path": "file.py", "repository_id": 123}
        result = await processor.handle_event(payload, resource_config)
        assert len(result.updated_raw_results) == 1

# Add to test_webhook_processors.py

@pytest.mark.asyncio
async def test_folder_processor_should_process():
    processor = FolderWebhookProcessor()
    event = WebhookEvent(headers=EventHeaders({"X-GitHub-Event": "push"}), payload=EventPayload({}))
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == ["githubFolder"]

@pytest.mark.asyncio
async def test_folder_processor_handle_event():
    processor = FolderWebhookProcessor()
    payload = EventPayload({
        "ref": "refs/heads/main",
        "repository": {"full_name": "test/repo", "id": 123, "default_branch": "main"},
        "commits": [{"added": ["services/newfolder/"]}]
    })
    resource_config = type('MockConfig', (), {'selector': type('MockSelector', (), {'paths': ['services/']})})()
    with patch('webhook_processors.folder.create_client', return_value=AsyncMock()) as mock_client:
        mock_client.return_value.get_folders.return_value = [[{"path": "services/newfolder"}]]
        result = await processor.handle_event(payload, resource_config)
        assert len(result.updated_raw_results) == 1