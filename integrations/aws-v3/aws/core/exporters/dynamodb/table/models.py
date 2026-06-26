from typing import Optional, Dict, Any, List
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class BillingModeSummary(BaseModel):
    BillingMode: Optional[str] = None
    LastUpdateToPayPerRequestDateTime: Optional[str] = None

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class ProvisionedThroughput(BaseModel):
    LastIncreaseDateTime: Optional[str] = None
    LastDecreaseDateTime: Optional[str] = None
    NumberOfDecreasesToday: Optional[int] = None
    ReadCapacityUnits: Optional[int] = None
    WriteCapacityUnits: Optional[int] = None

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class TableProperties(BaseModel):
    TableName: str = Field(default_factory=str)
    TableArn: Optional[str] = None
    TableId: Optional[str] = None
    TableStatus: Optional[str] = None
    TableSizeBytes: Optional[int] = None
    ItemCount: Optional[int] = None
    CreationDateTime: Optional[str] = None
    BillingModeSummary: Optional[BillingModeSummary] = None
    ProvisionedThroughput: Optional[ProvisionedThroughput] = None
    GlobalSecondaryIndexes: List[Dict[str, Any]] = Field(default_factory=list)
    LocalSecondaryIndexes: List[Dict[str, Any]] = Field(default_factory=list)
    KeySchema: List[Dict[str, Any]] = Field(default_factory=list)
    AttributeDefinitions: List[Dict[str, Any]] = Field(default_factory=list)
    StreamSpecification: Optional[Dict[str, Any]] = None
    LatestStreamLabel: Optional[str] = None
    LatestStreamArn: Optional[str] = None
    GlobalTableVersion: Optional[str] = None
    Replicas: List[Dict[str, Any]] = Field(default_factory=list)
    SSEDescription: Optional[Dict[str, Any]] = None
    DeletionProtectionEnabled: Optional[bool] = None
    Tags: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class DynamoDBTable(ResourceModel[TableProperties]):
    Type: str = "AWS::DynamoDB::Table"
    Properties: TableProperties = Field(default_factory=TableProperties)


class SingleDynamoDBTableRequest(ResourceRequestModel):
    """Options for exporting a single DynamoDB table."""

    table_name: str = Field(..., description="The name of the DynamoDB table to export")


class PaginatedDynamoDBTableRequest(ResourceRequestModel):
    """Options for exporting all DynamoDB tables in a region."""

    pass
