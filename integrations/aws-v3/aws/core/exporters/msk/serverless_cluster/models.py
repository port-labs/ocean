from typing import Any

from pydantic import ConfigDict, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel
from datetime import datetime


class MskServerlessClusterProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")

    activeOperationArn: str | None = Field(default=None, alias="ActiveOperationArn")
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")
    clusterName: str = Field(default_factory=str, alias="ClusterName")
    clusterType: str | None = Field(default=None, alias="ClusterType")
    creationTime: datetime | None = Field(default=None, alias="CreationTime")
    currentVersion: str | None = Field(default=None, alias="CurrentVersion")
    state: str | None = Field(default=None, alias="State")
    stateInfo: dict[str, Any] | None = Field(default=None, alias="StateInfo")
    tags: dict[str, str] | None = Field(default=None, alias="Tags")
    serverless: dict[str, Any] | None = Field(default=None, alias="Serverless")


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
