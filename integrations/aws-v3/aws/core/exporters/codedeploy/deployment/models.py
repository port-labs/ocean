from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class CodeDeployDeploymentProperties(BaseModel):
    """Properties for a CodeDeploy Deployment resource."""

    ApplicationName: Optional[str] = None
    DeploymentGroupName: Optional[str] = None
    DeploymentId: str = Field(default_factory=str)
    Status: Optional[str] = None
    ErrorInformation: Optional[Dict[str, Any]] = None
    CreateTime: Optional[datetime] = None
    StartTime: Optional[datetime] = None
    CompleteTime: Optional[datetime] = None
    DeploymentOverview: Optional[Dict[str, Any]] = None
    Description: Optional[str] = None
    Creator: Optional[str] = None
    IgnoreApplicationStopFailures: Optional[bool] = None
    AutoRollbackConfiguration: Optional[Dict[str, Any]] = None
    UpdateOutdatedInstancesOnly: Optional[bool] = None
    RollbackInfo: Optional[Dict[str, Any]] = None
    DeploymentStyle: Optional[Dict[str, Any]] = None
    TargetInstances: Optional[Dict[str, Any]] = None
    InstanceTerminationWaitTimeStarted: Optional[bool] = None
    BlueGreenDeploymentConfiguration: Optional[Dict[str, Any]] = None
    LoadBalancerInfo: Optional[Dict[str, Any]] = None
    AdditionalDeploymentStatusInfo: Optional[str] = None
    FileExistsBehavior: Optional[str] = None
    ExternalId: Optional[str] = None
    Revision: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"
        allow_population_by_name = True


class CodeDeployDeployment(ResourceModel[CodeDeployDeploymentProperties]):
    """CodeDeploy Deployment resource model using the generic ResourceModel pattern."""

    Type: str = "AWS::CodeDeploy::Deployment"
    Properties: CodeDeployDeploymentProperties = Field(default_factory=CodeDeployDeploymentProperties)


class SingleCodeDeployDeploymentRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy deployment."""

    deployment_id: str = Field(..., description="The ID of the CodeDeploy deployment to export")


class PaginatedCodeDeployDeploymentRequest(ResourceRequestModel):
    """Options for exporting paginated CodeDeploy deployments."""