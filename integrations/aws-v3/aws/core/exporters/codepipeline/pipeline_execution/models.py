from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class PipelineExecutionProperties(BaseModel):
    artifactRevisions: list[dict[str, Any]] | None = None
    executionMode: str | None = None
    executionType: str | None = None
    lastUpdateTime: datetime | None = None
    pipelineExecutionId: str | None = None
    pipelineName: str | None = None
    pipelineVersion: int | None = None
    rollbackMetadata: dict[str, Any] | None = None
    sourceRevisions: list[dict[str, Any]] | None = None
    startTime: datetime | None = None
    status: str | None = None
    statusSummary: str | None = None
    stopTrigger: dict[str, Any] | None = None
    trigger: dict[str, Any] | None = None
    variables: list[dict[str, Any]] | None = None

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


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
