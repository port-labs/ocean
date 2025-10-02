from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class ServiceProperties(BaseModel):
    availabilityZoneRebalancing: Optional[str] = Field(
        default=None, alias="AvailabilityZoneRebalancing"
    )
    capacityProviderStrategy: List[Dict[str, Any]] = Field(
        default_factory=list, alias="CapacityProviderStrategy"
    )
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")
    createdAt: Optional[datetime] = Field(default=None, alias="CreatedAt")
    createdBy: Optional[str] = Field(default=None, alias="CreatedBy")
    deploymentConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentConfiguration"
    )
    deploymentController: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentController"
    )
    deployments: List[Dict[str, Any]] = Field(default_factory=list, alias="Deployments")
    desiredCount: int = Field(default=0, alias="DesiredCount")
    enableECSManagedTags: Optional[bool] = Field(
        default=None, alias="EnableECSManagedTags"
    )
    enableExecuteCommand: Optional[bool] = Field(
        default=None, alias="EnableExecuteCommand"
    )
    events: List[Dict[str, Any]] = Field(default_factory=list, alias="Events")
    healthCheckGracePeriodSeconds: Optional[int] = Field(
        default=None, alias="HealthCheckGracePeriodSeconds"
    )
    launchType: Optional[str] = Field(default=None, alias="LaunchType")
    loadBalancers: List[Dict[str, Any]] = Field(
        default_factory=list, alias="LoadBalancers"
    )
    networkConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="NetworkConfiguration"
    )
    pendingCount: int = Field(default=0, alias="PendingCount")
    placementConstraints: List[Dict[str, Any]] = Field(
        default_factory=list, alias="PlacementConstraints"
    )
    placementStrategy: List[Dict[str, Any]] = Field(
        default_factory=list, alias="PlacementStrategy"
    )
    platformFamily: Optional[str] = Field(default=None, alias="PlatformFamily")
    platformVersion: Optional[str] = Field(default=None, alias="PlatformVersion")
    propagateTags: Optional[str] = Field(default=None, alias="PropagateTags")
    roleArn: Optional[str] = Field(default=None, alias="RoleArn")
    runningCount: int = Field(default=0, alias="RunningCount")
    schedulingStrategy: Optional[str] = Field(default=None, alias="SchedulingStrategy")
    serviceArn: str = Field(default_factory=str, alias="ServiceArn")
    serviceName: str = Field(default_factory=str, alias="ServiceName")
    serviceRegistries: List[Dict[str, Any]] = Field(
        default_factory=list, alias="ServiceRegistries"
    )
    status: Optional[str] = Field(default=None, alias="Status")
    tags: List[Dict[str, Any]] = Field(default_factory=list, alias="Tags")
    taskDefinition: str = Field(default_factory=str, alias="TaskDefinition")
    taskSets: List[Dict[str, Any]] = Field(default_factory=list, alias="TaskSets")
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
