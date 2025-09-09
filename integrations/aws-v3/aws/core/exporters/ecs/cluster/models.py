from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ClusterProperties(BaseModel):
    clusterName: str = Field(default_factory=str, alias="ClusterName")
    capacityProviders: List[str] = Field(
        default_factory=list, alias="CapacityProviders"
    )
    clusterSettings: List[Dict[str, Any]] = Field(
        default_factory=list, alias="ClusterSettings"
    )
    configuration: Optional[Dict[str, Any]] = Field(default=None, alias="Configuration")
    defaultCapacityProviderStrategy: List[Dict[str, Any]] = Field(
        default_factory=list, alias="DefaultCapacityProviderStrategy"
    )
    serviceConnectDefaults: Optional[Dict[str, Any]] = Field(
        default=None, alias="ServiceConnectDefaults"
    )
    tags: List[Dict[str, Any]] = Field(default_factory=list, alias="Tags")

    attachments: List[Dict[str, Any]] = Field(default_factory=list, alias="Attachments")
    attachmentsStatus: Optional[str] = Field(default=None, alias="AttachmentsStatus")
    statistics: List[Dict[str, Any]] = Field(default_factory=list, alias="Statistics")
    status: Optional[str] = Field(default=None, alias="Status")
    runningTasksCount: Optional[int] = Field(default=None, alias="RunningTasksCount")
    activeServicesCount: Optional[int] = Field(
        default=None, alias="ActiveServicesCount"
    )
    pendingTasksCount: Optional[int] = Field(default=None, alias="PendingTasksCount")
    registeredContainerInstancesCount: Optional[int] = Field(
        default=None, alias="RegisteredContainerInstancesCount"
    )
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")
    settings: List[Dict[str, Any]] = Field(default_factory=list, alias="Settings")

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class Cluster(ResourceModel[ClusterProperties]):
    Type: str = "AWS::ECS::Cluster"
    Properties: ClusterProperties = Field(default_factory=ClusterProperties)


class SingleClusterRequest(ResourceRequestModel):
    """Options for exporting a single ECS cluster."""

    cluster_name: str = Field(..., description="The name of the ECS cluster to export")


class PaginatedClusterRequest(ResourceRequestModel):
    """Options for exporting all ECS clusters in a region."""

    pass
