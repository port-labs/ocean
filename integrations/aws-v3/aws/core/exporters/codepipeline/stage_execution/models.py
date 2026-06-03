from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ActionExecutionProperties(BaseModel):
    """Properties for an action execution within a stage execution."""
    actionExecutionId: str = Field(default_factory=str)
    actionName: str = Field(default_factory=str)
    pipelineName: str = Field(default_factory=str)
    pipelineVersion: Optional[int] = None
    stageName: str = Field(default_factory=str)
    status: Optional[str] = None
    token: Optional[str] = None
    lastStatusChange: Optional[str] = None
    externalExecutionId: Optional[str] = None
    externalExecutionUrl: Optional[str] = None
    percentComplete: Optional[int] = None
    errorDetails: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class StageExecutionProperties(BaseModel):
    """Properties for a CodePipeline stage execution."""
    pipelineExecutionId: str = Field(default_factory=str)
    pipelineName: str = Field(default_factory=str)
    pipelineVersion: Optional[int] = None
    stageName: str = Field(default_factory=str)
    status: Optional[str] = None
    actionExecutionDetails: List[ActionExecutionProperties] = Field(default_factory=list)

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class CodePipelineStageExecution(ResourceModel[StageExecutionProperties]):
    """Model for a CodePipeline stage execution resource."""
    Type: str = "AWS::CodePipeline::StageExecution"
    Properties: StageExecutionProperties = Field(default_factory=StageExecutionProperties)


class SingleStageExecutionRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline stage execution."""
    pipeline_name: str = Field(..., description="The name of the pipeline")
    pipeline_execution_id: str = Field(..., description="The ID of the pipeline execution")


class PaginatedStageExecutionRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline stage executions in a region."""
    pass