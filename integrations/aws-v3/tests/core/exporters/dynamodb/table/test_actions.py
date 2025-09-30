import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from aws.core.exporters.dynamodb.table.actions import (
    GetTableDetailsAction,
    GetTableTagsAction,
    GetTableBackupStatusAction,
    ListTablesAction,
)


@pytest.mark.asyncio
async def test_get_table_details_action():
    action = GetTableDetailsAction()
    action.client = AsyncMock()
    action.client.describe_table.return_value = {
        "Table": {
            "TableName": "test-table",
            "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            "TableId": "12345678-1234-1234-1234-123456789012",
            "TableStatus": "ACTIVE",
            "CreationDateTime": datetime(2023, 1, 1, 12, 0, 0),
            "AttributeDefinitions": [
                {"AttributeName": "id", "AttributeType": "S"}
            ],
            "KeySchema": [
                {"AttributeName": "id", "KeyType": "HASH"}
            ],
            "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
            "TableSizeBytes": 1024,
            "ItemCount": 10,
        }
    }

    result = await action._execute([{"TableName": "test-table"}])

    assert len(result) == 1
    assert result[0]["TableName"] == "test-table"
    assert result[0]["TableArn"] == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    assert result[0]["TableStatus"] == "ACTIVE"
    assert result[0]["TableSizeBytes"] == 1024
    assert result[0]["ItemCount"] == 10
    action.client.describe_table.assert_called_once_with(TableName="test-table")


@pytest.mark.asyncio
async def test_get_table_tags_action():
    action = GetTableTagsAction()
    action.client = AsyncMock()
    action.client.list_tags_of_resource.return_value = {
        "Tags": [
            {"Key": "Environment", "Value": "test"},
            {"Key": "Application", "Value": "my-app"}
        ]
    }

    result = await action._execute([{
        "TableName": "test-table",
        "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    }])

    assert len(result) == 1
    assert len(result[0]["Tags"]) == 2
    assert result[0]["Tags"][0]["Key"] == "Environment"
    assert result[0]["Tags"][0]["Value"] == "test"
    action.client.list_tags_of_resource.assert_called_once_with(
        ResourceArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    )


@pytest.mark.asyncio
async def test_get_table_tags_action_no_tags():
    action = GetTableTagsAction()
    action.client = AsyncMock()
    action.client.list_tags_of_resource.return_value = {"Tags": []}

    result = await action._execute([{
        "TableName": "test-table",
        "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    }])

    assert len(result) == 1
    assert result[0]["Tags"] == []


@pytest.mark.asyncio
async def test_get_table_backup_status_action():
    action = GetTableBackupStatusAction()
    action.client = AsyncMock()
    action.client.describe_continuous_backups.return_value = {
        "ContinuousBackupsDescription": {
            "ContinuousBackupsStatus": "ENABLED",
            "PointInTimeRecoveryDescription": {
                "PointInTimeRecoveryStatus": "ENABLED"
            }
        }
    }

    result = await action._execute([{"TableName": "test-table"}])

    assert len(result) == 1
    assert result[0]["ContinuousBackupsDescription"]["ContinuousBackupsStatus"] == "ENABLED"
    assert result[0]["PointInTimeRecoveryDescription"]["PointInTimeRecoveryStatus"] == "ENABLED"
    action.client.describe_continuous_backups.assert_called_once_with(TableName="test-table")


@pytest.mark.asyncio
async def test_list_tables_action():
    action = ListTablesAction()
    
    result = await action._execute(["table1", "table2", "table3"])

    assert len(result) == 3
    assert result[0]["TableName"] == "table1"
    assert result[1]["TableName"] == "table2"
    assert result[2]["TableName"] == "table3"


@pytest.mark.asyncio
async def test_list_tables_action_with_dict_format():
    action = ListTablesAction()
    
    result = await action._execute([
        {"TableName": "table1"},
        {"TableName": "table2"}
    ])

    assert len(result) == 2
    assert result[0]["TableName"] == "table1"
    assert result[1]["TableName"] == "table2"


@pytest.mark.asyncio
async def test_get_table_details_action_with_exception():
    action = GetTableDetailsAction()
    action.client = AsyncMock()
    action.client.describe_table.side_effect = Exception("Table not found")

    result = await action._execute([{"TableName": "non-existent-table"}])

    assert len(result) == 0  # Should return empty list when exception occurs


@pytest.mark.asyncio
async def test_get_table_tags_action_with_client_error():
    from botocore.exceptions import ClientError
    
    action = GetTableTagsAction()
    action.client = AsyncMock()
    
    # Mock ClientError for ResourceNotFoundException
    error_response = {
        "Error": {
            "Code": "ResourceNotFoundException",
            "Message": "Requested resource not found"
        }
    }
    action.client.exceptions.ClientError = ClientError
    action.client.list_tags_of_resource.side_effect = ClientError(
        error_response, "ListTagsOfResource"
    )

    result = await action._execute([{
        "TableName": "test-table",
        "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    }])

    assert len(result) == 1
    assert result[0]["Tags"] == []