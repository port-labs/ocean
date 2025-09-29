import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aws.core.exporters.dynamodb.table.exporter import DynamoDBTableExporter
from aws.core.exporters.dynamodb.table.models import SingleTableRequest, PaginatedTableRequest


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def exporter(mock_session):
    return DynamoDBTableExporter(mock_session)


@pytest.mark.asyncio
async def test_get_resource_single_table(exporter, mock_session):
    options = SingleTableRequest(
        region="us-east-1",
        account_id="123456789012",
        table_name="test-table",
        include=[]
    )
    
    mock_response = {
        "Type": "AWS::DynamoDB::Table",
        "Properties": {
            "TableName": "test-table",
            "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            "TableStatus": "ACTIVE"
        }
    }

    with patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy") as mock_proxy_class:
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        
        with patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector") as mock_inspector_class:
            mock_inspector = AsyncMock()
            mock_inspector.inspect.return_value = [mock_response]
            mock_inspector_class.return_value = mock_inspector
            
            result = await exporter.get_resource(options)
            
            assert result == mock_response
            mock_inspector.inspect.assert_called_once_with(
                [{"TableName": "test-table"}], []
            )


@pytest.mark.asyncio 
async def test_get_resource_single_table_not_found(exporter, mock_session):
    options = SingleTableRequest(
        region="us-east-1", 
        account_id="123456789012",
        table_name="non-existent-table",
        include=[]
    )
    
    with patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy") as mock_proxy_class:
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        
        with patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector") as mock_inspector_class:
            mock_inspector = AsyncMock()
            mock_inspector.inspect.return_value = []
            mock_inspector_class.return_value = mock_inspector
            
            result = await exporter.get_resource(options)
            
            assert result == {}


@pytest.mark.asyncio
async def test_get_paginated_resources(exporter, mock_session):
    options = PaginatedTableRequest(
        region="us-east-1",
        account_id="123456789012",
        include=[]
    )
    
    mock_table_batch1 = [
        {
            "Type": "AWS::DynamoDB::Table",
            "Properties": {
                "TableName": "table1",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/table1"
            }
        },
        {
            "Type": "AWS::DynamoDB::Table", 
            "Properties": {
                "TableName": "table2",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/table2"
            }
        }
    ]
    
    mock_table_batch2 = [
        {
            "Type": "AWS::DynamoDB::Table",
            "Properties": {
                "TableName": "table3",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/table3"
            }
        }
    ]

    with patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy") as mock_proxy_class:
        mock_proxy = AsyncMock()
        mock_paginator = AsyncMock()
        
        # Mock paginator to return two batches
        async def mock_paginate():
            yield ["table1", "table2"]
            yield ["table3"]
            
        mock_paginator.paginate.side_effect = mock_paginate
        mock_proxy.get_paginator.return_value = mock_paginator
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        
        with patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector") as mock_inspector_class:
            mock_inspector = AsyncMock()
            # First call returns first batch, second call returns second batch
            mock_inspector.inspect.side_effect = [mock_table_batch1, mock_table_batch2]
            mock_inspector_class.return_value = mock_inspector
            
            results = []
            async for batch in exporter.get_paginated_resources(options):
                results.extend(batch)
            
            assert len(results) == 3
            assert results[0]["Properties"]["TableName"] == "table1"
            assert results[1]["Properties"]["TableName"] == "table2"
            assert results[2]["Properties"]["TableName"] == "table3"
            
            # Verify paginator was called correctly
            mock_proxy.get_paginator.assert_called_once_with("list_tables", "TableNames")
            
            # Verify inspector was called twice (once for each batch)
            assert mock_inspector.inspect.call_count == 2


@pytest.mark.asyncio
async def test_get_paginated_resources_empty_results(exporter, mock_session):
    options = PaginatedTableRequest(
        region="us-east-1",
        account_id="123456789012", 
        include=[]
    )

    with patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy") as mock_proxy_class:
        mock_proxy = AsyncMock()
        mock_paginator = AsyncMock()
        
        # Mock paginator to return empty results
        async def mock_paginate():
            yield []
            
        mock_paginator.paginate.side_effect = mock_paginate
        mock_proxy.get_paginator.return_value = mock_paginator
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        
        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.extend(batch)
        
        assert len(results) == 0


def test_service_name_and_model(exporter):
    assert exporter._service_name == "dynamodb"
    assert exporter._model_cls.__name__ == "Table"