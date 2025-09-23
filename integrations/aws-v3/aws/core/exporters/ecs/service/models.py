from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class ServiceProperties(BaseModel):
    serviceName: str = Field(default_factory=str, alias="ServiceName")
    serviceArn: str = Field(default_factory=str, alias="ServiceArn")
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")
    taskDefinition: str = Field(default_factory=str, alias="TaskDefinition")
    desiredCount: int = Field(default=0, alias="DesiredCount")
    runningCount: int = Field(default=0, alias="RunningCount")
    pendingCount: int = Field(default=0, alias="PendingCount")
    launchType: Optional[str] = Field(default=None, alias="LaunchType")
    schedulingStrategy: Optional[str] = Field(default=None, alias="SchedulingStrategy")
    status: Optional[str] = Field(default=None, alias="Status")
    deploymentConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentConfiguration"
    )
    deploymentController: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentController"
    )
    deployments: List[Dict[str, Any]] = Field(default_factory=list, alias="Deployments")
    events: List[Dict[str, Any]] = Field(default_factory=list, alias="Events")
    networkConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="NetworkConfiguration"
    )
    loadBalancers: List[Dict[str, Any]] = Field(
        default_factory=list, alias="LoadBalancers"
    )
    serviceRegistries: List[Dict[str, Any]] = Field(
        default_factory=list, alias="ServiceRegistries"
    )
    platformVersion: Optional[str] = Field(default=None, alias="PlatformVersion")
    platformFamily: Optional[str] = Field(default=None, alias="PlatformFamily")
    capacityProviderStrategy: List[Dict[str, Any]] = Field(
        default_factory=list, alias="CapacityProviderStrategy"
    )
    enableExecuteCommand: Optional[bool] = Field(
        default=None, alias="EnableExecuteCommand"
    )
    enableECSManagedTags: Optional[bool] = Field(
        default=None, alias="EnableECSManagedTags"
    )
    healthCheckGracePeriodSeconds: Optional[int] = Field(
        default=None, alias="HealthCheckGracePeriodSeconds"
    )
    placementConstraints: List[Dict[str, Any]] = Field(
        default_factory=list, alias="PlacementConstraints"
    )
    placementStrategy: List[Dict[str, Any]] = Field(
        default_factory=list, alias="PlacementStrategy"
    )
    propagateTags: Optional[str] = Field(default=None, alias="PropagateTags")
    roleArn: Optional[str] = Field(default=None, alias="RoleArn")
    taskSets: List[Dict[str, Any]] = Field(default_factory=list, alias="TaskSets")
    availabilityZoneRebalancing: Optional[str] = Field(
        default=None, alias="AvailabilityZoneRebalancing"
    )
    tags: List[Dict[str, Any]] = Field(default_factory=list, alias="Tags")
    createdBy: Optional[str] = Field(default=None, alias="CreatedBy")
    createdAt: Optional[datetime] = Field(default=None, alias="CreatedAt")
    updatedAt: Optional[datetime] = Field(default=None, alias="UpdatedAt")

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class Service(ResourceModel[ServiceProperties]):
    Type: str = "AWS::ECS::Service"
    Properties: ServiceProperties = Field(default_factory=ServiceProperties)


class SingleServiceRequest(ResourceRequestModel):
    """Options for exporting a single ECS service."""

    service_name: str = Field(..., description="The name of the ECS service to export")
    cluster_name: str = Field(
        ..., description="The name of the ECS cluster containing the service"
    )


class PaginatedServiceRequest(ResourceRequestModel):
    """Options for exporting all ECS services in a region."""

    pass
