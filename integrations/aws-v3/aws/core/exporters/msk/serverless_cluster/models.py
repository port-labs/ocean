from typing import Optional, Any

from pydantic import ConfigDict, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel
from datetime import datetime


class MskServerlessClusterProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")

    activeOperationArn: Optional[str] = Field(default=None, alias="ActiveOperationArn")
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")
    clusterName: str = Field(default_factory=str, alias="ClusterName")
    clusterType: Optional[str] = Field(default=None, alias="ClusterType")
    creationTime: Optional[datetime] = Field(default=None, alias="CreationTime")
    currentVersion: Optional[str] = Field(default=None, alias="CurrentVersion")
    state: Optional[str] = Field(default=None, alias="State")
    stateInfo: Optional[dict[str, Any]] = Field(default=None, alias="StateInfo")
    tags: Optional[dict[str, str]] = Field(default=None, alias="Tags")
    serverless: Optional[dict[str, Any]] = Field(default=None, alias="Serverless")


class MskServerlessCluster(ResourceModel[MskServerlessClusterProperties]):
    Type: str = "AWS::MSK::ServerlessCluster"
    Properties: MskServerlessClusterProperties = Field(
        default_factory=MskServerlessClusterProperties
    )


class SingleMskServerlessClusterRequest(ResourceRequestModel):
    """Options for exporting a single MSK ServerlessCluster."""

    cluster_arn: str = Field(..., description="The ARN of the MSK serverless cluster")


class PaginatedMskServerlessClusterRequest(ResourceRequestModel):
    """Options for exporting all MSK ServerlessClusters in a region."""

    pass
