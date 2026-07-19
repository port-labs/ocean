from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel


class DeploymentTargetProperties(BaseAWSPropertiesModel):
    deploymentId: str = Field(default_factory=str, alias="DeploymentId")
    deploymentTargetType: str | None = Field(default=None, alias="DeploymentTargetType")
    instanceTarget: dict[str, Any] | None = Field(default=None, alias="InstanceTarget")
    lambdaTarget: dict[str, Any] | None = Field(default=None, alias="LambdaTarget")
    ecsTarget: dict[str, Any] | None = Field(default=None, alias="EcsTarget")
    cloudFormationTarget: dict[str, Any] | None = Field(
        default=None, alias="CloudFormationTarget"
    )


class CodeDeployDeploymentTarget(ResourceModel[DeploymentTargetProperties]):
    Type: str = "AWS::CodeDeploy::DeploymentTarget"
    Properties: DeploymentTargetProperties = Field(
        default_factory=DeploymentTargetProperties
    )


class SingleCodeDeployDeploymentTargetRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy deployment target."""

    deployment_id: str = Field(..., description="The ID of the CodeDeploy deployment")
    target_id: str = Field(..., description="The ID of the deployment target")


class PaginatedCodeDeployDeploymentTargetRequest(ResourceRequestModel):
    """Options for exporting all CodeDeploy deployment targets in a region."""

    pass
