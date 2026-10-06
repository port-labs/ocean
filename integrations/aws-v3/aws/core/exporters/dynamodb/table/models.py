from datetime import datetime
from typing import Any

from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class TableProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")

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
    GlobalTableWitnesses: list[dict[str, Any]] | None = None
    GlobalTableSettingsReplicationMode: str | None = None
    OnDemandThroughput: dict[str, Any] | None = None
    WarmThroughput: dict[str, Any] | None = None
    MultiRegionConsistency: str | None = None
    Tags: list[dict[str, Any]] | None = None
    ContinuousBackupsDescription: dict[str, Any] | None = None


class Table(ResourceModel[TableProperties]):
    Type: str = "AWS::DynamoDB::Table"
    Properties: TableProperties = Field(default_factory=TableProperties)


class SingleTableRequest(ResourceRequestModel):
    table_name: str = Field(..., description="The name of the DynamoDB table to export")


class PaginatedTableRequest(ResourceRequestModel):
    pass
