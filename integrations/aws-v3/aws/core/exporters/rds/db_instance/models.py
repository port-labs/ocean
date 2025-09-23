from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class DbInstanceProperties(BaseModel):
    AllocatedStorage: int = Field(default=0)
    AutoMinorVersionUpgrade: bool = Field(default=False)
    AvailabilityZone: str = Field(default_factory=str)
    BackupRetentionPeriod: int = Field(default=0)
    CACertificateIdentifier: str = Field(default_factory=str)
    CharacterSetName: Optional[str] = Field(default=None)
    CopyTagsToSnapshot: bool = Field(default=False)
    DBInstanceArn: str = Field(default_factory=str)
    DBInstanceClass: str = Field(default_factory=str)
    DBInstanceIdentifier: str = Field(default_factory=str)
    DbInstancePort: int = Field(default=0, alias="Port")
    DBInstanceStatus: str = Field(default_factory=str)
    DBName: Optional[str] = Field(default=None)
    DBParameterGroups: List[Dict[str, Any]] = Field(default_factory=list)
    DBSecurityGroups: List[Dict[str, Any]] = Field(default_factory=list)
    DBSubnetGroup: Optional[Dict[str, Any]] = Field(default=None)
    DbiResourceId: str = Field(default_factory=str)
    DomainMemberships: List[Dict[str, Any]] = Field(default_factory=list)
    IAMDatabaseAuthenticationEnabled: bool = Field(default=False, alias="EnableIAMDatabaseAuthentication")
    PerformanceInsightsEnabled: bool = Field(default=False, alias="EnablePerformanceInsights")
    Endpoint: Optional[Dict[str, Any]] = Field(default=None)
    Engine: str = Field(default_factory=str)
    EngineVersion: str = Field(default_factory=str)
    EnhancedMonitoringResourceArn: Optional[str] = Field(default=None)
    InstanceCreateTime: Optional[datetime] = Field(default=None)
    Iops: Optional[int] = Field(default=None)
    KmsKeyId: Optional[str] = Field(default=None)
    LatestRestorableTime: Optional[datetime] = Field(default=None)
    LicenseModel: str = Field(default_factory=str)
    MasterUsername: str = Field(default_factory=str)
    MonitoringInterval: int = Field(default=0)
    MonitoringRoleArn: Optional[str] = Field(default=None)
    MultiAZ: bool = Field(default=False)
    OptionGroupMemberships: List[Dict[str, Any]] = Field(default_factory=list)
    PendingModifiedValues: Dict[str, Any] = Field(default_factory=dict)
    PreferredBackupWindow: str = Field(default_factory=str)
    PreferredMaintenanceWindow: str = Field(default_factory=str)
    PubliclyAccessible: bool = Field(default=False)
    ReadReplicaDBInstanceIdentifiers: List[str] = Field(default_factory=list)
    SecondaryAvailabilityZone: Optional[str] = Field(default=None)
    StorageEncrypted: bool = Field(default=False)
    StorageType: str = Field(default_factory=str)
    Tags: List[Dict[str, Any]] = Field(default_factory=list)
    VpcSecurityGroups: List[Dict[str, Any]] = Field(default_factory=list, alias="VPCSecurityGroups")
    DatabaseInsightsMode: Optional[str] = Field(default=None)
    DeletionProtection: bool = Field(default=False)
    AssociatedRoles: List[Dict[str, Any]] = Field(default_factory=list)
    CustomerOwnedIpEnabled: bool = Field(default=False)
    ActivityStreamStatus: Optional[str] = Field(default=None)
    BackupTarget: Optional[str] = Field(default=None)
    NetworkType: Optional[str] = Field(default=None)
    StorageThroughput: Optional[int] = Field(default=None)
    CertificateDetails: Optional[Dict[str, Any]] = Field(default=None)
    DedicatedLogVolume: bool = Field(default=False)
    IsStorageConfigUpgradeAvailable: bool = Field(default=False)
    EngineLifecycleSupport: Optional[str] = Field(default=None)

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
