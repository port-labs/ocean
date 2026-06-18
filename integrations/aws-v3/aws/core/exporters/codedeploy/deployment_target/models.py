from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class DeploymentTargetProperties(BaseModel):
    deploymentId: str = Field(default_factory=str, alias="DeploymentId")
    deploymentTargetType: Optional[str] = Field(
        default=None, alias="DeploymentTargetType"
    )
    instanceTarget: Optional[Dict[str, Any]] = Field(
        default=None, alias="InstanceTarget"
    )
    lambdaTarget: Optional[Dict[str, Any]] = Field(default=None, alias="LambdaTarget")
    ecsTarget: Optional[Dict[str, Any]] = Field(default=None, alias="EcsTarget")
    cloudFormationTarget: Optional[Dict[str, Any]] = Field(
        default=None, alias="CloudFormationTarget"
    )
    targetId: str = Field(default_factory=str, alias="TargetId")
    targetArn: Optional[str] = Field(default=None, alias="TargetArn")
    status: Optional[str] = Field(default=None, alias="Status")
    lastUpdatedAt: Optional[str] = Field(default=None, alias="LastUpdatedAt")
    lifecycleEvents: List[Dict[str, Any]] = Field(
        default_factory=list, alias="LifecycleEvents"
    )

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodeDeployDeploymentTarget(ResourceModel[DeploymentTargetProperties]):
    Type: str = "AWS::CodeDeploy::DeploymentTarget"
    Properties: DeploymentTargetProperties = Field(
        default_factory=DeploymentTargetProperties
    )


class SingleCodeDeployDeploymentTargetRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy deployment target."""

    deployment_id: str = Field(
        ..., description="The ID of the CodeDeploy deployment"
    )
    target_id: str = Field(
        ..., description="The ID of the deployment target"
    )


class PaginatedCodeDeployDeploymentTargetRequest(ResourceRequestModel):
    """Options for exporting all CodeDeploy deployment targets in a region."""

    pass
