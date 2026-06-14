from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class DeploymentGroupProperties(BaseModel):
    alarmConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="AlarmConfiguration"
    )
    applicationName: str = Field(default_factory=str, alias="ApplicationName")
    autoRollbackConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="AutoRollbackConfiguration"
    )
    autoScalingGroups: List[Dict[str, Any]] = Field(
        default_factory=list, alias="AutoScalingGroups"
    )
    blueGreenDeploymentConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="BlueGreenDeploymentConfiguration"
    )
    computePlatform: Optional[str] = Field(default=None, alias="ComputePlatform")
    deploymentConfigName: Optional[str] = Field(
        default=None, alias="DeploymentConfigName"
    )
    deploymentGroupId: str = Field(default_factory=str, alias="DeploymentGroupId")
    deploymentGroupName: str = Field(default_factory=str, alias="DeploymentGroupName")
    deploymentStyle: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentStyle"
    )
    ec2TagFilters: List[Dict[str, Any]] = Field(
        default_factory=list, alias="Ec2TagFilters"
    )
    ec2TagSet: list[dict[str, Any]] | None = Field(default=None, alias="Ec2TagSet")
    ecsServices: List[Dict[str, Any]] = Field(default_factory=list, alias="EcsServices")
    lastAttemptedDeployment: Optional[Dict[str, Any]] = Field(
        default=None, alias="LastAttemptedDeployment"
    )
    lastSuccessfulDeployment: Optional[Dict[str, Any]] = Field(
        default=None, alias="LastSuccessfulDeployment"
    )
    loadBalancerInfo: Optional[Dict[str, Any]] = Field(
        default_factory=dict, alias="LoadBalancerInfo"
    )
    onPremisesInstanceTagFilters: List[Dict[str, Any]] = Field(
        default_factory=list, alias="OnPremisesInstanceTagFilters"
    )
    onPremisesTagSet: list[dict[str, Any]] | None = Field(default=None, alias="OnPremisesTagSet")
    outdatedInstancesStrategy: Optional[str] = Field(
        default=None, alias="OutdatedInstancesStrategy"
    )
    serviceRoleArn: Optional[str] = Field(default=None, alias="ServiceRoleArn")
    Tags: List[Dict[str, str]] = Field(default_factory=list)
    targetRevision: Optional[dict[str, Any]] = Field(
        default=None, alias="TargetRevision"
    )
    terminationHookEnabled: Optional[bool] = Field(
        default=None, alias="TerminationHookEnabled"
    )
    triggerConfigurations: List[Dict[str, Any]] = Field(
        default_factory=list, alias="TriggerConfigurations"
    )

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


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
