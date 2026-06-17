from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class StageProperties(BaseModel):
    Actions: list[dict[str, Any]] | None = Field(default=None)
    Blockers: list[dict[str, Any]] | None = Field(default=None)
    PipelineArn: str | None = Field(default=None)
    PipelineName: str = Field(default_factory=str)
    StageName: str = Field(default_factory=str)
    StageOrder: int | None = Field(default=None)
    Tags: list[dict[str, str]] | None = Field(default=None)

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineStage(ResourceModel[StageProperties]):
    Type: str = "AWS::CodePipeline::Stage"
    Properties: StageProperties = Field(default_factory=StageProperties)


class SingleCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline stage."""

    pipeline_name: str = Field(
        ..., description="The name of the CodePipeline pipeline"
    )
    stage_name: str = Field(
        ..., description="The name of the stage within the pipeline"
    )


class PaginatedCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline stages in a region."""

    pass
