from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class DbInstanceProperties(BaseModel):
    # Core identifiers
    dbInstanceIdentifier: str = Field(default_factory=str, alias="DBInstanceIdentifier")
    dbInstanceArn: str = Field(default_factory=str, alias="DBInstanceArn")
    dbiResourceId: str = Field(default_factory=str, alias="DbiResourceId")
    
    # Instance configuration
    dbInstanceClass: str = Field(default_factory=str, alias="DBInstanceClass")
    engine: str = Field(default_factory=str, alias="Engine")
    engineVersion: str = Field(default_factory=str, alias="EngineVersion")
    dbInstanceStatus: str = Field(default_factory=str, alias="DBInstanceStatus")
    
    # Storage configuration
    allocatedStorage: int = Field(default=0, alias="AllocatedStorage")
    storageType: str = Field(default_factory=str, alias="StorageType")
    iops: Optional[int] = Field(default=None, alias="Iops")
    storageEncrypted: bool = Field(default=False, alias="StorageEncrypted")
    kmsKeyId: Optional[str] = Field(default=None, alias="KmsKeyId")
    
    # Network configuration
    endpoint: Optional[Dict[str, Any]] = Field(default=None, alias="Endpoint")
    publiclyAccessible: bool = Field(default=False, alias="PubliclyAccessible")
    availabilityZone: str = Field(default_factory=str, alias="AvailabilityZone")
    secondaryAvailabilityZone: Optional[str] = Field(default=None, alias="SecondaryAvailabilityZone")
    multiAZ: bool = Field(default=False, alias="MultiAZ")
    
    # Security configuration
    vpcSecurityGroups: List[Dict[str, Any]] = Field(default_factory=list, alias="VpcSecurityGroups")
    dbSubnetGroup: Optional[Dict[str, Any]] = Field(default=None, alias="DBSubnetGroup")
    iamDatabaseAuthenticationEnabled: bool = Field(default=False, alias="IAMDatabaseAuthenticationEnabled")
    
    # Backup configuration
    backupRetentionPeriod: int = Field(default=0, alias="BackupRetentionPeriod")
    preferredBackupWindow: str = Field(default_factory=str, alias="PreferredBackupWindow")
    preferredMaintenanceWindow: str = Field(default_factory=str, alias="PreferredMaintenanceWindow")
    copyTagsToSnapshot: bool = Field(default=False, alias="CopyTagsToSnapshot")
    
    # Monitoring configuration
    monitoringInterval: int = Field(default=0, alias="MonitoringInterval")
    monitoringRoleArn: Optional[str] = Field(default=None, alias="MonitoringRoleArn")
    enhancedMonitoringResourceArn: Optional[str] = Field(default=None, alias="EnhancedMonitoringResourceArn")
    performanceInsightsEnabled: bool = Field(default=False, alias="PerformanceInsightsEnabled")
    
    # Database configuration
    masterUsername: str = Field(default_factory=str, alias="MasterUsername")
    dbName: Optional[str] = Field(default=None, alias="DBName")
    characterSetName: Optional[str] = Field(default=None, alias="CharacterSetName")
    licenseModel: str = Field(default_factory=str, alias="LicenseModel")
    
    # Parameter and option groups
    dbParameterGroups: List[Dict[str, Any]] = Field(default_factory=list, alias="DBParameterGroups")
    optionGroupMemberships: List[Dict[str, Any]] = Field(default_factory=list, alias="OptionGroupMemberships")
    
    # Replication configuration
    readReplicaDBInstanceIdentifiers: List[str] = Field(default_factory=list, alias="ReadReplicaDBInstanceIdentifiers")
    
    # Time information
    instanceCreateTime: Optional[datetime] = Field(default=None, alias="InstanceCreateTime")
    latestRestorableTime: Optional[datetime] = Field(default=None, alias="LatestRestorableTime")
    
    # Additional configuration
    autoMinorVersionUpgrade: bool = Field(default=False, alias="AutoMinorVersionUpgrade")
    caCertificateIdentifier: str = Field(default_factory=str, alias="CACertificateIdentifier")
    dbInstancePort: int = Field(default=0, alias="DbInstancePort")
    domainMemberships: List[Dict[str, Any]] = Field(default_factory=list, alias="DomainMemberships")
    pendingModifiedValues: Dict[str, Any] = Field(default_factory=dict, alias="PendingModifiedValues")
    
    # Tags
    tags: List[Dict[str, Any]] = Field(default_factory=list, alias="Tags")

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class DbInstance(ResourceModel[DbInstanceProperties]):
    Type: str = "AWS::RDS::DBInstance"
    Properties: DbInstanceProperties = Field(default_factory=DbInstanceProperties)


class SingleDbInstanceRequest(ResourceRequestModel):
    """Options for exporting a single RDS DB instance."""

    db_instance_identifier: str = Field(..., description="The identifier of the RDS DB instance to export")


class PaginatedDbInstanceRequest(ResourceRequestModel):
    """Options for exporting all RDS DB instances in a region."""

    pass
