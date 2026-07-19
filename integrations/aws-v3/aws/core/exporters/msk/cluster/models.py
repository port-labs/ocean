from typing import Any
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class MskClusterProperties(BaseModel):
    """Properties for an MSK cluster resource."""

    ClusterArn: str = Field(default_factory=str)
    ClusterName: str = Field(default_factory=str)
    State: str | None = None
    CreationTime: datetime | None = None
    CurrentVersion: str | None = None

    BrokerNodeGroupInfo: dict[str, Any] | None = None
    ClientAuthentication: dict[str, Any] | None = None
    EncryptionInfo: dict[str, Any] | None = None
    CurrentBrokerSoftwareInfo: dict[str, Any] | None = None
    LoggingInfo: dict[str, Any] | None = None
    OpenMonitoring: dict[str, Any] | None = None

    NumberOfBrokerNodes: int | None = None
    EnhancedMonitoring: str | None = None
    StorageMode: str | None = None

    ZookeeperConnectString: str | None = None
    ZookeeperConnectStringTls: str | None = None

    Tags: dict[str, str] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class MskCluster(ResourceModel[MskClusterProperties]):
    """MSK cluster resource model."""

    Type: str = "AWS::MSK::Cluster"
    Properties: MskClusterProperties = Field(default_factory=MskClusterProperties)


class SingleMskClusterRequest(ResourceRequestModel):
    """Options for exporting a single MSK cluster."""

    cluster_arn: str = Field(..., description="The ARN of the MSK cluster to export")


class PaginatedMskClusterRequest(ResourceRequestModel):
    """Options for exporting all MSK clusters in a region."""

    pass
