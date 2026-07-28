from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class ActionTypeIdProperties(BaseAWSPropertiesModel):
    category: str | None = Field(default=None, alias="Category")
    owner: str | None = Field(default=None, alias="Owner")
    provider: str | None = Field(default=None, alias="Provider")
    version: str | None = Field(default=None, alias="Version")


class CodePipelineActionProperties(BaseAWSPropertiesModel):
    actionTypeId: ActionTypeIdProperties = Field(
        default_factory=ActionTypeIdProperties, alias="ActionTypeId"
    )
    configuration: dict[str, str] | None = Field(default=None, alias="Configuration")
    commands: list[str] | None = Field(default=None, alias="Commands")
    environmentVariables: list[dict[str, Any]] | None = Field(
        default=None, alias="EnvironmentVariables"
    )
    inputArtifacts: list[dict[str, Any]] | None = Field(
        default=None, alias="InputArtifacts"
    )
    name: str = Field(default_factory=str, alias="Name")
    namespace: str | None = Field(default=None, alias="Namespace")
    outputArtifacts: list[dict[str, Any]] | None = Field(
        default=None, alias="OutputArtifacts"
    )
    outputVariables: list[str] | None = Field(default=None, alias="OutputVariables")
    pipelineName: str | None = Field(default=None, alias="PipelineName")
    pipelineArn: str | None = Field(default=None, alias="PipelineArn")
    pipelineVersion: int | None = Field(default=None, alias="PipelineVersion")
    region: str | None = Field(default=None, alias="Region")
    roleArn: str | None = Field(default=None, alias="RoleArn")
    runOrder: int | None = Field(default=None, alias="RunOrder")
    stageName: str | None = Field(default=None, alias="StageName")
    timeoutInMinutes: int | None = Field(default=None, alias="TimeoutInMinutes")


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
