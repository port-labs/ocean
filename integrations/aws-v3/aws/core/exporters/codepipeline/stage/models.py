from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class StageProperties(BaseModel):
    actions: list[dict[str, Any]] | None = Field(default=None, alias="Actions")
    beforeEntry: dict[str, Any] | None = Field(default=None, alias="BeforeEntry")
    blockers: list[dict[str, Any]] | None = Field(default=None, alias="Blockers")
    name: str = Field(default_factory=str, alias="Name")
    onFailure: dict[str, Any] | None = Field(default=None, alias="OnFailure")
    onSuccess: dict[str, Any] | None = Field(default=None, alias="OnSuccess")
    order: int | None = Field(default=None, alias="Order")
    pipelineArn: str | None = Field(default=None, alias="PipelineArn")
    pipelineName: str = Field(default_factory=str, alias="PipelineName")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineStage(ResourceModel[StageProperties]):
    Type: str = "AWS::CodePipeline::Stage"
    Properties: StageProperties = Field(default_factory=StageProperties)


class SingleCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline stage."""

    pipeline_name: str = Field(..., description="The name of the CodePipeline pipeline")
    stage_name: str = Field(
        ..., description="The name of the stage within the pipeline"
    )


class PaginatedCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline stages in a region."""

    pass
