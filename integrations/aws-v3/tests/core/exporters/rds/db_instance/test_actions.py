from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.rds.db_instance.actions import (
    DescribeDBInstancesAction,
    ListTagsForResourceAction,
    RdsDbInstanceActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeDBInstancesAction:

    @pytest.fixture
    def action(self) -> DescribeDBInstancesAction:
        return DescribeDBInstancesAction(AsyncMock())

    def test_inheritance(self, action: DescribeDBInstancesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input(
        self, action: DescribeDBInstancesAction
    ) -> None:
        """Test that the pass-through action returns the input as-is."""
        db_instances = [
            {
                "DBInstanceIdentifier": "db-1",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-1",
            },
            {
                "DBInstanceIdentifier": "db-2",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-2",
            },
        ]
        result = await action.execute(db_instances)
        assert result == db_instances


class TestListTagsForResourceAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.list_tags_for_resource = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsForResourceAction:
        return ListTagsForResourceAction(mock_client)

    def test_inheritance(self, action: ListTagsForResourceAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test successful execution of list_tags_for_resource."""
        db_instances = [
            {
                "DBInstanceIdentifier": "db-1",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-1",
            },
            {
                "DBInstanceIdentifier": "db-2",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-2",
            },
        ]

        # Mock should return different responses for each individual call
        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if ResourceName == "arn:aws:rds:us-east-1:123456789012:db:db-1":
                return {
                    "TagList": [
                        {"Key": "Environment", "Value": "production"},
                        {"Key": "Project", "Value": "web-app"},
                    ]
                }
            elif ResourceName == "arn:aws:rds:us-east-1:123456789012:db:db-2":
                return {
                    "TagList": [
                        {"Key": "Environment", "Value": "staging"},
                        {"Key": "Owner", "Value": "devops-team"},
                    ]
                }
            else:
                return {"TagList": []}

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(db_instances)

        expected_result = [
            {
                "Tags": [
                    {"Key": "Environment", "Value": "production"},
                    {"Key": "Project", "Value": "web-app"},
                ]
            },
            {
                "Tags": [
                    {"Key": "Environment", "Value": "staging"},
                    {"Key": "Owner", "Value": "devops-team"},
                ]
            },
        ]
        assert result == expected_result

        # Verify that list_tags_for_resource was called twice (once for each DB instance)
        assert action.client.list_tags_for_resource.call_count == 2
        action.client.list_tags_for_resource.assert_any_call(
            ResourceName="arn:aws:rds:us-east-1:123456789012:db:db-1"
        )
        action.client.list_tags_for_resource.assert_any_call(
            ResourceName="arn:aws:rds:us-east-1:123456789012:db:db-2"
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 2 DB instances"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.actions.logger")
    async def test_execute_with_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test that recoverable exceptions are handled gracefully and logged as warnings."""
        db_instances = [
            {
                "DBInstanceIdentifier": "db-1",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-1",
            },
            {
                "DBInstanceIdentifier": "db-2",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-2",
            },
        ]

        # First call succeeds, second call fails with AccessDenied (recoverable)
        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if ResourceName == "arn:aws:rds:us-east-1:123456789012:db:db-1":
                return {"TagList": [{"Key": "Environment", "Value": "production"}]}
            else:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                    "ListTagsForResource",
                )

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(db_instances)

        # Should only return results for successful calls
        expected_result = [{"Tags": [{"Key": "Environment", "Value": "production"}]}]
        assert result == expected_result

        # Verify warning logging for recoverable exception
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Skipping tags for DB instance 'db-2'" in warning_call
        assert "Access denied" in warning_call

        # Verify success logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 DB instances"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.actions.logger")
    async def test_execute_with_non_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test that non-recoverable exceptions are raised."""
        db_instances = [
            {
                "DBInstanceIdentifier": "db-1",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-1",
            },
        ]

        # Mock a non-recoverable exception (network error)
        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            raise ClientError(
                {"Error": {"Code": "NetworkError", "Message": "Network timeout"}},
                "ListTagsForResource",
            )

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        # Should raise the exception
        with pytest.raises(ClientError) as exc_info:
            await action.execute(db_instances)

        assert exc_info.value.response["Error"]["Code"] == "NetworkError"

        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error fetching tags for DB instance 'db-1'" in error_call
        assert "Network timeout" in error_call

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.actions.logger")
    async def test_execute_empty_tag_list(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test execution when DB instance has no tags."""
        db_instances = [
            {
                "DBInstanceIdentifier": "db-1",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-1",
            }
        ]

        action.client.list_tags_for_resource.return_value = {"TagList": []}

        result = await action.execute(db_instances)

        expected_result: list[dict[str, Any]] = [{"Tags": []}]
        assert result == expected_result

        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceName="arn:aws:rds:us-east-1:123456789012:db:db-1"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 DB instances"
        )


class TestRdsDbInstanceActionsMap:

    def test_merge_includes_defaults(self) -> None:
        """Test that merge includes default actions."""
        action_map = RdsDbInstanceActionsMap()
        merged = action_map.merge([])

        # Default is DescribeDBInstancesAction
        names = [cls.__name__ for cls in merged]
        assert "DescribeDBInstancesAction" in names

    def test_merge_with_options(self) -> None:
        """Test that merge includes optional actions when specified."""
        include = ["ListTagsForResourceAction"]
        actions = RdsDbInstanceActionsMap().merge(include)
        names = [a.__name__ for a in actions]
        assert "DescribeDBInstancesAction" in names
        assert "ListTagsForResourceAction" in names

    def test_merge_with_list_tags_action(self) -> None:
        """Test that merge includes ListTagsForResourceAction when specified."""
        action_map = RdsDbInstanceActionsMap()
        merged = action_map.merge(["ListTagsForResourceAction"])

        names = [cls.__name__ for cls in merged]
        assert "DescribeDBInstancesAction" in names  # Default action
        assert "ListTagsForResourceAction" in names  # Optional action when specified
