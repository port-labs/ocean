from typing import Any
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)
from datetime import datetime


class CacheClusterProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")
    CacheClusterId: str = Field(default_factory=str)
    ARN: str | None = Field(default=None)
    CacheNodeType: str | None = Field(default=None)
    Engine: str | None = Field(default=None)
    EngineVersion: str | None = Field(default=None)
    CacheClusterStatus: str | None = Field(default=None)
    NumCacheNodes: int | None = Field(default=None)
    PreferredAvailabilityZone: str | None = Field(default=None)
    PreferredOutpostArn: str | None = Field(default=None)
    CacheClusterCreateTime: datetime | None = Field(default=None)
    PreferredMaintenanceWindow: str | None = Field(default=None)
    PendingModifiedValues: dict[str, Any] | None = Field(default=None)
    NotificationConfiguration: dict[str, Any] | None = Field(default=None)
    CacheSecurityGroups: list[dict[str, Any]] | None = Field(default=None)
    CacheParameterGroup: dict[str, Any] | None = Field(default=None)
    CacheSubnetGroupName: str | None = Field(default=None)
    CacheNodes: list[dict[str, Any]] | None = Field(default=None)
    AutoMinorVersionUpgrade: bool | None = Field(default=None)
    SecurityGroups: list[dict[str, Any]] | None = Field(default=None)
    ReplicationGroupId: str | None = Field(default=None)
    SnapshotRetentionLimit: int | None = Field(default=None)
    SnapshotWindow: str | None = Field(default=None)
    AuthTokenEnabled: bool | None = Field(default=None)
    AuthTokenLastModifiedDate: datetime | None = Field(default=None)
    TransitEncryptionEnabled: bool | None = Field(default=None)
    AtRestEncryptionEnabled: bool | None = Field(default=None)
    ReplicationGroupLogDeliveryEnabled: bool | None = Field(default=None)
    LogDeliveryConfigurations: list[dict[str, Any]] | None = Field(default=None)
    NetworkType: str | None = Field(default=None)
    IpDiscovery: str | None = Field(default=None)
    TransitEncryptionMode: str | None = Field(default=None)
    ConfigurationEndpoint: dict[str, Any] | None = Field(default=None)
    ClientDownloadLandingPage: str | None = Field(default=None)
    TagList: list[dict[str, Any]] | None = Field(default=None)


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
