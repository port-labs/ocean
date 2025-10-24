import pytest
from typing import Any, Dict, List
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)


@pytest.fixture
def branch_webhook_processor(event: WebhookEvent) -> BranchWebhookProcessor:
    return BranchWebhookProcessor(event)


@pytest.mark.asyncio
async def test_should_process_event(
    branch_webhook_processor: BranchWebhookProcessor, mock_event_context: None
) -> None:
    event = WebhookEvent(
        trace_id="t",
        payload={"eventType": "git.push", "publisherId": "tfs", "resource": {}},
        headers={},
    )
    assert await branch_webhook_processor.should_process_event(event) is True
    event.payload["eventType"] = "git.repo.created"
    assert await branch_webhook_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_validate_payload(
    branch_webhook_processor: BranchWebhookProcessor, mock_event_context: None
) -> None:
    valid = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {
            "repository": {"id": "repo1"},
            "refUpdates": [{"name": "refs/heads/main", "newObjectId": "abc"}],
        },
    }
    assert await branch_webhook_processor.validate_payload(valid) is True
    assert await branch_webhook_processor.validate_payload({"resource": {}}) is False


@pytest.mark.asyncio
async def test_handle_event_update_and_delete(
    branch_webhook_processor: BranchWebhookProcessor, mock_event_context: None
) -> None:
    payload = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "repo1",
                "name": "Test Repo",
                "project": {"id": "p1", "name": "Test Project"},
            },
            "refUpdates": [
                {"name": "refs/heads/main", "oldObjectId": "old", "newObjectId": "new"},
                {
                    "name": "refs/heads/feature/x",
                    "oldObjectId": "old2",
                    "newObjectId": "0000000000000000000000000000000000000000",
                },
                {"name": "refs/tags/v1.0", "oldObjectId": "t", "newObjectId": "t2"},
            ],
        },
    }
    result = await branch_webhook_processor.handle_event(
        payload, resource_config=MagicMock()
    )

    # Test updated branches
    assert len(result.updated_raw_results) == 1
    updated_branch = result.updated_raw_results[0]
    assert updated_branch["name"] == "main"
    assert updated_branch["refName"] == "refs/heads/main"
    assert updated_branch["objectId"] == "new"
    assert "__repository" in updated_branch
    assert updated_branch["__repository"]["id"] == "repo1"

    # Test deleted branches
    assert len(result.deleted_raw_results) == 1
    deleted_branch = result.deleted_raw_results[0]
    assert deleted_branch["name"] == "feature/x"
    assert deleted_branch["refName"] == "refs/heads/feature/x"
    assert deleted_branch["objectId"] == "old2"
    assert "__repository" in deleted_branch


@pytest.mark.asyncio
async def test_handle_event_repository_with_no_matching_branches(
    branch_webhook_processor: BranchWebhookProcessor, mock_event_context: None
) -> None:
    """Test handling when repository exists but has no matching branch updates."""
    payload = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "repo1",
                "name": "Test Repo",
                "project": {"id": "p1", "name": "Test Project"},
            },
            "refUpdates": [],  # Empty ref updates
        },
    }

    result = await branch_webhook_processor.handle_event(
        payload, resource_config=MagicMock()
    )
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_no_branch_refs(
    branch_webhook_processor: BranchWebhookProcessor, mock_event_context: None
) -> None:
    """Test handling when no branch references are present."""
    payload = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "repo1",
                "name": "Test Repo",
                "project": {"id": "p1", "name": "Test Project"},
            },
            "refUpdates": [
                {"name": "refs/tags/v1.0", "oldObjectId": "t", "newObjectId": "t2"},
                {
                    "name": "refs/remotes/origin/main",
                    "oldObjectId": "old",
                    "newObjectId": "new",
                },
            ],
        },
    }

    result = await branch_webhook_processor.handle_event(
        payload, resource_config=MagicMock()
    )
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


def test_extract_branch_changes_static_method() -> None:
    """Test the static method for extracting branch changes."""
    repository = {
        "id": "repo1",
        "name": "Test Repo",
        "project": {"id": "p1", "name": "Project"},
    }

    ref_updates = [
        {"name": "refs/heads/main", "oldObjectId": "old1", "newObjectId": "new1"},
        {
            "name": "refs/heads/feature",
            "oldObjectId": "old2",
            "newObjectId": "0000000000000000000000000000000000000000",
        },
        {"name": "refs/tags/v1.0", "oldObjectId": "t1", "newObjectId": "t2"},
        {"name": "refs/heads/bugfix", "oldObjectId": "old3", "newObjectId": "new3"},
    ]

    updated, deleted = BranchWebhookProcessor._extract_branch_changes(
        ref_updates, repository
    )

    # Test updated branches
    assert len(updated) == 2
    assert updated[0]["name"] == "main"
    assert updated[0]["refName"] == "refs/heads/main"
    assert updated[0]["objectId"] == "new1"
    assert updated[0]["__repository"] == repository

    assert updated[1]["name"] == "bugfix"
    assert updated[1]["refName"] == "refs/heads/bugfix"
    assert updated[1]["objectId"] == "new3"

    # Test deleted branches
    assert len(deleted) == 1
    assert deleted[0]["name"] == "feature"
    assert deleted[0]["refName"] == "refs/heads/feature"
    assert deleted[0]["objectId"] == "old2"


def test_extract_branch_changes_empty_input() -> None:
    """Test static method with empty input."""
    repository = {"id": "repo1", "name": "Test Repo"}
    updated, deleted = BranchWebhookProcessor._extract_branch_changes([], repository)
    assert len(updated) == 0
    assert len(deleted) == 0


def test_extract_branch_changes_malformed_refs() -> None:
    """Test static method with malformed ref data."""
    repository = {"id": "repo1", "name": "Test Repo"}

    ref_updates: List[Dict[str, Any]] = [
        {"name": "refs/heads/main"},
        {"name": "refs/heads/branch", "oldObjectId": "old", "newObjectId": None},
        {},
    ]

    updated, deleted = BranchWebhookProcessor._extract_branch_changes(
        ref_updates, repository
    )

    assert len(updated) == 2
    assert len(deleted) == 0
