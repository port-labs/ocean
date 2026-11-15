from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)
from datetime import datetime


class EksNodegroupProperties(BaseAWSPropertiesModel):
    nodegroupName: str = Field(default_factory=str, alias="NodegroupName")
    nodegroupArn: str = Field(default_factory=str, alias="NodegroupArn")
    clusterName: str = Field(default_factory=str, alias="ClusterName")
    status: str | None = Field(default=None, alias="Status")
    capacityType: str | None = Field(default=None, alias="CapacityType")
    scalingConfig: dict[str, Any] | None = Field(default=None, alias="ScalingConfig")
    instanceTypes: list[str] | None = Field(default=None, alias="InstanceTypes")
    subnets: list[str] | None = Field(default=None, alias="Subnets")
    amiType: str | None = Field(default=None, alias="AmiType")
    nodeRole: str | None = Field(default=None, alias="NodeRole")
    labels: dict[str, str] | None = Field(default=None, alias="Labels")
    taints: list[dict[str, Any]] | None = Field(default=None, alias="Taints")
    resources: dict[str, Any] | None = Field(default=None, alias="Resources")
    diskSize: int | None = Field(default=None, alias="DiskSize")
    health: dict[str, Any] | None = Field(default=None, alias="Health")
    updateConfig: dict[str, Any] | None = Field(default=None, alias="UpdateConfig")
    launchTemplate: dict[str, Any] | None = Field(default=None, alias="LaunchTemplate")
    createdAt: datetime | None = Field(default=None, alias="CreatedAt")
    modifiedAt: datetime | None = Field(default=None, alias="ModifiedAt")
    releaseVersion: str | None = Field(default=None, alias="ReleaseVersion")
    version: str | None = Field(default=None, alias="Version")
    tags: dict[str, str] | None = Field(default=None, alias="Tags")


class EksNodegroup(ResourceModel[EksNodegroupProperties]):
    Type: str = "AWS::EKS::Nodegroup"
    Properties: EksNodegroupProperties = Field(
        default_factory=EksNodegroupProperties
    )


class SingleEksNodegroupRequest(ResourceRequestModel):
    """Options for exporting a single EKS nodegroup."""

    cluster_name: str = Field(
        ..., description="The name of the EKS cluster containing the nodegroup"
    )
    nodegroup_name: str = Field(
        ..., description="The name of the EKS nodegroup to export"
    )


class PaginatedEksNodegroupRequest(ResourceRequestModel):
    """Options for exporting all EKS nodegroups in a region."""

    pass
