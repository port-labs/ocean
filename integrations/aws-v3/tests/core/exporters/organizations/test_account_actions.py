import pytest
from typing import Any
from unittest.mock import AsyncMock
from botocore.exceptions import ClientError

from aws.core.exporters.organizations.account.actions import (
    ListTagsAction,
    OrganizationsAccountActionsMap,
)
from aws.core.interfaces.action import Action

# Type ignore for mock Organizations client methods throughout this file
# mypy: disable-error-code=attr-defined


class TestListTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock Organizations client for testing."""
        mock_client = AsyncMock()
        mock_client.list_tags_for_resource = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsAction:
        """Create a ListTagsAction instance for testing."""
        return ListTagsAction(mock_client)

    def test_inheritance(self, action: ListTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success_with_tags(self, action: ListTagsAction) -> None:
        """Test successful execution of list_tags_for_resource with tags."""
        # Mock response
        expected_response = {
            "Tags": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Project", "Value": "aws-integration"},
            ]
        }
        action.client.list_tags_for_resource.return_value = expected_response

        # Execute
        result = await action.execute("123456789012")

        # Verify
        assert result == {"Tags": expected_response["Tags"]}

        # Verify client was called correctly
        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceId="123456789012"
        )

    @pytest.mark.asyncio
    async def test_execute_success_no_tags(self, action: ListTagsAction) -> None:
        """Test successful execution of list_tags_for_resource with no tags."""
        # Mock response
        expected_response: dict[str, list[dict[str, str]]] = {"Tags": []}
        action.client.list_tags_for_resource.return_value = expected_response

        # Execute
        result = await action.execute("123456789012")

        # Verify
        expected_result: dict[str, list[dict[str, str]]] = {"Tags": []}
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_execute_different_account_id(self, action: ListTagsAction) -> None:
        """Test execution with different account ID."""
        expected_response = {"Tags": [{"Key": "Team", "Value": "platform"}]}
        action.client.list_tags_for_resource.return_value = expected_response

        result = await action.execute("987654321098")

        assert result == {"Tags": expected_response["Tags"]}
        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceId="987654321098"
        )

    @pytest.mark.asyncio
    async def test_execute_access_denied(self, action: ListTagsAction) -> None:
        """Test execution when access is denied."""
        error_response: dict[str, Any] = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "User is not authorized to perform: organizations:ListTagsForResource",
            }
        }
        action.client.list_tags_for_resource.side_effect = ClientError(
            error_response, "ListTagsForResource"  # type: ignore
        )

        # Should raise the exception
        with pytest.raises(ClientError):
            await action.execute("123456789012")

        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceId="123456789012"
        )


class TestOrganizationsAccountActionsMap:

    def test_defaults_is_empty(self) -> None:
        """Test that defaults is empty for account actions."""
        actions_map = OrganizationsAccountActionsMap()
        assert actions_map.defaults == []
        assert len(actions_map.defaults) == 0

    def test_options_contains_list_tags_action(self) -> None:
        """Test that options contains the correct action."""
        actions_map = OrganizationsAccountActionsMap()
        assert ListTagsAction in actions_map.options
        assert len(actions_map.options) == 1

    def test_merge_with_empty_include(self) -> None:
        """Test merge with empty include list."""
        actions_map = OrganizationsAccountActionsMap()
        result = actions_map.merge([])

        assert len(result) == 0
        assert ListTagsAction not in result

    def test_merge_with_list_tags_action(self) -> None:
        """Test merge with ListTagsAction included."""
        actions_map = OrganizationsAccountActionsMap()
        result = actions_map.merge(["ListTagsAction"])

        assert len(result) == 1
        assert ListTagsAction in result

    def test_merge_with_unknown_action(self) -> None:
        """Test merge with unknown action name."""
        actions_map = OrganizationsAccountActionsMap()
        result = actions_map.merge(["UnknownAction"])

        assert len(result) == 0
        assert ListTagsAction not in result

    def test_merge_with_multiple_actions(self) -> None:
        """Test merge with multiple action names."""
        actions_map = OrganizationsAccountActionsMap()
        result = actions_map.merge(["ListTagsAction", "UnknownAction"])

        assert len(result) == 1
        assert ListTagsAction in result

    def test_merge_case_sensitive(self) -> None:
        """Test that action names are case sensitive."""
        actions_map = OrganizationsAccountActionsMap()
        result = actions_map.merge(["listtagsaction"])  # lowercase

        assert len(result) == 0
        assert ListTagsAction not in result
