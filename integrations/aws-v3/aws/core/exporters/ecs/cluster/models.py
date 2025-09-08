from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ClusterProperties(BaseModel):
    ClusterName: str = Field(default_factory=str)
    CapacityProviders: List[str] = Field(default_factory=list)
    ClusterSettings: List[Dict[str, Any]] = Field(default_factory=list)
    Configuration: Optional[Dict[str, Any]] = None
    DefaultCapacityProviderStrategy: List[Dict[str, Any]] = Field(default_factory=list)
    ServiceConnectDefaults: Optional[Dict[str, Any]] = None
    Tags: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Additional runtime properties (not in CloudFormation but useful for Port)
    Status: Optional[str] = None
    RunningTasksCount: Optional[int] = None
    ActiveServicesCount: Optional[int] = None
    PendingTasksCount: Optional[int] = None
    RegisteredContainerInstancesCount: Optional[int] = None
    Arn: str = Field(default_factory=str)

    class Config:
        extra = "forbid"
        populate_by_name = True


class Cluster(ResourceModel[ClusterProperties]):
    Type: str = "AWS::ECS::Cluster"
    Properties: ClusterProperties = Field(default_factory=ClusterProperties)


class SingleClusterRequest(ResourceRequestModel):
    """Options for exporting a single ECS cluster."""

    cluster_name: str = Field(..., description="The name of the ECS cluster to export")


class PaginatedClusterRequest(ResourceRequestModel):
    """Options for exporting all ECS clusters in a region."""
    pass
