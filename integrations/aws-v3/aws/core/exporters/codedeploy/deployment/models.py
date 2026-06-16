from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class CodeDeployDeploymentProperties(BaseModel):
    """Properties for a CodeDeploy Deployment resource."""

    AdditionalDeploymentStatusInfo: Optional[str] = None
    ApplicationName: Optional[str] = None
    AutoRollbackConfiguration: Optional[Dict[str, Any]] = None
    BlueGreenDeploymentConfiguration: Optional[Dict[str, Any]] = None
    CompleteTime: Optional[datetime] = None
    ComputePlatform: Optional[str] = None
    CreateTime: Optional[datetime] = None
    Creator: Optional[str] = None
    DeploymentConfigName: Optional[str] = None
    DeploymentGroupName: Optional[str] = None
    DeploymentId: str = Field(default_factory=str)
    DeploymentOverview: Optional[Dict[str, Any]] = None
    DeploymentStatusMessages: Optional[List[str]] = None
    DeploymentStyle: Optional[Dict[str, Any]] = None
    Description: Optional[str] = None
    ErrorInformation: Optional[Dict[str, Any]] = None
    ExternalId: Optional[str] = None
    FileExistsBehavior: Optional[str] = None
    IgnoreApplicationStopFailures: Optional[bool] = None
    InstanceTerminationWaitTimeStarted: Optional[bool] = None
    LoadBalancerInfo: Optional[Dict[str, Any]] = None
    OverrideAlarmConfiguration: Optional[Dict[str, Any]] = None
    PreviousRevision: Optional[Dict[str, Any]] = None
    RelatedDeployments: Optional[Dict[str, Any]] = None
    Revision: Optional[Dict[str, Any]] = None
    RollbackInfo: Optional[Dict[str, Any]] = None
    StartTime: Optional[datetime] = None
    Status: Optional[str] = None
    TargetInstances: Optional[Dict[str, Any]] = None
    UpdateOutdatedInstancesOnly: Optional[bool] = None

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
