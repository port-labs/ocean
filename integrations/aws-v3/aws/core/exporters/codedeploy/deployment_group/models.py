from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class DeploymentGroupProperties(BaseAWSPropertiesModel):
    alarmConfiguration: dict[str, Any] | None = Field(
        default=None, alias="AlarmConfiguration"
    )
    applicationName: str = Field(default_factory=str, alias="ApplicationName")
    autoRollbackConfiguration: dict[str, Any] | None = Field(
        default=None, alias="AutoRollbackConfiguration"
    )
    autoScalingGroups: list[dict[str, Any]] = Field(
        default_factory=list, alias="AutoScalingGroups"
    )
    blueGreenDeploymentConfiguration: dict[str, Any] | None = Field(
        default=None, alias="BlueGreenDeploymentConfiguration"
    )
    computePlatform: str | None = Field(default=None, alias="ComputePlatform")
    deploymentConfigName: str | None = Field(default=None, alias="DeploymentConfigName")
    deploymentGroupId: str = Field(default_factory=str, alias="DeploymentGroupId")
    deploymentGroupName: str = Field(default_factory=str, alias="DeploymentGroupName")
    deploymentStyle: dict[str, Any] | None = Field(
        default=None, alias="DeploymentStyle"
    )
    ec2TagFilters: list[dict[str, Any]] = Field(
        default_factory=list, alias="Ec2TagFilters"
    )
    ec2TagSet: list[dict[str, Any]] | None = Field(default=None, alias="Ec2TagSet")
    ecsServices: list[dict[str, Any]] = Field(default_factory=list, alias="EcsServices")
    lastAttemptedDeployment: dict[str, Any] | None = Field(
        default=None, alias="LastAttemptedDeployment"
    )
    lastSuccessfulDeployment: dict[str, Any] | None = Field(
        default=None, alias="LastSuccessfulDeployment"
    )
    loadBalancerInfo: dict[str, Any] | None = Field(
        default_factory=dict, alias="LoadBalancerInfo"
    )
    onPremisesInstanceTagFilters: list[dict[str, Any]] = Field(
        default_factory=list, alias="OnPremisesInstanceTagFilters"
    )
    onPremisesTagSet: list[dict[str, Any]] | None = Field(
        default=None, alias="OnPremisesTagSet"
    )
    outdatedInstancesStrategy: str | None = Field(
        default=None, alias="OutdatedInstancesStrategy"
    )
    serviceRoleArn: str | None = Field(default=None, alias="ServiceRoleArn")
    Tags: list[dict[str, str]] = Field(default_factory=list)
    targetRevision: dict[str, Any] | None = Field(default=None, alias="TargetRevision")
    terminationHookEnabled: bool | None = Field(
        default=None, alias="TerminationHookEnabled"
    )
    triggerConfigurations: list[dict[str, Any]] = Field(
        default_factory=list, alias="TriggerConfigurations"
    )


class CodeDeployDeploymentGroup(ResourceModel[DeploymentGroupProperties]):
    Type: str = "AWS::CodeDeploy::DeploymentGroup"
    Properties: DeploymentGroupProperties = Field(
        default_factory=DeploymentGroupProperties
    )


class SingleCodeDeployDeploymentGroupRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy deployment group."""

    application_name: str = Field(
        ..., description="The name of the CodeDeploy application"
    )
    deployment_group_name: str = Field(
        ..., description="The name of the deployment group"
    )


class PaginatedCodeDeployDeploymentGroupRequest(ResourceRequestModel):
    """Options for exporting all CodeDeploy deployment groups in a region."""

    pass
