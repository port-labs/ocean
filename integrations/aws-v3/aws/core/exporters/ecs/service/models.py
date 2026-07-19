from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)
from datetime import datetime


class ServiceProperties(BaseAWSPropertiesModel):
    availabilityZoneRebalancing: str | None = Field(
        default=None, alias="AvailabilityZoneRebalancing"
    )
    capacityProviderStrategy: list[dict[str, Any]] = Field(
        default_factory=list, alias="CapacityProviderStrategy"
    )
    clusterArn: str = Field(default_factory=str, alias="ClusterArn")
    createdAt: datetime | None = Field(default=None, alias="CreatedAt")
    createdBy: str | None = Field(default=None, alias="CreatedBy")
    deploymentConfiguration: dict[str, Any] | None = Field(
        default=None, alias="DeploymentConfiguration"
    )
    deploymentController: dict[str, Any] | None = Field(
        default=None, alias="DeploymentController"
    )
    deployments: list[dict[str, Any]] = Field(default_factory=list, alias="Deployments")
    desiredCount: int = Field(default=0, alias="DesiredCount")
    enableECSManagedTags: bool | None = Field(
        default=None, alias="EnableECSManagedTags"
    )
    enableExecuteCommand: bool | None = Field(
        default=None, alias="EnableExecuteCommand"
    )
    events: list[dict[str, Any]] = Field(default_factory=list, alias="Events")
    healthCheckGracePeriodSeconds: int | None = Field(
        default=None, alias="HealthCheckGracePeriodSeconds"
    )
    launchType: str | None = Field(default=None, alias="LaunchType")
    loadBalancers: list[dict[str, Any]] = Field(
        default_factory=list, alias="LoadBalancers"
    )
    networkConfiguration: dict[str, Any] | None = Field(
        default=None, alias="NetworkConfiguration"
    )
    pendingCount: int = Field(default=0, alias="PendingCount")
    placementConstraints: list[dict[str, Any]] = Field(
        default_factory=list, alias="PlacementConstraints"
    )
    placementStrategy: list[dict[str, Any]] = Field(
        default_factory=list, alias="PlacementStrategy"
    )
    platformFamily: str | None = Field(default=None, alias="PlatformFamily")
    platformVersion: str | None = Field(default=None, alias="PlatformVersion")
    propagateTags: str | None = Field(default=None, alias="PropagateTags")
    roleArn: str | None = Field(default=None, alias="RoleArn")
    runningCount: int = Field(default=0, alias="RunningCount")
    schedulingStrategy: str | None = Field(default=None, alias="SchedulingStrategy")
    serviceArn: str = Field(default_factory=str, alias="ServiceArn")
    serviceName: str = Field(default_factory=str, alias="ServiceName")
    serviceRegistries: list[dict[str, Any]] = Field(
        default_factory=list, alias="ServiceRegistries"
    )
    status: str | None = Field(default=None, alias="Status")
    tags: list[dict[str, Any]] = Field(default_factory=list, alias="Tags")
    taskDefinition: str = Field(default_factory=str, alias="TaskDefinition")
    taskSets: list[dict[str, Any]] = Field(default_factory=list, alias="TaskSets")
    updatedAt: datetime | None = Field(default=None, alias="UpdatedAt")


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
