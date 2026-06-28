import pytest
from pydantic.v1 import ValidationError

from aws.core.exporters.dynamodb.table.models import (
    TableProperties,
    DynamoDBTable,
    SingleDynamoDBTableRequest,
    PaginatedDynamoDBTableRequest,
)


class TestSingleDynamoDBTableRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleDynamoDBTableRequest(
            region="us-west-2",
            account_id="123456789012",
            table_name="test-table",
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.table_name == "test-table"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["ListTagsOfResourceAction"]
        options = SingleDynamoDBTableRequest(
            region="eu-central-1",
            account_id="123456789012",
            table_name="test-table",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.table_name == "test-table"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleDynamoDBTableRequest(
                account_id="123456789012",
                table_name="test-table",
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_table_name(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleDynamoDBTableRequest(
                region="us-east-1",
                account_id="123456789012",
            )  # type: ignore
        assert "table_name" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        options = SingleDynamoDBTableRequest(
            region="us-east-1",
            account_id="123456789012",
            table_name="test-table",
            include=[],
        )
        assert options.include == []


class TestPaginatedDynamoDBTableRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedDynamoDBTableRequest inherits from the base class."""
        from aws.core.modeling.resource_models import ResourceRequestModel

        assert issubclass(PaginatedDynamoDBTableRequest, ResourceRequestModel)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedDynamoDBTableRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["ListTagsOfResourceAction"]
        options = PaginatedDynamoDBTableRequest(
            region="us-east-1",
            account_id="123456789012",
            include=include_list,
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == include_list


class TestTableProperties:

    def test_initialization_empty(self) -> None:
        """Test TableProperties with no arguments."""
        props = TableProperties()
        assert props.TableName == ""
        assert props.TableArn is None
        assert props.TableStatus is None
        assert props.ItemCount is None
        assert props.Tags == []
        assert props.GlobalSecondaryIndexes == []
        assert props.LocalSecondaryIndexes == []

    def test_initialization_with_properties(self) -> None:
        """Test TableProperties with specific values."""
        props = TableProperties(
            TableName="test-table",
            TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            TableId="abc-123",
            TableStatus="ACTIVE",
            TableSizeBytes=2048,
            ItemCount=100,
        )
        assert props.TableName == "test-table"
        assert (
            props.TableArn
            == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
        )
        assert props.TableId == "abc-123"
        assert props.TableStatus == "ACTIVE"
        assert props.TableSizeBytes == 2048
        assert props.ItemCount == 100

    def test_dict_exclude_none(self) -> None:
        """Test that dict() excludes None values."""
        props = TableProperties(
            TableName="test-table",
            TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
        )

        props_dict = props.dict(exclude_none=True)

        assert "TableStatus" not in props_dict
        assert "ItemCount" not in props_dict

        assert props_dict["TableName"] == "test-table"
        assert (
            props_dict["TableArn"]
            == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
        )

    def test_tags_default_is_empty_list(self) -> None:
        """Test that Tags defaults to an empty list."""
        props = TableProperties()
        assert props.Tags == []

    def test_with_tags(self) -> None:
        """Test TableProperties with tags."""
        props = TableProperties(
            TableName="test-table",
            Tags=[{"Key": "Environment", "Value": "Production"}],
        )
        assert len(props.Tags) == 1
        assert props.Tags[0]["Key"] == "Environment"
        assert props.Tags[0]["Value"] == "Production"


class TestDynamoDBTable:

    def test_type_is_fixed(self) -> None:
        """Test that the type field is fixed."""
        table = DynamoDBTable()
        assert table.Type == "AWS::DynamoDB::Table"

    def test_initialization_with_properties(self) -> None:
        """Test DynamoDBTable initialization with properties."""
        props = TableProperties(
            TableName="test-table",
            TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            TableStatus="ACTIVE",
        )
        table = DynamoDBTable(Properties=props)
        assert table.Type == "AWS::DynamoDB::Table"
        assert table.Properties.TableName == "test-table"
        assert table.Properties.TableStatus == "ACTIVE"

    def test_properties_default_factory(self) -> None:
        """Test that properties has a default factory."""
        table1 = DynamoDBTable()
        table2 = DynamoDBTable()

        # Properties should be different instances
        assert table1.Properties is not table2.Properties
