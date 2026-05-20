from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class MskClusterProperties(BaseModel):
    """Properties for an MSK cluster resource."""

    ClusterArn: str = Field(default_factory=str)
    ClusterName: str = Field(default_factory=str)
    State: Optional[str] = None
    CreationTime: Optional[datetime] = None
    CurrentVersion: Optional[str] = None

    BrokerNodeGroupInfo: Optional[Dict[str, Any]] = None
    ClientAuthentication: Optional[Dict[str, Any]] = None
    EncryptionInfo: Optional[Dict[str, Any]] = None
    CurrentBrokerSoftwareInfo: Optional[Dict[str, Any]] = None
    LoggingInfo: Optional[Dict[str, Any]] = None
    OpenMonitoring: Optional[Dict[str, Any]] = None

    NumberOfBrokerNodes: Optional[int] = None
    EnhancedMonitoring: Optional[str] = None
    StorageMode: Optional[str] = None

    ZookeeperConnectString: Optional[str] = None
    ZookeeperConnectStringTls: Optional[str] = None

    Tags: Dict[str, str] = Field(default_factory=dict)

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
