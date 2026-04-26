from typing import Optional, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class CacheClusterProperties(BaseModel):
    CacheClusterId: str = Field(default_factory=str)
    ARN: str = Field(default_factory=str)
    CacheNodeType: str = Field(default_factory=str)
    Engine: str = Field(default_factory=str)
    EngineVersion: str = Field(default_factory=str)
    CacheClusterStatus: str = Field(default_factory=str)
    NumCacheNodes: int = Field(default=0)
    PreferredAvailabilityZone: Optional[str] = Field(default=None)
    PreferredOutpostArn: Optional[str] = Field(default=None)
    CacheClusterCreateTime: Optional[datetime] = Field(default=None)
    PreferredMaintenanceWindow: str = Field(default_factory=str)
    PendingModifiedValues: dict[str, Any] = Field(default_factory=dict)
    NotificationConfiguration: Optional[dict[str, Any]] = Field(default=None)
    CacheSecurityGroups: list[dict[str, Any]] = Field(default_factory=list)
    CacheParameterGroup: Optional[dict[str, Any]] = Field(default=None)
    CacheSubnetGroupName: Optional[str] = Field(default=None)
    CacheNodes: list[dict[str, Any]] = Field(default_factory=list)
    AutoMinorVersionUpgrade: bool = Field(default=False)
    SecurityGroups: list[dict[str, Any]] = Field(default_factory=list)
    ReplicationGroupId: Optional[str] = Field(default=None)
    SnapshotRetentionLimit: int = Field(default=0)
    SnapshotWindow: Optional[str] = Field(default=None)
    AuthTokenEnabled: bool = Field(default=False)
    AuthTokenLastModifiedDate: Optional[datetime] = Field(default=None)
    TransitEncryptionEnabled: bool = Field(default=False)
    AtRestEncryptionEnabled: bool = Field(default=False)
    ReplicationGroupLogDeliveryEnabled: bool = Field(default=False)
    LogDeliveryConfigurations: list[dict[str, Any]] = Field(default_factory=list)
    NetworkType: Optional[str] = Field(default=None)
    IpDiscovery: Optional[str] = Field(default=None)
    TransitEncryptionMode: Optional[str] = Field(default=None)
    ConfigurationEndpoint: Optional[dict[str, Any]] = Field(default=None)
    ClientDownloadLandingPage: Optional[str] = Field(default=None)
    TagList: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        extra = "ignore"


class CacheCluster(ResourceModel[CacheClusterProperties]):
    Type: str = "AWS::ElastiCache::Cluster"
    Properties: CacheClusterProperties = Field(default_factory=CacheClusterProperties)


class SingleCacheClusterRequest(ResourceRequestModel):
    """Options for exporting a single ElastiCache cluster."""

    cache_cluster_id: str = Field(
        ..., description="The identifier of the ElastiCache cluster to export"
    )


class PaginatedCacheClusterRequest(ResourceRequestModel):
    """Options for exporting all ElastiCache clusters in a region."""

    pass
