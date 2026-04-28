from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class TaskDefinitionProperties(BaseModel):
    taskDefinitionArn: str = Field(default_factory=str, alias="TaskDefinitionArn")
    family: str = Field(default_factory=str, alias="Family")
    revision: int = Field(default=0, alias="Revision")
    status: Optional[str] = Field(default=None, alias="Status")
    containerDefinitions: List[Dict[str, Any]] = Field(
        default_factory=list, alias="ContainerDefinitions"
    )
    cpu: Optional[str] = Field(default=None, alias="Cpu")
    memory: Optional[str] = Field(default=None, alias="Memory")
    networkMode: Optional[str] = Field(default=None, alias="NetworkMode")
    requiresCompatibilities: List[str] = Field(
        default_factory=list, alias="RequiresCompatibilities"
    )
    taskRoleArn: Optional[str] = Field(default=None, alias="TaskRoleArn")
    executionRoleArn: Optional[str] = Field(default=None, alias="ExecutionRoleArn")
    volumes: List[Dict[str, Any]] = Field(default_factory=list, alias="Volumes")
    placementConstraints: List[Dict[str, Any]] = Field(
        default_factory=list, alias="PlacementConstraints"
    )
    tags: List[Dict[str, Any]] = Field(default_factory=list, alias="Tags")
    registeredAt: Optional[datetime] = Field(default=None, alias="RegisteredAt")

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class TaskDefinition(ResourceModel[TaskDefinitionProperties]):
    Type: str = "AWS::ECS::TaskDefinition"
    Properties: TaskDefinitionProperties = Field(
        default_factory=TaskDefinitionProperties
    )


class SingleTaskDefinitionRequest(ResourceRequestModel):
    """Options for exporting a single ECS task definition."""

    task_definition_arn: str = Field(
        ..., description="The ARN of the ECS task definition to export"
    )


class PaginatedTaskDefinitionRequest(ResourceRequestModel):
    """Options for exporting all ECS task definitions in a region."""

    pass
