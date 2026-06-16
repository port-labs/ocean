from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class CodeDeployDeploymentProperties(BaseModel):
    """Properties for a CodeDeploy Deployment resource."""

    additionalDeploymentStatusInfo: Optional[str] = Field(
        default=None, alias="AdditionalDeploymentStatusInfo"
    )
    applicationName: Optional[str] = Field(default=None, alias="ApplicationName")
    autoRollbackConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="AutoRollbackConfiguration"
    )
    blueGreenDeploymentConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="BlueGreenDeploymentConfiguration"
    )
    completeTime: Optional[datetime] = Field(default=None, alias="CompleteTime")
    computePlatform: Optional[str] = Field(default=None, alias="ComputePlatform")
    createTime: Optional[datetime] = Field(default=None, alias="CreateTime")
    creator: Optional[str] = Field(default=None, alias="Creator")
    deploymentConfigName: Optional[str] = Field(
        default=None, alias="DeploymentConfigName"
    )
    deploymentGroupName: Optional[str] = Field(
        default=None, alias="DeploymentGroupName"
    )
    deploymentId: str = Field(default_factory=str, alias="DeploymentId")
    deploymentOverview: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentOverview"
    )
    deploymentStatusMessages: Optional[List[str]] = Field(
        default=None, alias="DeploymentStatusMessages"
    )
    deploymentStyle: Optional[Dict[str, Any]] = Field(
        default=None, alias="DeploymentStyle"
    )
    description: Optional[str] = Field(default=None, alias="Description")
    errorInformation: Optional[Dict[str, Any]] = Field(
        default=None, alias="ErrorInformation"
    )
    externalId: Optional[str] = Field(default=None, alias="ExternalId")
    fileExistsBehavior: Optional[str] = Field(default=None, alias="FileExistsBehavior")
    ignoreApplicationStopFailures: Optional[bool] = Field(
        default=None, alias="IgnoreApplicationStopFailures"
    )
    instanceTerminationWaitTimeStarted: Optional[bool] = Field(
        default=None, alias="InstanceTerminationWaitTimeStarted"
    )
    loadBalancerInfo: Optional[Dict[str, Any]] = Field(
        default=None, alias="LoadBalancerInfo"
    )
    overrideAlarmConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="OverrideAlarmConfiguration"
    )
    previousRevision: Optional[Dict[str, Any]] = Field(
        default=None, alias="PreviousRevision"
    )
    relatedDeployments: Optional[Dict[str, Any]] = Field(
        default=None, alias="RelatedDeployments"
    )
    revision: Optional[Dict[str, Any]] = Field(default=None, alias="Revision")
    rollbackInfo: Optional[Dict[str, Any]] = Field(default=None, alias="RollbackInfo")
    startTime: Optional[datetime] = Field(default=None, alias="StartTime")
    status: Optional[str] = Field(default=None, alias="Status")
    targetInstances: Optional[Dict[str, Any]] = Field(
        default=None, alias="TargetInstances"
    )
    updateOutdatedInstancesOnly: Optional[bool] = Field(
        default=None, alias="UpdateOutdatedInstancesOnly"
    )

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


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
