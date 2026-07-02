from datetime import datetime
from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel


class CodePipelineActionExecutionProperties(BaseAWSPropertiesModel):
    actionExecutionId: str | None = Field(default=None, alias="ActionExecutionId")
    actionName: str | None = Field(default=None, alias="ActionName")
    input: dict[str, Any] | None = Field(default=None, alias="Input")
    lastUpdateTime: datetime | None = Field(default=None, alias="LastUpdateTime")
    output: dict[str, Any] | None = Field(default=None, alias="Output")
    pipelineExecutionId: str | None = Field(default=None, alias="PipelineExecutionId")
    pipelineVersion: int | None = Field(default=None, alias="PipelineVersion")
    stageName: str | None = Field(default=None, alias="StageName")
    startTime: datetime | None = Field(default=None, alias="StartTime")
    status: str | None = Field(default=None, alias="Status")
    updatedBy: str | None = Field(default=None, alias="UpdatedBy")


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
