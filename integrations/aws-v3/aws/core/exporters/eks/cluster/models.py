from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class EksClusterProperties(BaseModel):
    accessConfig: Optional[Dict[str, Any]] = Field(default=None, alias="AccessConfig")
    arn: str = Field(default_factory=str, alias="Arn")
    certificateAuthority: Optional[Dict[str, Any]] = Field(
        default=None, alias="CertificateAuthority"
    )
    computeConfig: Optional[Dict[str, Any]] = Field(default=None, alias="ComputeConfig")
    createdAt: Optional[datetime] = Field(default=None, alias="CreatedAt")
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    identity: Optional[Dict[str, Any]] = Field(default=None, alias="Identity")
    kubernetesNetworkConfig: Optional[Dict[str, Any]] = Field(
        default=None, alias="KubernetesNetworkConfig"
    )
    logging: Optional[Dict[str, Any]] = Field(default=None, alias="Logging")
    name: str = Field(default_factory=str, alias="Name")
    platformVersion: Optional[str] = Field(default=None, alias="PlatformVersion")
    resourcesVpcConfig: Optional[Dict[str, Any]] = Field(
        default=None, alias="ResourcesVpcConfig"
    )
    roleArn: str = Field(default_factory=str, alias="RoleArn")
    status: str = Field(default_factory=str, alias="Status")
    storageConfig: Optional[Dict[str, Any]] = Field(default=None, alias="StorageConfig")
    tags: Optional[Dict[str, str]] = Field(default=None, alias="Tags")
    upgradePolicy: Optional[Dict[str, Any]] = Field(default=None, alias="UpgradePolicy")
    version: str = Field(default_factory=str, alias="Version")
    zonalShiftConfig: Optional[Dict[str, Any]] = Field(
        default=None, alias="ZonalShiftConfig"
    )

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class EksCluster(ResourceModel[EksClusterProperties]):
    Type: str = "AWS::EKS::Cluster"
    Properties: EksClusterProperties = Field(default_factory=EksClusterProperties)


class SingleEksClusterRequest(ResourceRequestModel):
    """Options for exporting a single EKS cluster."""

    cluster_name: str = Field(..., description="The name of the EKS cluster to export")


class PaginatedEksClusterRequest(ResourceRequestModel):
    """Options for exporting all EKS clusters in a region."""

    pass
