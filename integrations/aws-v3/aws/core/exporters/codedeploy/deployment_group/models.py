from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class DeploymentGroupProperties(BaseModel):
    ApplicationName: str = Field(default_factory=str)
    DeploymentGroupName: str = Field(default_factory=str)
    DeploymentGroupId: str = Field(default_factory=str)
    ServiceRoleArn: Optional[str] = None
    AutoRollbackConfiguration: Optional[Dict[str, Any]] = None
    TriggerConfigurations: List[Dict[str, Any]] = Field(default_factory=list)
    AlarmConfiguration: Optional[Dict[str, Any]] = None
    OutdatedInstancesStrategy: Optional[str] = None
    DeploymentStyle: Optional[Dict[str, Any]] = None
    BlueGreenDeploymentConfiguration: Optional[Dict[str, Any]] = None
    LoadBalancerInfo: Optional[Dict[str, Any]] = None
    LastSuccessfulDeployment: Optional[Dict[str, Any]] = None
    LastAttemptedDeployment: Optional[Dict[str, Any]] = None
    Ec2TagFilters: List[Dict[str, Any]] = Field(default_factory=list)
    OnPremisesInstanceTagFilters: List[Dict[str, Any]] = Field(default_factory=list)
    AutoScalingGroups: List[Dict[str, Any]] = Field(default_factory=list)
    Ec2TagSetList: List[Dict[str, Any]] = Field(default_factory=list)
    OnPremisesTagSetList: List[Dict[str, Any]] = Field(default_factory=list)
    EcsServices: List[Dict[str, Any]] = Field(default_factory=list)
    ComputePlatform: Optional[str] = None
    Tags: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class CodeDeployDeploymentGroup(ResourceModel[DeploymentGroupProperties]):
    Type: str = "AWS::CodeDeploy::DeploymentGroup"
    Properties: DeploymentGroupProperties = Field(default_factory=DeploymentGroupProperties)


class SingleCodeDeployDeploymentGroupRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy deployment group."""

    application_name: str = Field(..., description="The name of the CodeDeploy application")
    deployment_group_name: str = Field(..., description="The name of the deployment group")


class PaginatedCodeDeployDeploymentGroupRequest(ResourceRequestModel):
    """Options for exporting all CodeDeploy deployment groups in a region."""

    pass
