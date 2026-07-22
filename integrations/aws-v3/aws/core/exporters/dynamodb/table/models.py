from datetime import datetime
from typing import Any
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class TableProperties(BaseModel):
    TableName: str = Field(default_factory=str)
    TableArn: str | None = None
    TableId: str | None = None
    TableStatus: str | None = None
    CreationDateTime: datetime | None = None
    ProvisionedThroughput: dict[str, Any] | None = None
    TableSizeBytes: int | None = None
    ItemCount: int | None = None
    BillingModeSummary: dict[str, Any] | None = None
    KeySchema: list[dict[str, Any]] | None = None
    AttributeDefinitions: list[dict[str, Any]] | None = None
    GlobalSecondaryIndexes: list[dict[str, Any]] | None = None
    LocalSecondaryIndexes: list[dict[str, Any]] | None = None
    StreamSpecification: dict[str, Any] | None = None
    LatestStreamArn: str | None = None
    LatestStreamLabel: str | None = None
    SSEDescription: dict[str, Any] | None = None
    RestoreSummary: dict[str, Any] | None = None
    ArchivalSummary: dict[str, Any] | None = None
    TableClassSummary: dict[str, Any] | None = None
    DeletionProtectionEnabled: bool | None = None
    Replicas: list[dict[str, Any]] | None = None
    GlobalTableVersion: str | None = None
    Tags: list[dict[str, Any]] | None = None
    ContinuousBackupsDescription: dict[str, Any] | None = None

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class Table(ResourceModel[TableProperties]):
    Type: str = "AWS::DynamoDB::Table"
    Properties: TableProperties = Field(default_factory=TableProperties)


class SingleTableRequest(ResourceRequestModel):
    table_name: str = Field(..., description="The name of the DynamoDB table to export")


class PaginatedTableRequest(ResourceRequestModel):
    pass
