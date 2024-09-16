from unittest.mock import MagicMock
from typing import Any
from gitlab_integration.gitlab_service import GitlabService


def test_create_webhook_when_webhook_exists_but_disabled(
    mocked_gitlab_service: GitlabService, monkeypatch: Any
):
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 456
    mock_group.attributes = {"full_path": "group2"}

    # Mock the group hooks.list method to return an existing disabled webhook
    mock_hook = MagicMock()
    mock_hook.url = "http://example.com/integration/hook/456"  # Updated URL for clarity
    mock_hook.alert_status = "disabled"
    mock_hook.id = 456
    mock_group.hooks.list.return_value = [mock_hook]

    # Mock the methods for deleting and creating webhooks
    mock_delete_webhook = MagicMock()
    monkeypatch.setattr(mocked_gitlab_service, "_delete_group_webhook", mock_delete_webhook)
    mock_create_webhook = MagicMock()
    monkeypatch.setattr(mocked_gitlab_service, "_create_group_webhook", mock_create_webhook)

    # Act
    webhook_id = mocked_gitlab_service.create_webhook(
        mock_group, events=["push", "merge_request"]
    )

    # Assert
    assert webhook_id == "456"
    mock_delete_webhook.assert_called_once_with(mock_group, mock_hook.id)  # Ensure delete method is called
    mock_create_webhook.assert_called_once_with(mock_group, ["push", "merge_request"])  # Ensure create method is called with correct arguments


def test_create_webhook_when_webhook_exists_and_enabled(
    mocked_gitlab_service: GitlabService, monkeypatch: Any
):
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 789
    mock_group.attributes = {"full_path": "group3"}

    # Mock the group hooks.list method to return an existing enabled webhook
    mock_hook = MagicMock()
    mock_hook.url = "http://example.com/integration/hook/789"
    mock_hook.alert_status = "executable"
    mock_hook.id = 789
    mock_group.hooks.list.return_value = [mock_hook]

    # Mock the method for creating webhooks
    mock_create_webhook = MagicMock()
    monkeypatch.setattr(mocked_gitlab_service, "_create_group_webhook", mock_create_webhook)

    # Act
    webhook_id = mocked_gitlab_service.create_webhook(
        mock_group, events=["push", "merge_request"]
    )

    # Assert
    assert webhook_id == "789"
    mock_create_webhook.assert_not_called()  # Ensure no new webhook is created


def test_create_webhook_when_no_webhook_exists(
    mocked_gitlab_service: GitlabService, monkeypatch: Any
):
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 123
    mock_group.attributes = {"full_path": "group1"}

    # Mock the group hooks.list method to return no webhook
    mock_group.hooks.list.return_value = []

    # Act
    webhook_id = mocked_gitlab_service.create_webhook(
        mock_group, events=["push", "merge_request"]
    )

    # Assert
    assert webhook_id == "123"
    mock_group.hooks.create.assert_called_once()  # A new webhook should be created


def test_delete_webhook(
    mocked_gitlab_service: GitlabService, monkeypatch: Any
):
    # Arrange
    mock_group = MagicMock()
    mock_group.get_id.return_value = 456
    mock_group.attributes = {"full_path": "group2"}

    # Mock the group hooks.list method to return a webhook
    mock_hook = MagicMock()
    mock_hook.url = "http://example.com/integration/hook/17"
    mock_hook.id = 17
    mock_group.hooks.list.return_value = [mock_hook]

    # Act
    mocked_gitlab_service._delete_group_webhook(mock_group, mock_hook.id)

    # Assert
    mock_group.hooks.delete.assert_called_once_with(mock_hook.id)  # Ensure the webhook is deleted

