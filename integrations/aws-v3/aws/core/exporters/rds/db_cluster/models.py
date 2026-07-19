from typing import Any
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel
from datetime import datetime


class DbClusterProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")

    ActivityStreamStatus: str | None = Field(default=None)
    AssociatedRoles: list[dict[str, Any]] = Field(default_factory=list)
    AutoMinorVersionUpgrade: bool = Field(default=False)
    AvailabilityZones: list[str] = Field(default_factory=list)
    BackupRetentionPeriod: int = Field(default=0)
    ClusterCreateTime: datetime | None = Field(default=None)
    CopyTagsToSnapshot: bool = Field(default=False)
    CrossAccountClone: bool = Field(default=False)
    DatabaseName: str | None = Field(default=None)
    DBClusterArn: str = Field(default_factory=str)
    DBClusterIdentifier: str = Field(default_factory=str)
    DBClusterMembers: list[dict[str, Any]] = Field(default_factory=list)
    DbClusterResourceId: str = Field(default_factory=str)
    DeletionProtection: bool = Field(default=False)
    EarliestRestorableTime: datetime | None = Field(default=None)
    Endpoint: str | None = Field(default=None)
    Engine: str = Field(default_factory=str)
    EngineMode: str | None = Field(default=None)
    EngineVersion: str = Field(default_factory=str)
    GlobalWriteForwardingStatus: str | None = Field(default=None)
    HttpEndpointEnabled: bool = Field(default=False)
    IAMDatabaseAuthenticationEnabled: bool = Field(default=False)
    KmsKeyId: str | None = Field(default=None)
    LatestRestorableTime: datetime | None = Field(default=None)
    MasterUsername: str = Field(default_factory=str)
    MultiAZ: bool = Field(default=False)
    NetworkType: str | None = Field(default=None)
    Port: int = Field(default=0)
    PreferredBackupWindow: str = Field(default_factory=str)
    PreferredMaintenanceWindow: str = Field(default_factory=str)
    ReaderEndpoint: str | None = Field(default=None)
    Status: str = Field(default_factory=str)
    StorageEncrypted: bool = Field(default=False)
    StorageType: str | None = Field(default=None)
    Tags: list[dict[str, Any]] = Field(default_factory=list)
    VpcSecurityGroups: list[dict[str, Any]] = Field(default_factory=list)
    DBSubnetGroup: str | None = Field(default=None)


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
