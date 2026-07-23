from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)
from datetime import datetime


class EksClusterProperties(BaseAWSPropertiesModel):
    accessConfig: dict[str, Any] | None = Field(default=None, alias="AccessConfig")
    arn: str = Field(default_factory=str, alias="Arn")
    certificateAuthority: dict[str, Any] | None = Field(
        default=None, alias="CertificateAuthority"
    )
    computeConfig: dict[str, Any] | None = Field(default=None, alias="ComputeConfig")
    createdAt: datetime | None = Field(default=None, alias="CreatedAt")
    endpoint: str | None = Field(default=None, alias="Endpoint")
    identity: dict[str, Any] | None = Field(default=None, alias="Identity")
    kubernetesNetworkConfig: dict[str, Any] | None = Field(
        default=None, alias="KubernetesNetworkConfig"
    )
    logging: dict[str, Any] | None = Field(default=None, alias="Logging")
    name: str = Field(default_factory=str, alias="Name")
    platformVersion: str | None = Field(default=None, alias="PlatformVersion")
    resourcesVpcConfig: dict[str, Any] | None = Field(
        default=None, alias="ResourcesVpcConfig"
    )
    roleArn: str = Field(default_factory=str, alias="RoleArn")
    status: str = Field(default_factory=str, alias="Status")
    storageConfig: dict[str, Any] | None = Field(default=None, alias="StorageConfig")
    tags: dict[str, str] | None = Field(default=None, alias="Tags")
    upgradePolicy: dict[str, Any] | None = Field(default=None, alias="UpgradePolicy")
    version: str = Field(default_factory=str, alias="Version")
    zonalShiftConfig: dict[str, Any] | None = Field(
        default=None, alias="ZonalShiftConfig"
    )


class EksCluster(ResourceModel[EksClusterProperties]):
    Type: str = "AWS::EKS::Cluster"
    Properties: EksClusterProperties = Field(default_factory=EksClusterProperties)


class SingleEksClusterRequest(ResourceRequestModel):
    """Options for exporting a single EKS cluster."""

    cluster_name: str = Field(..., description="The name of the EKS cluster to export")


class PaginatedEksClusterRequest(ResourceRequestModel):
    """Options for exporting all EKS clusters in a region."""

    pass
