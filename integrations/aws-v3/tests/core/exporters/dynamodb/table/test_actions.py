from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.dynamodb.table.actions import (
    DescribeTableAction,
    ListTagsOfResourceAction,
    ListTablesAction,
    DynamoDBTableActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeTableAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock DynamoDB client for testing."""
        mock_client = AsyncMock()
        mock_client.describe_table = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> DescribeTableAction:
        """Create a DescribeTableAction instance for testing."""
        return DescribeTableAction(mock_client)

    def test_inheritance(self, action: DescribeTableAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: DescribeTableAction) -> None:
        """Test successful execution of describe_table."""
        expected_response = {
            "Table": {
                "TableName": "test-table",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "TableId": "abc-123",
                "TableStatus": "ACTIVE",
                "TableSizeBytes": 1024,
                "ItemCount": 10,
                "CreationDateTime": "2021-01-01T00:00:00Z",
            }
        }
        action.client.describe_table.return_value = expected_response

        result = await action._execute(["test-table"])

        assert len(result) == 1
        assert result[0]["TableName"] == "test-table"
        assert (
            result[0]["TableArn"]
            == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
        )
        assert result[0]["TableStatus"] == "ACTIVE"

        action.client.describe_table.assert_called_once_with(TableName="test-table")

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: DescribeTableAction) -> None:
        """Test execution with empty table list."""
        result = await action._execute([])

        assert result == []
        action.client.describe_table.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: DescribeTableAction
    ) -> None:
        """Test execution with recoverable exception preserves an empty placeholder."""
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException"}},
            operation_name="DescribeTable",
        )
        action.client.describe_table.side_effect = error

        result = await action._execute(["test-table"])

        # Recoverable error must still produce an entry to preserve index alignment
        assert result == [{}]
        action.client.describe_table.assert_called_once_with(TableName="test-table")

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: DescribeTableAction
    ) -> None:
        """Middle table fails recoverably; results keep aligned positions."""

        def mock_describe_table(TableName: str, **kwargs: Any) -> dict[str, Any]:
            if TableName == "table-2":
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDeniedException"}},
                    operation_name="DescribeTable",
                )
            return {
                "Table": {
                    "TableName": TableName,
                    "TableArn": f"arn:aws:dynamodb:us-east-1:123456789012:table/{TableName}",
                    "TableStatus": "ACTIVE",
                }
            }

        action.client.describe_table.side_effect = mock_describe_table

        table_names = ["table-1", "table-2", "table-3"]
        result = await action._execute(table_names)

        assert len(result) == 3
        assert result[0]["TableName"] == "table-1"
        assert result[1] == {}
        assert result[2]["TableName"] == "table-3"

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: DescribeTableAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="DescribeTable",
        )
        action.client.describe_table.side_effect = error

        with pytest.raises(ClientError):
            await action._execute(["test-table"])


class TestListTagsOfResourceAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock DynamoDB client for testing."""
        mock_client = AsyncMock()
        mock_client.describe_table = AsyncMock()
        mock_client.list_tags_of_resource = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsOfResourceAction:
        """Create a ListTagsOfResourceAction instance for testing."""
        return ListTagsOfResourceAction(mock_client)

    def test_inheritance(self, action: ListTagsOfResourceAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListTagsOfResourceAction) -> None:
        """Test successful execution of list_tags_of_resource."""
        action.client.describe_table.return_value = {
            "Table": {
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
            }
        }
        action.client.list_tags_of_resource.return_value = {
            "Tags": [{"Key": "Environment", "Value": "Production"}]
        }

        result = await action._execute(["test-table"])

        assert len(result) == 1
        assert result[0]["Tags"] == [{"Key": "Environment", "Value": "Production"}]

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListTagsOfResourceAction) -> None:
        """Test execution with empty table list."""
        result = await action._execute([])

        assert result == []
        action.client.describe_table.assert_not_called()
        action.client.list_tags_of_resource.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_no_tags(self, action: ListTagsOfResourceAction) -> None:
        """Test execution with no tags."""
        action.client.describe_table.return_value = {
            "Table": {
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
            }
        }
        action.client.list_tags_of_resource.return_value = {"Tags": []}

        result = await action._execute(["test-table"])

        assert len(result) == 1
        assert result[0]["Tags"] == []

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: ListTagsOfResourceAction
    ) -> None:
        """Test execution with recoverable exception preserves an empty placeholder."""
        error = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException"}},
            operation_name="ListTagsOfResource",
        )
        action.client.describe_table.side_effect = error

        result = await action._execute(["test-table"])

        # Recoverable error must still produce an entry to preserve index alignment
        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: ListTagsOfResourceAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="ListTagsOfResource",
        )
        action.client.describe_table.side_effect = error

        with pytest.raises(ClientError):
            await action._execute(["test-table"])


class TestListTablesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock DynamoDB client for testing."""
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTablesAction:
        """Create a ListTablesAction instance for testing."""
        return ListTablesAction(mock_client)

    def test_inheritance(self, action: ListTablesAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListTablesAction) -> None:
        """Test successful execution of list tables (pass-through)."""
        table_names = ["table-1", "table-2"]

        result = await action._execute(table_names)

        assert len(result) == 2
        assert result[0]["TableName"] == "table-1"
        assert result[1]["TableName"] == "table-2"

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListTablesAction) -> None:
        """Test execution with empty table list."""
        result = await action._execute([])
        assert result == []


class TestDynamoDBTableActionsMap:

    def test_defaults_include_required_actions(self) -> None:
        """Test that defaults include all required actions."""
        actions_map = DynamoDBTableActionsMap()
        assert ListTablesAction in actions_map.defaults
        assert DescribeTableAction in actions_map.defaults

    def test_options_include_tag_action(self) -> None:
        """Test that tag action is optional."""
        actions_map = DynamoDBTableActionsMap()
        assert actions_map.options == [ListTagsOfResourceAction]
