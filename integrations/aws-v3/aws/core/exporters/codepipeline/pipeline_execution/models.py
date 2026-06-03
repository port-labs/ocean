from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class PipelineExecutionArtifact(BaseModel):
    name: Optional[str] = None
    revision: Optional[str] = None
    location: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class PipelineExecutionActionExecution(BaseModel):
    actionExecutionId: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    lastStatusChange: Optional[str] = None
    token: Optional[str] = None
    lastUpdatedBy: Optional[str] = None
    externalExecutionId: Optional[str] = None
    externalExecutionUrl: Optional[str] = None
    percentComplete: Optional[int] = None
    errorDetails: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class PipelineExecutionStageExecution(BaseModel):
    pipelineExecutionId: Optional[str] = None
    stageName: Optional[str] = None
    status: Optional[str] = None
    actionExecutionDetails: Optional[List[PipelineExecutionActionExecution]] = Field(default_factory=list)

    class Config:
        extra = "forbid"
        populate_by_name = True


class PipelineExecutionProperties(BaseModel):
    pipelineArn: str = Field(default_factory=str)
    pipelineName: str = Field(default_factory=str)
    pipelineVersion: Optional[int] = None
    pipelineExecutionId: str = Field(default_factory=str)
    status: Optional[str] = None
    statusSummary: Optional[str] = None
    artifactRevisions: List[PipelineExecutionArtifact] = Field(default_factory=list)
    variableValues: Optional[Dict[str, str]] = None
    trigger: Optional[Dict[str, Any]] = None
    executionMode: Optional[str] = None
    rollbackMetadata: Optional[Dict[str, Any]] = None
    pipelineExecutionDisplayName: Optional[str] = None
    stageStates: List[PipelineExecutionStageExecution] = Field(default_factory=list)
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    region: str = Field(default_factory=str)
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class PipelineExecution(ResourceModel[PipelineExecutionProperties]):
    Type: str = "AWS::CodePipeline::PipelineExecution"
    Properties: PipelineExecutionProperties = Field(default_factory=PipelineExecutionProperties)


class SinglePipelineExecutionRequest(ResourceRequestModel):
    """Options for exporting a single pipeline execution."""
    pipeline_name: str = Field(..., description="The name of the pipeline")
    pipeline_execution_id: str = Field(..., description="The ID of the pipeline execution to export")


class PaginatedPipelineExecutionRequest(ResourceRequestModel):
    """Options for exporting all pipeline executions in a region."""
    pipeline_name: Optional[str] = Field(None, description="Optional pipeline name filter")
    max_results: Optional[int] = Field(100, description="Maximum number of results per page")