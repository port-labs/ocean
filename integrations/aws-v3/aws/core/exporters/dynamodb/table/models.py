from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class TableProperties(BaseModel):
    TableName: str = Field(default_factory=str)
    TableArn: str = Field(default_factory=str)
    TableId: str = Field(default_factory=str)
    TableStatus: str = Field(default_factory=str)
    CreationDateTime: Optional[datetime] = None
    AttributeDefinitions: List[Dict[str, Any]] = Field(default_factory=list)
    KeySchema: List[Dict[str, Any]] = Field(default_factory=list)
    BillingModeSummary: Optional[Dict[str, Any]] = None
    ProvisionedThroughput: Optional[Dict[str, Any]] = None
    TableSizeBytes: Optional[int] = None
    ItemCount: Optional[int] = None
    Tags: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Optional fields for advanced configurations
    GlobalSecondaryIndexes: Optional[List[Dict[str, Any]]] = None
    LocalSecondaryIndexes: Optional[List[Dict[str, Any]]] = None
    StreamSpecification: Optional[Dict[str, Any]] = None
    LatestStreamLabel: Optional[str] = None
    LatestStreamArn: Optional[str] = None
    RestoreSummary: Optional[Dict[str, Any]] = None
    SSEDescription: Optional[Dict[str, Any]] = None
    ArchivalSummary: Optional[Dict[str, Any]] = None
    DeletionProtectionEnabled: Optional[bool] = None
    PointInTimeRecoveryDescription: Optional[Dict[str, Any]] = None
    ContinuousBackupsDescription: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "forbid"
        populate_by_name = True


class Table(ResourceModel[TableProperties]):
    Type: str = "AWS::DynamoDB::Table"
    Properties: TableProperties = Field(default_factory=TableProperties)


class SingleTableRequest(ResourceRequestModel):
    """Options for exporting a single DynamoDB table."""
    
    table_name: str = Field(..., description="The name of the DynamoDB table to export")


class PaginatedTableRequest(ResourceRequestModel):
    """Options for exporting all DynamoDB tables in a region."""
    pass