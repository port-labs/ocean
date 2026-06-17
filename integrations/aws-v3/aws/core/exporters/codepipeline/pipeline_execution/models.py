from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class PipelineExecutionProperties(BaseModel):
    pipelineArn: str = Field(default_factory=str)
    pipelineName: str = Field(default_factory=str)
    pipelineVersion: int | None = None
    pipelineExecutionId: str = Field(default_factory=str)
    status: str | None = None
    statusSummary: str = None
    artifactRevisions: list[dict[str, Any]] = Field(default_factory=list)
    variableValues: dict[str, str] = None
    trigger: dict[str, Any] = None
    executionMode: str | None = None
    rollbackMetadata: dict[str, Any] = None
    pipelineExecutionDisplayName: str | None = None
    stageStates: list[dict[str, Any]] | None = Field(default=None)
    region: str = Field(default_factory=str)
    createdAt: str | None = None
    updatedAt: str | None = None

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
