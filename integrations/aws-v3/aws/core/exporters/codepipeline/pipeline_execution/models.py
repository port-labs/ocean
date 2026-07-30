from datetime import datetime
from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class PipelineExecutionProperties(BaseAWSPropertiesModel):
    artifactRevisions: list[dict[str, Any]] | None = Field(
        default=None, alias="ArtifactRevisions"
    )
    executionMode: str | None = Field(default=None, alias="ExecutionMode")
    executionType: str | None = Field(default=None, alias="ExecutionType")
    lastUpdateTime: datetime | None = Field(default=None, alias="LastUpdateTime")
    pipelineExecutionId: str | None = Field(default=None, alias="PipelineExecutionId")
    pipelineName: str | None = Field(default=None, alias="PipelineName")
    pipelineVersion: int | None = Field(default=None, alias="PipelineVersion")
    rollbackMetadata: dict[str, Any] | None = Field(
        default=None, alias="RollbackMetadata"
    )
    sourceRevisions: list[dict[str, Any]] | None = Field(
        default=None, alias="SourceRevisions"
    )
    startTime: datetime | None = Field(default=None, alias="StartTime")
    status: str | None = Field(default=None, alias="Status")
    statusSummary: str | None = Field(default=None, alias="StatusSummary")
    stopTrigger: dict[str, Any] | None = Field(default=None, alias="StopTrigger")
    trigger: dict[str, Any] | None = Field(default=None, alias="Trigger")
    variables: list[dict[str, Any]] | None = Field(default=None, alias="Variables")


class PipelineExecution(ResourceModel[PipelineExecutionProperties]):
    Type: str = "AWS::CodePipeline::PipelineExecution"
    Properties: PipelineExecutionProperties = Field(
        default_factory=PipelineExecutionProperties
    )


class SinglePipelineExecutionRequest(ResourceRequestModel):
    """Options for exporting a single pipeline execution."""

    pipeline_name: str = Field(..., description="The name of the pipeline")
    pipeline_execution_id: str = Field(
        ..., description="The ID of the pipeline execution to export"
    )


class PaginatedPipelineExecutionRequest(ResourceRequestModel):
    """Options for exporting all pipeline executions in a region."""

    pass
