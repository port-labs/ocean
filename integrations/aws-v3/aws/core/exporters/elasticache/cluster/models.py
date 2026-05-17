from typing import Optional, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class CacheClusterProperties(BaseModel):
    CacheClusterId: str = Field(default_factory=str)
    ARN: Optional[str] = Field(default=None)
    CacheNodeType: Optional[str] = Field(default=None)
    Engine: Optional[str] = Field(default=None)
    EngineVersion: Optional[str] = Field(default=None)
    CacheClusterStatus: Optional[str] = Field(default=None)
    NumCacheNodes: Optional[int] = Field(default=None)
    PreferredAvailabilityZone: Optional[str] = Field(default=None)
    PreferredOutpostArn: Optional[str] = Field(default=None)
    CacheClusterCreateTime: Optional[datetime] = Field(default=None)
    PreferredMaintenanceWindow: Optional[str] = Field(default=None)
    PendingModifiedValues: Optional[dict[str, Any]] = Field(default=None)
    NotificationConfiguration: Optional[dict[str, Any]] = Field(default=None)
    CacheSecurityGroups: Optional[list[dict[str, Any]]] = Field(default=None)
    CacheParameterGroup: Optional[dict[str, Any]] = Field(default=None)
    CacheSubnetGroupName: Optional[str] = Field(default=None)
    CacheNodes: Optional[list[dict[str, Any]]] = Field(default=None)
    AutoMinorVersionUpgrade: Optional[bool] = Field(default=None)
    SecurityGroups: Optional[list[dict[str, Any]]] = Field(default=None)
    ReplicationGroupId: Optional[str] = Field(default=None)
    SnapshotRetentionLimit: Optional[int] = Field(default=None)
    SnapshotWindow: Optional[str] = Field(default=None)
    AuthTokenEnabled: Optional[bool] = Field(default=None)
    AuthTokenLastModifiedDate: Optional[datetime] = Field(default=None)
    TransitEncryptionEnabled: Optional[bool] = Field(default=None)
    AtRestEncryptionEnabled: Optional[bool] = Field(default=None)
    ReplicationGroupLogDeliveryEnabled: Optional[bool] = Field(default=None)
    LogDeliveryConfigurations: Optional[list[dict[str, Any]]] = Field(default=None)
    NetworkType: Optional[str] = Field(default=None)
    IpDiscovery: Optional[str] = Field(default=None)
    TransitEncryptionMode: Optional[str] = Field(default=None)
    ConfigurationEndpoint: Optional[dict[str, Any]] = Field(default=None)
    ClientDownloadLandingPage: Optional[str] = Field(default=None)
    TagList: Optional[list[dict[str, Any]]] = Field(default=None)

    class Config:
        allow_population_by_field_name = True
        extra = "allow"


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
