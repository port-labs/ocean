from typing import Any
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class DbInstanceProperties(BaseModel):
    AllocatedStorage: int = Field(default=0)
    AutoMinorVersionUpgrade: bool = Field(default=False)
    AvailabilityZone: str = Field(default_factory=str)
    BackupRetentionPeriod: int = Field(default=0)
    CACertificateIdentifier: str = Field(default_factory=str)
    CharacterSetName: str | None = Field(default=None)
    CopyTagsToSnapshot: bool = Field(default=False)
    DBInstanceArn: str = Field(default_factory=str)
    DBInstanceClass: str = Field(default_factory=str)
    DBInstanceIdentifier: str = Field(default_factory=str)
    DbInstancePort: int = Field(default=0, alias="Port")
    DBInstanceStatus: str = Field(default_factory=str)
    DBName: str | None = Field(default=None)
    DBParameterGroups: list[dict[str, Any]] = Field(default_factory=list)
    DBSecurityGroups: list[dict[str, Any]] = Field(default_factory=list)
    DBSubnetGroup: dict[str, Any] | None = Field(default=None)
    DbiResourceId: str = Field(default_factory=str)
    DomainMemberships: list[dict[str, Any]] = Field(default_factory=list)
    IAMDatabaseAuthenticationEnabled: bool = Field(
        default=False, alias="EnableIAMDatabaseAuthentication"
    )
    PerformanceInsightsEnabled: bool = Field(
        default=False, alias="EnablePerformanceInsights"
    )
    Endpoint: dict[str, Any] | None = Field(default=None)
    Engine: str = Field(default_factory=str)
    EngineVersion: str = Field(default_factory=str)
    EnhancedMonitoringResourceArn: str | None = Field(default=None)
    InstanceCreateTime: datetime | None = Field(default=None)
    Iops: int | None = Field(default=None)
    KmsKeyId: str | None = Field(default=None)
    LatestRestorableTime: datetime | None = Field(default=None)
    LicenseModel: str = Field(default_factory=str)
    MasterUsername: str = Field(default_factory=str)
    MonitoringInterval: int = Field(default=0)
    MonitoringRoleArn: str | None = Field(default=None)
    MultiAZ: bool = Field(default=False)
    OptionGroupMemberships: list[dict[str, Any]] = Field(default_factory=list)
    PendingModifiedValues: dict[str, Any] = Field(default_factory=dict)
    PreferredBackupWindow: str = Field(default_factory=str)
    PreferredMaintenanceWindow: str = Field(default_factory=str)
    PubliclyAccessible: bool = Field(default=False)
    ReadReplicaDBInstanceIdentifiers: list[str] = Field(default_factory=list)
    SecondaryAvailabilityZone: str | None = Field(default=None)
    StorageEncrypted: bool = Field(default=False)
    StorageType: str = Field(default_factory=str)
    Tags: list[dict[str, Any]] = Field(default_factory=list)
    VpcSecurityGroups: list[dict[str, Any]] = Field(
        default_factory=list, alias="VPCSecurityGroups"
    )
    DatabaseInsightsMode: str | None = Field(default=None)
    DeletionProtection: bool = Field(default=False)
    AssociatedRoles: list[dict[str, Any]] = Field(default_factory=list)
    CustomerOwnedIpEnabled: bool = Field(default=False)
    ActivityStreamStatus: str | None = Field(default=None)
    BackupTarget: str | None = Field(default=None)
    NetworkType: str | None = Field(default=None)
    StorageThroughput: int | None = Field(default=None)
    CertificateDetails: dict[str, Any] | None = Field(default=None)
    DedicatedLogVolume: bool = Field(default=False)
    IsStorageConfigUpgradeAvailable: bool = Field(default=False)
    EngineLifecycleSupport: str | None = Field(default=None)

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class DbInstance(ResourceModel[DbInstanceProperties]):
    Type: str = "AWS::RDS::DBInstance"
    Properties: DbInstanceProperties = Field(default_factory=DbInstanceProperties)


class SingleDbInstanceRequest(ResourceRequestModel):
    """Options for exporting a single RDS DB instance."""

    db_instance_identifier: str = Field(
        ..., description="The identifier of the RDS DB instance to export"
    )


class PaginatedDbInstanceRequest(ResourceRequestModel):
    """Options for exporting all RDS DB instances in a region."""

    pass
