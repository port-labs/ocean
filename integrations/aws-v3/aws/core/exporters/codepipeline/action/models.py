from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ActionTypeIdProperties(BaseModel):
    category: str | None = Field(default=None, alias="Category")
    owner: str | None = Field(default=None, alias="Owner")
    provider: str | None = Field(default=None, alias="Provider")
    version: str | None = Field(default=None, alias="Version")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineActionProperties(BaseModel):
    actionTypeId: ActionTypeIdProperties = Field(
        default_factory=ActionTypeIdProperties, alias="ActionTypeId"
    )
    configuration: Optional[Dict[str, str]] = Field(default=None, alias="Configuration")
    commands: Optional[List[str]] = Field(default=None, alias="Commands")
    environmentVariables: Optional[List[dict[str, Any]]] = Field(
        default=None, alias="EnvironmentVariables"
    )
    inputArtifacts: Optional[List[dict[str, Any]]] = Field(
        default=None, alias="InputArtifacts"
    )
    name: str = Field(default_factory=str, alias="Name")
    namespace: Optional[str] = Field(default=None, alias="Namespace")
    outputArtifacts: Optional[List[dict[str, Any]]] = Field(
        default=None, alias="OutputArtifacts"
    )
    outputVariables: Optional[List[str]] = Field(default=None, alias="OutputVariables")
    pipelineName: Optional[str] = Field(default=None, alias="PipelineName")
    pipelineArn: Optional[str] = Field(default=None, alias="PipelineArn")
    pipelineVersion: Optional[int] = Field(default=None, alias="PipelineVersion")
    region: Optional[str] = Field(default=None, alias="Region")
    roleArn: Optional[str] = Field(default=None, alias="RoleArn")
    runOrder: Optional[int] = Field(default=None, alias="RunOrder")
    stageName: Optional[str] = Field(default=None, alias="StageName")
    timeoutInMinutes: Optional[int] = Field(default=None, alias="TimeoutInMinutes")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineAction(ResourceModel[CodePipelineActionProperties]):
    Type: str = "AWS::CodePipeline::Action"
    Properties: CodePipelineActionProperties = Field(
        default_factory=CodePipelineActionProperties
    )


class SingleCodePipelineActionRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline action."""

    pipeline_name: str = Field(
        ..., description="The name of the pipeline containing the action"
    )
    stage_name: str = Field(
        ..., description="The name of the stage containing the action"
    )
    action_name: str = Field(..., description="The name of the action to export")


class PaginatedCodePipelineActionRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline actions in a region."""

    pass
