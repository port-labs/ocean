from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class ClusterProperties(BaseAWSPropertiesModel):
    clusterName: str = Field(default_factory=str, alias="ClusterName")
    capacityProviders: list[str] = Field(
        default_factory=list, alias="CapacityProviders"
    )
    settings: list[dict[str, Any]] = Field(
        default_factory=list, alias="ClusterSettings"
    )
    configuration: dict[str, Any] | None = Field(default=None, alias="Configuration")
    defaultCapacityProviderStrategy: list[dict[str, Any]] = Field(
        default_factory=list, alias="DefaultCapacityProviderStrategy"
    )
    serviceConnectDefaults: dict[str, Any] | None = Field(
        default=None, alias="ServiceConnectDefaults"
    )
    tags: list[dict[str, Any]] = Field(default_factory=list, alias="Tags")

    attachments: list[dict[str, Any]] = Field(default_factory=list, alias="Attachments")
    attachmentsStatus: str | None = Field(default=None, alias="AttachmentsStatus")
    statistics: list[dict[str, Any]] = Field(default_factory=list, alias="Statistics")
    status: str | None = Field(default=None, alias="Status")
    runningTasksCount: int | None = Field(default=None, alias="RunningTasksCount")
    activeServicesCount: int | None = Field(default=None, alias="ActiveServicesCount")
    pendingTasksCount: int | None = Field(default=None, alias="PendingTasksCount")
    registeredContainerInstancesCount: int | None = Field(
        default=None, alias="RegisteredContainerInstancesCount"
    )
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")


class Cluster(ResourceModel[ClusterProperties]):
    Type: str = "AWS::ECS::Cluster"
    Properties: ClusterProperties = Field(default_factory=ClusterProperties)


class SingleClusterRequest(ResourceRequestModel):
    """Options for exporting a single ECS cluster."""

    cluster_name: str = Field(..., description="The name of the ECS cluster to export")


class PaginatedClusterRequest(ResourceRequestModel):
    """Options for exporting all ECS clusters in a region."""

    pass
