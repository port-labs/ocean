from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ActionTypeIdProperties(BaseModel):
    category: Optional[str] = Field(default=None, alias="Category")
    owner: Optional[str] = Field(default=None, alias="Owner")
    provider: Optional[str] = Field(default=None, alias="Provider")
    version: Optional[str] = Field(default=None, alias="Version")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ActionExecutionInputProperties(BaseModel):
    actionTypeId: Optional[ActionTypeIdProperties] = Field(
        default=None, alias="ActionTypeId"
    )
    configuration: Optional[Dict[str, str]] = Field(default=None, alias="Configuration")
    resolvedConfiguration: Optional[Dict[str, str]] = Field(
        default=None, alias="ResolvedConfiguration"
    )
    roleArn: Optional[str] = Field(default=None, alias="RoleArn")
    region: Optional[str] = Field(default=None, alias="Region")
    inputArtifacts: Optional[List[Dict[str, Any]]] = Field(
        default=None, alias="InputArtifacts"
    )
    namespace: Optional[str] = Field(default=None, alias="Namespace")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ActionExecutionResultProperties(BaseModel):
    externalExecutionId: Optional[str] = Field(
        default=None, alias="ExternalExecutionId"
    )
    externalExecutionSummary: Optional[str] = Field(
        default=None, alias="ExternalExecutionSummary"
    )
    externalExecutionUrl: Optional[str] = Field(
        default=None, alias="ExternalExecutionUrl"
    )
    errorDetails: Optional[Dict[str, str]] = Field(default=None, alias="ErrorDetails")
    logStreamARN: Optional[str] = Field(default=None, alias="LogStreamARN")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ActionExecutionOutputProperties(BaseModel):
    outputArtifacts: Optional[List[Dict[str, Any]]] = Field(
        default=None, alias="OutputArtifacts"
    )
    executionResult: Optional[ActionExecutionResultProperties] = Field(
        default=None, alias="ExecutionResult"
    )
    outputVariables: Optional[Dict[str, str]] = Field(
        default=None, alias="OutputVariables"
    )

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineActionExecutionProperties(BaseModel):
    actionExecutionId: Optional[str] = Field(default=None, alias="ActionExecutionId")
    actionName: Optional[str] = Field(default=None, alias="ActionName")
    pipelineExecutionId: Optional[str] = Field(
        default=None, alias="PipelineExecutionId"
    )
    pipelineVersion: Optional[int] = Field(default=None, alias="PipelineVersion")
    pipelineName: Optional[str] = Field(default=None, alias="PipelineName")
    stageName: Optional[str] = Field(default=None, alias="StageName")
    startTime: Optional[datetime] = Field(default=None, alias="StartTime")
    lastUpdateTime: Optional[datetime] = Field(default=None, alias="LastUpdateTime")
    updatedBy: Optional[str] = Field(default=None, alias="UpdatedBy")
    status: Optional[str] = Field(default=None, alias="Status")
    input: Optional[ActionExecutionInputProperties] = Field(
        default=None, alias="Input"
    )
    output: Optional[ActionExecutionOutputProperties] = Field(
        default=None, alias="Output"
    )

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineActionExecution(ResourceModel[CodePipelineActionExecutionProperties]):
    Type: str = "AWS::CodePipeline::ActionExecution"
    Properties: CodePipelineActionExecutionProperties = Field(
        default_factory=CodePipelineActionExecutionProperties
    )


class SingleCodePipelineActionExecutionRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline action execution."""

    pipeline_name: str = Field(
        ..., description="The name of the pipeline containing the action execution"
    )
    action_execution_id: str = Field(
        ..., description="The ID of the action execution to export"
    )


class PaginatedCodePipelineActionExecutionRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline action executions in a region."""

    pass
