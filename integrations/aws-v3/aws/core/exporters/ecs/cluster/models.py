from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
)


class ECSClusterProperties(BaseModel):
    """Properties for an ECS cluster resource."""

    clusterArn: str = Field(default_factory=str)
    clusterName: Optional[str] = None
    status: Optional[str] = None
    activeServicesCount: Optional[int] = None
    pendingTasksCount: Optional[int] = None
    runningTasksCount: Optional[int] = None
    registeredContainerInstancesCount: Optional[int] = None
    capacityProviders: Optional[List[str]] = None
    defaultCapacityProviderStrategy: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[Dict[str, Any]]] = None
    settings: Optional[List[Dict[str, Any]]] = None
    configurations: Optional[List[Dict[str, Any]]] = None
    statistics: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    attachmentsStatus: Optional[str] = None
    serviceConnectDefaults: Optional[Dict[str, Any]] = None
    pendingTaskArns: Optional[List[str]] = None

    class Config:
        extra = "forbid"


class ECSCluster(ResourceModel[ECSClusterProperties]):
    """ECS Cluster resource model using the generic ResourceModel pattern."""

    Type: str = "AWS::ECS::Cluster"
    Properties: ECSClusterProperties = Field(default_factory=ECSClusterProperties)
    # Metadata is inherited from ResourceModel base class


class SingleECSClusterRequest(ResourceRequestModel):
    """Options for exporting a single ECS cluster."""

    cluster_arn: str = Field(..., description="The ARN of the ECS cluster to export")


class PaginatedECSClusterRequest(ResourceRequestModel):
    """Options for exporting paginated ECS clusters."""
