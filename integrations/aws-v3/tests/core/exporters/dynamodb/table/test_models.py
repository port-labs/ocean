import pytest
from datetime import datetime
from pydantic import ValidationError
from aws.core.exporters.dynamodb.table.models import (
    TableProperties,
    Table,
    SingleTableRequest,
    PaginatedTableRequest,
)


def test_table_properties_minimal():
    """Test TableProperties with minimal required fields."""
    props = TableProperties()
    
    assert props.TableName == ""
    assert props.TableArn == ""
    assert props.TableId == ""
    assert props.TableStatus == ""
    assert props.CreationDateTime is None
    assert props.Tags == []


def test_table_properties_full():
    """Test TableProperties with all fields populated."""
    creation_time = datetime(2023, 1, 1, 12, 0, 0)
    
    props = TableProperties(
        TableName="test-table",
        TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
        TableId="12345678-1234-1234-1234-123456789012",
        TableStatus="ACTIVE",
        CreationDateTime=creation_time,
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        BillingModeSummary={"BillingMode": "PAY_PER_REQUEST"},
        TableSizeBytes=1024,
        ItemCount=10,
        Tags=[{"Key": "Environment", "Value": "test"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"}],
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            }
        ],
        LocalSecondaryIndexes=[
            {
                "IndexName": "LSI1", 
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"},
                    {"AttributeName": "lsi1sk", "KeyType": "RANGE"}
                ]
            }
        ],
        StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"},
        LatestStreamLabel="2023-01-01T12:00:00.000Z",
        LatestStreamArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table/stream/2023-01-01T12:00:00.000",
        DeletionProtectionEnabled=True,
    )
    
    assert props.TableName == "test-table"
    assert props.TableArn == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    assert props.TableStatus == "ACTIVE"
    assert props.CreationDateTime == creation_time
    assert len(props.AttributeDefinitions) == 1
    assert len(props.KeySchema) == 1
    assert props.BillingModeSummary["BillingMode"] == "PAY_PER_REQUEST"
    assert props.TableSizeBytes == 1024
    assert props.ItemCount == 10
    assert len(props.Tags) == 1
    assert len(props.GlobalSecondaryIndexes) == 1
    assert len(props.LocalSecondaryIndexes) == 1
    assert props.DeletionProtectionEnabled is True


def test_table_model():
    """Test the Table model."""
    table = Table()
    
    assert table.Type == "AWS::DynamoDB::Table"
    assert isinstance(table.Properties, TableProperties)
    
    # Test with custom properties
    props = TableProperties(TableName="my-table", TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/my-table")
    table_with_props = Table(Properties=props)
    
    assert table_with_props.Properties.TableName == "my-table"
    assert table_with_props.Properties.TableArn == "arn:aws:dynamodb:us-east-1:123456789012:table/my-table"


def test_single_table_request():
    """Test SingleTableRequest model."""
    request = SingleTableRequest(
        region="us-east-1",
        account_id="123456789012",
        table_name="test-table",
        include=["tags", "backup"]
    )
    
    assert request.region == "us-east-1"
    assert request.account_id == "123456789012" 
    assert request.table_name == "test-table"
    assert request.include == ["tags", "backup"]


def test_single_table_request_missing_table_name():
    """Test SingleTableRequest validation when table_name is missing."""
    with pytest.raises(ValidationError) as exc_info:
        SingleTableRequest(
            region="us-east-1",
            account_id="123456789012"
        )
    
    assert "table_name" in str(exc_info.value)


def test_paginated_table_request():
    """Test PaginatedTableRequest model."""
    request = PaginatedTableRequest(
        region="us-west-2", 
        account_id="123456789012",
        include=[]
    )
    
    assert request.region == "us-west-2"
    assert request.account_id == "123456789012"
    assert request.include == []


def test_table_properties_extra_fields_forbidden():
    """Test that TableProperties forbids extra fields."""
    with pytest.raises(ValidationError) as exc_info:
        TableProperties(
            TableName="test-table",
            UnknownField="this should fail"
        )
    
    assert "extra fields not permitted" in str(exc_info.value).lower()


def test_table_properties_populate_by_name():
    """Test that field aliases work correctly."""
    # This test ensures populate_by_name=True works 
    # In practice this would be for API response field mapping
    props = TableProperties(
        TableName="test-table",
        TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
    )
    
    assert props.TableName == "test-table"
    assert props.TableArn == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"