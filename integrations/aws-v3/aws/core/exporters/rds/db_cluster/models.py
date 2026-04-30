from typing import Optional, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class DbClusterProperties(BaseModel):
    ActivityStreamStatus: Optional[str] = Field(default=None)
    AssociatedRoles: list[dict[str, Any]] = Field(default_factory=list)
    AutoMinorVersionUpgrade: bool = Field(default=False)
    AvailabilityZones: list[str] = Field(default_factory=list)
    BackupRetentionPeriod: int = Field(default=0)
    ClusterCreateTime: Optional[datetime] = Field(default=None)
    CopyTagsToSnapshot: bool = Field(default=False)
    CrossAccountClone: bool = Field(default=False)
    DatabaseName: Optional[str] = Field(default=None)
    DBClusterArn: str = Field(default_factory=str)
    DBClusterIdentifier: str = Field(default_factory=str)
    DBClusterMembers: list[dict[str, Any]] = Field(default_factory=list)
    DbClusterResourceId: str = Field(default_factory=str)
    DeletionProtection: bool = Field(default=False)
    EarliestRestorableTime: Optional[datetime] = Field(default=None)
    Endpoint: Optional[str] = Field(default=None)
    Engine: str = Field(default_factory=str)
    EngineMode: Optional[str] = Field(default=None)
    EngineVersion: str = Field(default_factory=str)
    GlobalWriteForwardingStatus: Optional[str] = Field(default=None)
    HttpEndpointEnabled: bool = Field(default=False)
    IAMDatabaseAuthenticationEnabled: bool = Field(default=False)
    KmsKeyId: Optional[str] = Field(default=None)
    LatestRestorableTime: Optional[datetime] = Field(default=None)
    MasterUsername: str = Field(default_factory=str)
    MultiAZ: bool = Field(default=False)
    NetworkType: Optional[str] = Field(default=None)
    Port: int = Field(default=0)
    PreferredBackupWindow: str = Field(default_factory=str)
    PreferredMaintenanceWindow: str = Field(default_factory=str)
    ReaderEndpoint: Optional[str] = Field(default=None)
    Status: str = Field(default_factory=str)
    StorageEncrypted: bool = Field(default=False)
    StorageType: Optional[str] = Field(default=None)
    Tags: list[dict[str, Any]] = Field(default_factory=list)
    VpcSecurityGroups: list[dict[str, Any]] = Field(default_factory=list)
    DBSubnetGroup: Optional[str] = Field(default=None)

    class Config:
        extra = "ignore"


class DbCluster(ResourceModel[DbClusterProperties]):
    Type: str = "AWS::RDS::DBCluster"
    Properties: DbClusterProperties = Field(default_factory=DbClusterProperties)


class SingleDbClusterRequest(ResourceRequestModel):
    """Options for exporting a single RDS DB cluster."""

    db_cluster_identifier: str = Field(
        ..., description="The identifier of the RDS DB cluster to export"
    )


class PaginatedDbClusterRequest(ResourceRequestModel):
    """Options for exporting all RDS DB clusters in a region."""

    pass
