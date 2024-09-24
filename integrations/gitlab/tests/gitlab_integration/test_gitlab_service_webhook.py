from unittest.mock import MagicMock, AsyncMock
from gitlab_integration.gitlab_service import GitlabService
import pytest


@pytest.mark.asyncio
async def test_delete_group_webhook_success(
    mocked_gitlab_service: GitlabService,
) -> None:
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 123
    mock_group.hooks.delete = AsyncMock()  # Mock successful deletion

    # Mock the group hooks.list method to return a webhook
    mock_hook = MagicMock()
    mock_hook.url = "http://example.com/integration/hook/456"
    mock_hook.id = 17

    # Act
    await mocked_gitlab_service._delete_group_webhook(mock_group, mock_hook.id)

    # Assert
    mock_group.hooks.delete.assert_called_once_with(mock_hook.id)


@pytest.mark.asyncio
async def test_delete_group_webhook_failure(
    mocked_gitlab_service: GitlabService,
) -> None:
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 123
    mock_group.hooks.delete = AsyncMock(side_effect=Exception("Delete failed"))

    mock_hook = MagicMock()
    mock_hook.url = "http://example.com/integration/hook/456"
    mock_hook.id = 17
    # Act
    await mocked_gitlab_service._delete_group_webhook(mock_group, mock_hook.id)

    # Assert
    mock_group.hooks.delete.assert_called_once_with(mock_hook.id)


@pytest.mark.asyncio
async def test_create_group_webhook_success(
    mocked_gitlab_service: GitlabService,
) -> None:
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 123
    mock_group.hooks.create = AsyncMock(
        return_value=MagicMock(id=789, url="http://example.com/hook/123")
    )

    # Act
    await mocked_gitlab_service._create_group_webhook(
        mock_group, ["push_events", "merge_requests_events"]
    )

    # Assert
    mock_group.hooks.create.assert_called_once_with(
        {
            "url": "http://example.com/integration/hook/123",
            "push_events": True,
            "merge_requests_events": True,
            "issues_events": False,
            "job_events": False,
            "pipeline_events": False,
            "releases_events": False,
            "tag_push_events": False,
            "subgroup_events": False,
            "confidential_issues_events": False,
        }
    )


@pytest.mark.asyncio
async def test_create_group_webhook_failure(
    mocked_gitlab_service: GitlabService,
) -> None:
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 123
    mock_group.hooks.create = AsyncMock(side_effect=Exception("Create failed"))

    # Act
    await mocked_gitlab_service._create_group_webhook(
        mock_group, ["push_events", "merge_requests_events"]
    )

    # Assert
    mock_group.hooks.create.assert_called_once_with(
        {
            "url": "http://example.com/integration/hook/123",
            "push_events": True,
            "merge_requests_events": True,
            "issues_events": False,
            "job_events": False,
            "pipeline_events": False,
            "releases_events": False,
            "tag_push_events": False,
            "subgroup_events": False,
            "confidential_issues_events": False,
        }
    )
