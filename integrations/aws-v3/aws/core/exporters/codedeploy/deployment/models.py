from typing import Any
from datetime import datetime
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class CodeDeployDeploymentProperties(BaseAWSPropertiesModel):
    """Properties for a CodeDeploy Deployment resource."""

    additionalDeploymentStatusInfo: str | None = Field(
        default=None, alias="AdditionalDeploymentStatusInfo"
    )
    applicationName: str | None = Field(default=None, alias="ApplicationName")
    autoRollbackConfiguration: dict[str, Any] | None = Field(
        default=None, alias="AutoRollbackConfiguration"
    )
    blueGreenDeploymentConfiguration: dict[str, Any] | None = Field(
        default=None, alias="BlueGreenDeploymentConfiguration"
    )
    completeTime: datetime | None = Field(default=None, alias="CompleteTime")
    computePlatform: str | None = Field(default=None, alias="ComputePlatform")
    createTime: datetime | None = Field(default=None, alias="CreateTime")
    creator: str | None = Field(default=None, alias="Creator")
    deploymentConfigName: str | None = Field(default=None, alias="DeploymentConfigName")
    deploymentGroupName: str | None = Field(default=None, alias="DeploymentGroupName")
    deploymentId: str = Field(default_factory=str, alias="DeploymentId")
    deploymentOverview: dict[str, Any] | None = Field(
        default=None, alias="DeploymentOverview"
    )
    deploymentStatusMessages: list[str] | None = Field(
        default=None, alias="DeploymentStatusMessages"
    )
    deploymentStyle: dict[str, Any] | None = Field(
        default=None, alias="DeploymentStyle"
    )
    description: str | None = Field(default=None, alias="Description")
    errorInformation: dict[str, Any] | None = Field(
        default=None, alias="ErrorInformation"
    )
    externalId: str | None = Field(default=None, alias="ExternalId")
    fileExistsBehavior: str | None = Field(default=None, alias="FileExistsBehavior")
    ignoreApplicationStopFailures: bool | None = Field(
        default=None, alias="IgnoreApplicationStopFailures"
    )
    instanceTerminationWaitTimeStarted: bool | None = Field(
        default=None, alias="InstanceTerminationWaitTimeStarted"
    )
    loadBalancerInfo: dict[str, Any] | None = Field(
        default=None, alias="LoadBalancerInfo"
    )
    overrideAlarmConfiguration: dict[str, Any] | None = Field(
        default=None, alias="OverrideAlarmConfiguration"
    )
    previousRevision: dict[str, Any] | None = Field(
        default=None, alias="PreviousRevision"
    )
    relatedDeployments: dict[str, Any] | None = Field(
        default=None, alias="RelatedDeployments"
    )
    revision: dict[str, Any] | None = Field(default=None, alias="Revision")
    rollbackInfo: dict[str, Any] | None = Field(default=None, alias="RollbackInfo")
    startTime: datetime | None = Field(default=None, alias="StartTime")
    status: str | None = Field(default=None, alias="Status")
    targetInstances: dict[str, Any] | None = Field(
        default=None, alias="TargetInstances"
    )
    updateOutdatedInstancesOnly: bool | None = Field(
        default=None, alias="UpdateOutdatedInstancesOnly"
    )


class CodeDeployDeployment(ResourceModel[CodeDeployDeploymentProperties]):
    """CodeDeploy Deployment resource model using the generic ResourceModel pattern."""

    Type: str = "AWS::CodeDeploy::Deployment"
    Properties: CodeDeployDeploymentProperties = Field(
        default_factory=CodeDeployDeploymentProperties
    )


class SingleCodeDeployDeploymentRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy deployment."""

    deployment_id: str = Field(
        ..., description="The ID of the CodeDeploy deployment to export"
    )


class PaginatedCodeDeployDeploymentRequest(ResourceRequestModel):
    """Options for exporting paginated CodeDeploy deployments."""
